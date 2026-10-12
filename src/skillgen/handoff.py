"""What whoever runs skillgen does next when a run stops short of a finished skill.

skillgen never asks on its own: it runs inside an AI agent. When a run needs the
agent's work (reading the code) or the developer's (an address, a sign-in, a download,
a yes), it says so as data, with the question to ask and the commands to run after.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from skillgen import TOOL_NAME

URL_PLACEHOLDER = "<url>"
LABEL_PLACEHOLDER = "<label>"
OVERWRITE = "overwrite"
# Backslashes and angle brackets mean something to a shell, so they are quoted.
_PLAIN_ARGUMENT = re.compile(r"[\w@%+=:,./-]+")


@dataclass(frozen=True)
class NextStep:
    """One thing to do before a run can finish.

    Attributes:
        action: `analyse` (the agent reads the code itself) or `ask` (the developer
            decides or acts).
        need: What is missing: `analysis`, `url`, `probe`, `chromium`, `server`, `login`,
            `open` or `overwrite`.
        reason: Why the run stopped, in one sentence.
        ask: The question for the developer; empty for `analyse`.
        run: The command to run after a yes; empty when the developer acts themselves.
        then: The command that continues the work.
        prompt: For `analyse`: the prompt to follow.
        write: For `analyse`: where to write the page analysis.
    """

    action: str
    need: str
    reason: str
    ask: str = ""
    run: str = ""
    then: str = ""
    prompt: str = ""
    write: str = ""


def format_command(arguments: Sequence[str]) -> str:
    """Write a skillgen command line that bash and PowerShell both read the same way.

    Args:
        arguments: The arguments after the program name.

    Returns:
        The command, with arguments quoted only when they need it.
    """
    return " ".join([TOOL_NAME, *(_quote(argument) for argument in arguments)])


def _quote(argument: str) -> str:
    if _PLAIN_ARGUMENT.fullmatch(argument):
        return argument
    if "'" not in argument:
        return f"'{argument}'"
    return '"' + argument.replace('"', '\\"') + '"'


def with_flag(arguments: Sequence[str], flag: str, value: str | None = None) -> list[str]:
    """Add a flag to a command line unless it is already there.

    Args:
        arguments: The command line.
        flag: The flag, such as `--overwrite`.
        value: The flag's value, if it takes one.

    Returns:
        The command line with the flag.
    """
    if any(argument == flag or argument.startswith(f"{flag}=") for argument in arguments):
        return list(arguments)
    return [*arguments, flag] if value is None else [*arguments, flag, value]


def without_flag(arguments: Sequence[str], flag: str) -> list[str]:
    """Remove a flag that takes a value, every time it appears.

    Args:
        arguments: The command line.
        flag: The flag, such as `--open`.

    Returns:
        The command line without it.
    """
    kept: list[str] = []
    skip = False
    for argument in arguments:
        if skip:
            skip = False
        elif argument == flag:
            skip = True
        elif not argument.startswith(f"{flag}="):
            kept.append(argument)
    return kept


def find_root_arguments(arguments: Sequence[str]) -> list[str]:
    """Return the `--root` part of a command line, to repeat it in other commands.

    Args:
        arguments: The command line.

    Returns:
        `["--root", folder]`, or nothing when the command ran in the project folder.
    """
    for index, argument in enumerate(arguments):
        if argument.startswith("--root="):
            return ["--root", argument.split("=", 1)[1]]
        if argument == "--root" and index + 1 < len(arguments):
            return ["--root", arguments[index + 1]]
    return []


def build_next_step(
    need: str,
    detail: str,
    command_line: Sequence[str],
    *,
    has_written: bool = False,
    prompt: str = "",
    write: str = "",
) -> NextStep:
    """Say what to do next for one need, and how to continue afterwards.

    Args:
        need: What is missing (see `NextStep.need`).
        detail: The error, URL or skill name the need is about.
        command_line: The arguments of the command that stopped.
        has_written: True when the run still wrote the skill, so continuing recreates it.
        prompt: For `analysis`: the prompt file.
        write: For `analysis`: where the page analysis goes.

    Returns:
        The next step.
    """
    then = with_flag(command_line, "--overwrite") if has_written else list(command_line)
    if need == "analysis":
        return NextStep(
            "analyse", need, detail, then=format_command(then), prompt=prompt, write=write
        )
    if need == "url":
        then = with_flag(then, "--url", URL_PLACEHOLDER)
    if need == OVERWRITE:
        then = with_flag(then, "--overwrite")
    if need == "open":
        then = [*without_flag(then, "--open"), "--open", f"text:{LABEL_PLACEHOLDER}"]
    reason, ask, run = _describe_need(need, detail, find_root_arguments(command_line))
    return NextStep("ask", need, reason, ask, run, format_command(then))


def _describe_need(need: str, detail: str, root: list[str]) -> tuple[str, str, str]:
    """(reason, question for the developer, command to run after a yes) for one need."""
    if need == "limit":
        return (
            detail,
            f"{detail} This resets on its own: wait until then and run the same command "
            "again. Nothing is lost, and any analysis already done is reused. Do not "
            "write the analysis by hand instead; that spends much more of the same limit.",
            "",
        )
    if need == "url":
        return (
            "--xy measures the page on a running dev copy, and no address is set",
            "x/y is measured on a running dev copy of the app. What is its address, "
            "for example http://localhost:3000?",
            "",
        )
    if need == "probe":
        return (
            f"--xy needs {TOOL_NAME}'s browser part (the probe extra), which is not installed",
            f"x/y needs {TOOL_NAME}'s browser part. Reinstall {TOOL_NAME} with the probe "
            "extra as its README shows, then say when it is done.",
            "",
        )
    if need == "chromium":
        return (
            "Chromium is not downloaded yet",
            "x/y needs Chromium, a one-time download of about 150 MB. Download it now?",
            format_command(["doctor", "--fix"]),
        )
    if need == "server":
        return (
            f"nothing answers at {detail}",
            f"Nothing answers at {detail}. Start your dev server, then say when it is up.",
            "",
        )
    if need == "open":
        return (
            f"no field was on screen at {detail}, so the form opens with a click",
            f"On {detail} the form's fields are hidden until something is clicked. Which "
            "button, tab or link shows them? Give its text as it appears on the page.",
            "",
        )
    if need == "login":
        return (
            f"{detail} showed a sign-in page instead of the form",
            f"{detail} asks you to sign in before x/y can be measured. Open a browser "
            "window so you can sign in now? Sign in, then close the window.",
            format_command(["login", "--url", detail, *root]),
        )
    return (
        f"{detail} already exists",
        f"The skill {detail} already exists. Recreate it and replace it? Notes in its "
        "user section are kept.",
        "",
    )
