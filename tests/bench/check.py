"""Run bench test cases by hand in Claude or Cowork, and check what was submitted.

Standard library only. Typical round:

    python3 tests/bench/check.py list            # every case
    python3 tests/bench/check.py prompt 03       # print a prompt to paste into Claude
    python3 tests/bench/check.py reset           # forget earlier submissions
    ... paste the prompt in Claude or Cowork, answer any follow-up ...
    python3 tests/bench/check.py check 03        # PASS or FAIL with the differences

Other commands:
    python3 tests/bench/check.py zip             # tests/bench/dist/bench-apply.zip for upload
    python3 tests/bench/check.py install         # copy the skill to ~/.claude/skills/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
SKILL_NAME = "bench-apply"
SKILL_DIR = BENCH / "skills" / SKILL_NAME
DEFAULT_URL = "http://localhost:8765"


def load_cases() -> list[dict[str, object]]:
    data = json.loads((BENCH / "cases.json").read_text(encoding="utf-8"))
    return list(data["cases"])


def find_case(cases: list[dict[str, object]], wanted: str) -> dict[str, object]:
    matches = [
        case for case in cases if str(case["id"]) == wanted or str(case["id"]).startswith(wanted)
    ]
    if len(matches) != 1:
        names = ", ".join(str(case["id"]) for case in cases)
        raise SystemExit(f"no single case matches {wanted!r}; cases: {names}")
    return matches[0]


def request_json(url: str, method: str = "GET") -> object:
    request = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.URLError as error:
        raise SystemExit(
            f"cannot reach the bench at {url}: {error}. Is serve.py running?"
        ) from error


def compare(expected: object, actual: object, path: str = "") -> list[str]:
    """List differences, treating expected objects as subsets of actual ones."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or 'submission'}: expected an object, got {actual!r}"]
        problems = []
        for key, value in expected.items():
            if key not in actual:
                problems.append(f"{path}{key}: missing")
            else:
                problems += compare(value, actual[key], f"{path}{key}.")
        return problems
    if expected != actual:
        return [f"{path.rstrip('.')}: expected {expected!r}, got {actual!r}"]
    return []


def check_case(case: dict[str, object], base_url: str) -> list[str]:
    expect = case["expect"]
    assert isinstance(expect, dict)
    submissions = request_json(f"{base_url}/api/submissions")
    assert isinstance(submissions, list)
    if expect["outcome"] == "not-submitted":
        return [f"expected no submission, found {len(submissions)}"] if submissions else []
    if not submissions:
        return ["expected a submission, found none (did Claude submit? did you reset first?)"]
    last = submissions[-1]
    assert isinstance(last, dict)
    return compare(expect.get("submission", {}), last["received"])


def print_case(case: dict[str, object]) -> None:
    expect = case["expect"]
    assert isinstance(expect, dict)
    print(f"# {case['id']} — {case['title']}\n")
    print("Prompt to paste:\n")
    print(case["prompt"])
    if case.get("follow_up"):
        print(f"\nWhen Claude asks, answer:\n\n{case['follow_up']}")
    if case.get("attach"):
        print(f"\nAttach this file to the message: {case['attach']}")
    print("\nClaude should:")
    for line in expect.get("claude_should", []):
        print(f"  - {line}")
    print("Claude should not:")
    for line in expect.get("claude_should_not", []):
        print(f"  - {line}")


def make_zip() -> Path:
    target = BENCH / "dist" / f"{SKILL_NAME}.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path(SKILL_NAME) / path.relative_to(SKILL_DIR))
    return target


def install_skill() -> Path:
    target = Path.home() / ".claude" / "skills" / SKILL_NAME
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SKILL_DIR, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["list", "prompt", "reset", "check", "zip", "install"])
    parser.add_argument("case", nargs="?", help="case id or its number prefix, such as 03")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"bench address (default {DEFAULT_URL})")
    arguments = parser.parse_args()
    cases = load_cases()
    if arguments.command == "list":
        for case in cases:
            flag = "  (manual)" if case.get("manual") else ""
            print(f"{case['id']:<28} {case['title']}{flag}")
    elif arguments.command == "prompt":
        print_case(find_case(cases, arguments.case or ""))
    elif arguments.command == "reset":
        request_json(f"{arguments.url}/api/reset", "POST")
        print("bench reset: no submissions")
    elif arguments.command == "check":
        case = find_case(cases, arguments.case or "")
        problems = check_case(case, arguments.url)
        print(f"{'PASS' if not problems else 'FAIL'}  {case['id']}")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "Also judge by hand: did Claude follow 'should' and avoid 'should not'? "
            "(the prompt command shows both)"
        )
        return 1 if problems else 0
    elif arguments.command == "zip":
        print(f"wrote {make_zip()}")
    else:
        print(f"installed {install_skill()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
