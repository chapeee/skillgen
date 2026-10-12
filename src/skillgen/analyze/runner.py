"""Run the analysis step: headless Claude Code, a file Claude Code wrote, or a replay.

All three return the same validated `page-analysis` document.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from skillgen.analyze.prompt import AnalysisRequest, build_analysis_prompt
from skillgen.errors import AnalysisError
from skillgen.routes.naming import slugify_route
from skillgen.schema import find_schema_problems, load_schema

logger = logging.getLogger(__name__)

CLAUDE_EXECUTABLE = "claude"
READ_ONLY_TOOLS = ("Read", "Grep", "Glob")
SHELL_SCRIPT_SUFFIXES = (".cmd", ".bat")
DEFAULT_TIMEOUT_SECONDS = 900
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

AnalysisDocument = dict[str, Any]


class Analyzer(Protocol):
    """Anything that turns an analysis request into a page-analysis document."""

    def analyze(self, request: AnalysisRequest) -> AnalysisDocument:
        """Analyse one route.

        Args:
            request: The route and what is known about it.

        Returns:
            The validated page-analysis document.
        """


def check_analysis(document: object, source: str) -> AnalysisDocument:
    """Validate a page-analysis document.

    Args:
        document: The parsed document.
        source: Where it came from, for error messages.

    Returns:
        The same document, typed.

    Raises:
        AnalysisError: If it does not match the schema.
    """
    problems = find_schema_problems(document, "page-analysis")
    if problems or not isinstance(document, dict):
        raise AnalysisError(
            f"analysis from {source} does not match the schema: " + "; ".join(problems[:5])
        )
    return document


def parse_claude_output(stdout: str) -> object:
    """Pull the structured result out of `claude -p --output-format json` output.

    Args:
        stdout: The command's standard output.

    Returns:
        The parsed analysis document.

    Raises:
        AnalysisError: If no JSON result can be found.
    """
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise AnalysisError(
            f"claude printed something that is not JSON: {stdout[:200]!r}"
        ) from error
    if isinstance(envelope, dict) and envelope.get("is_error"):
        raise AnalysisError(f"claude reported an error: {str(envelope.get('result', ''))[:300]}")
    if isinstance(envelope, dict) and isinstance(envelope.get("structured_output"), dict):
        return envelope["structured_output"]
    result = envelope.get("result") if isinstance(envelope, dict) else None
    if isinstance(result, str):
        try:
            return json.loads(_FENCE.sub("", result.strip()))
        except json.JSONDecodeError as error:
            raise AnalysisError(
                "claude's result is not the JSON object the schema asks for"
            ) from error
    raise AnalysisError("claude's output has no result")


def schema_for_claude(name: str = "page-analysis") -> dict[str, Any]:
    """Return a shipped schema in the form `claude --json-schema` accepts.

    Claude Code's validator does not know the draft 2020-12 meta-schema URL, so the
    `$schema` key is dropped; the rest of the schema is unchanged.

    Args:
        name: The schema name.

    Returns:
        The schema without `$schema`.
    """
    return {key: value for key, value in load_schema(name).items() if key != "$schema"}


def build_claude_command(
    executable: str, schema_name: str, model: str = "", has_schema_argument: bool = True
) -> list[str]:
    """Build a read-only `claude -p` command that must answer in a schema.

    The prompt is not part of the command: it goes on standard input, where no shell
    can cut it at a newline.

    Args:
        executable: The `claude` command.
        schema_name: Shipped schema the answer must match.
        model: Optional model alias.
        has_schema_argument: Whether to pass the schema as `--json-schema`.

    Returns:
        The argument list.
    """
    command = [
        executable,
        "-p",
        "--output-format",
        "json",
        "--allowedTools",
        *READ_ONLY_TOOLS,
        "--permission-mode",
        "dontAsk",
    ]
    if has_schema_argument:
        command += ["--json-schema", json.dumps(schema_for_claude(schema_name))]
    return [*command, "--model", model] if model else command


def add_schema_to_prompt(prompt: str, schema_name: str) -> str:
    """Append the answer schema to a prompt, for runs that cannot take `--json-schema`.

    Args:
        prompt: The prompt.
        schema_name: Shipped schema the answer must match.

    Returns:
        The prompt followed by the schema.
    """
    schema = json.dumps(schema_for_claude(schema_name), indent=1)
    return (
        f"{prompt}\n\nAnswer with only a JSON object that matches this JSON schema:\n"
        f"```json\n{schema}\n```"
    )


@dataclass(frozen=True)
class ClaudeCall:
    """One headless Claude Code question.

    Attributes:
        prompt: The prompt.
        schema_name: Shipped schema the answer must match.
        model: Optional model alias passed to `--model`.
    """

    prompt: str
    schema_name: str
    model: str = ""


def prepare_claude_run(path: str, call: ClaudeCall) -> tuple[list[str], str]:
    """Build the command and standard input for one call to a resolved `claude`.

    Args:
        path: Full path of the `claude` executable.
        call: The question.

    Returns:
        The argument list and the text for standard input.
    """
    # npm installs Claude Code on Windows as a .cmd shim, and cmd.exe re-parses its
    # arguments, breaking the quotes and carets of a JSON schema. The answer is checked
    # against the schema afterwards anyway, so the shim gets it inside the prompt.
    is_shell_script = Path(path).suffix.lower() in SHELL_SCRIPT_SUFFIXES
    command = build_claude_command(path, call.schema_name, call.model, not is_shell_script)
    prompt = add_schema_to_prompt(call.prompt, call.schema_name) if is_shell_script else call.prompt
    return command, prompt


def run_claude(
    repository: Path, executable: str, call: ClaudeCall, timeout_seconds: int, what: str
) -> object:
    """Run headless Claude Code and return its structured answer.

    Args:
        repository: Folder Claude Code reads from.
        executable: The `claude` command.
        call: The question.
        timeout_seconds: Longest the run may take.
        what: What is being done, for messages (such as a route).

    Returns:
        The parsed answer, not yet checked against its schema.

    Raises:
        AnalysisError: If Claude Code is missing, times out or fails.
    """
    # Windows starts only .exe files by bare name, so run the file PATH resolves to.
    path = shutil.which(executable)
    if path is None:
        raise AnalysisError(
            f"Claude Code (`{executable}`) is not on PATH; install it or use --analyzer file"
        )
    command, prompt = prepare_claude_run(path, call)
    logger.info("asking Claude Code: %s (prompt %d characters)", what, len(prompt))
    logger.debug(
        "claude command: %s (schema %s)",
        path,
        "as --json-schema" if "--json-schema" in command else "in the prompt",
    )
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            input=prompt,
            cwd=repository,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        logger.warning("Claude Code timed out on %s after %.2fs", what, time.monotonic() - started)
        raise AnalysisError(f"Claude Code took longer than {timeout_seconds}s on {what}") from error
    except OSError as error:
        logger.warning(
            "Claude Code could not start on %s after %.2fs", what, time.monotonic() - started
        )
        raise AnalysisError(f"could not start Claude Code ({path}): {error}") from error
    elapsed = time.monotonic() - started
    logger.debug(
        "claude exit code %d after %.2fs; stderr: %s",
        result.returncode,
        elapsed,
        result.stderr.strip()[-2000:],
    )
    if result.returncode != 0:
        detail = describe_claude_failure(result.stdout, result.stderr)
        raise AnalysisError(f"Claude Code failed on {what}: {detail}")
    logger.info("Claude Code finished %s in %.2fs", what, elapsed)
    return parse_claude_output(result.stdout)


def describe_claude_failure(stdout: str, stderr: str) -> str:
    """Say in one sentence why headless Claude Code failed.

    With `--output-format json` the reason is the `result` of the JSON it prints, not
    its error stream, which is often empty.

    Args:
        stdout: The command's standard output.
        stderr: The command's error output.

    Returns:
        The reason, with a hint when it is a known one.
    """
    reason = stderr.strip()
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        envelope = None
    if isinstance(envelope, dict) and isinstance(envelope.get("result"), str):
        reason = envelope["result"].strip() or reason
    reason = (reason or stdout.strip() or "no output")[:300]
    lowered = reason.lower()
    if any(word in lowered for word in ("authenticate", "oauth", "log in", "login")):
        return f"{reason} (Claude Code is not signed in: run `claude` once and sign in)"
    return reason


# What an AI says when it will not answer until its own limit resets. "session limit" is
# the wording a real run hit; the rest are the other phrasings seen for the same thing.
_LIMIT_WORDS = (
    "session limit",
    "usage limit",
    "rate limit",
    "quota",
    "credit",
    "too many requests",
)


def is_limit_reached(reason: str) -> bool:
    """Tell whether a failure is the AI's own limit rather than a problem with the code.

    A limit resets on its own, so the answer is to wait and run again. Treating it as a
    failed analysis sends the agent off to read the code and write the analysis by hand,
    which costs far more of the same limit.

    Args:
        reason: The failure as the AI reported it.

    Returns:
        True when the run should wait rather than do the work another way.
    """
    return any(word in reason.lower() for word in _LIMIT_WORDS)


@dataclass(frozen=True)
class ClaudeCodeAnalyzer:
    """Batch analysis through headless Claude Code with read-only tools.

    Attributes:
        repository: Where Claude Code runs (it reads files relative to this folder).
        executable: The `claude` command.
        model: Optional model alias passed to `--model`.
        timeout_seconds: Longest a single route may take.
    """

    repository: Path
    executable: str = CLAUDE_EXECUTABLE
    model: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def analyze(self, request: AnalysisRequest) -> AnalysisDocument:
        """Run Claude Code on one route.

        Args:
            request: The route and what is known about it.

        Returns:
            The validated page-analysis document.

        Raises:
            AnalysisError: If Claude Code is missing, fails or answers off-schema.
        """
        call = ClaudeCall(build_analysis_prompt(request), "page-analysis", self.model)
        answer = run_claude(
            self.repository, self.executable, call, self.timeout_seconds, request.route
        )
        return check_analysis(answer, f"Claude Code ({request.route})")


def list_routes_with_claude(
    repository: Path,
    prompt: str,
    executable: str = CLAUDE_EXECUTABLE,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Ask Claude Code to list the app's routes from a map of the code graph.

    Args:
        repository: The repository root.
        prompt: The route-listing prompt.
        executable: The `claude` command.
        timeout_seconds: Longest the run may take.

    Returns:
        Route entries (`route`, `entry_files`, `title`).

    Raises:
        AnalysisError: If Claude Code fails or answers off-schema.
    """
    call = ClaudeCall(prompt, "route-listing")
    answer = run_claude(repository, executable, call, timeout_seconds, "list routes")
    problems = find_schema_problems(answer, "route-listing")
    if problems or not isinstance(answer, dict):
        raise AnalysisError(
            "Claude Code's route list does not match the schema: " + "; ".join(problems[:3])
        )
    routes: list[dict[str, Any]] = answer["routes"]
    return routes


@dataclass(frozen=True)
class FileAnalyzer:
    """Reads `analysis.json` that Claude Code wrote itself (interactive `/skillgen`).

    Attributes:
        pages_folder: The workspace's `pages/` folder.
    """

    pages_folder: Path

    def analyze(self, request: AnalysisRequest) -> AnalysisDocument:
        """Read the analysis written for one route.

        Args:
            request: The route; its skill name locates the file.

        Returns:
            The validated document.

        Raises:
            AnalysisError: If the file is missing, unreadable or off-schema.
        """
        path = self.pages_folder / request.skill / "analysis.json"
        return check_analysis(read_analysis_file(path), str(path))


@dataclass(frozen=True)
class ReplayAnalyzer:
    """Reads recorded analyses named `<route-slug>.json` (tests and fixtures).

    Attributes:
        folder: Folder of recorded analyses.
    """

    folder: Path

    def analyze(self, request: AnalysisRequest) -> AnalysisDocument:
        """Return the recorded analysis for a route.

        Args:
            request: The route.

        Returns:
            The validated document.

        Raises:
            AnalysisError: If no recording exists or it is off-schema.
        """
        path = self.folder / f"{slugify_route(request.route)}.json"
        return check_analysis(read_analysis_file(path), str(path))


def read_analysis_file(path: Path) -> object:
    """Read an analysis file.

    Args:
        path: The file.

    Returns:
        The parsed JSON.

    Raises:
        AnalysisError: If the file is missing or not JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AnalysisError(
            f"no analysis at {path}; run the analysis step for this route first"
        ) from error
    except json.JSONDecodeError as error:
        raise AnalysisError(f"{path} is not valid JSON: {error}") from error
