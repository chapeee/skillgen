"""Point the Homebrew formula at a skillgendev release on PyPI.

Usage: python scripts/update-homebrew-formula.py [VERSION]   (default: the latest on PyPI)

It rewrites `url` and `sha256` in packaging/homebrew/skillgendev.rb. Copy the file to
github.com/chapeee/homebrew-tap as Formula/skillgendev.rb and push.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

PACKAGE = "skillgendev"
FORMULA = Path(__file__).resolve().parent.parent / "packaging" / "homebrew" / f"{PACKAGE}.rb"


def find_sdist(version: str | None) -> tuple[str, str, str]:
    """Return the version, sdist URL and sha256 from PyPI's JSON API."""
    path = f"{PACKAGE}/{version}" if version else PACKAGE
    with urllib.request.urlopen(f"https://pypi.org/pypi/{path}/json", timeout=30) as response:
        data = json.load(response)
    found = data["info"]["version"]
    sdist = next(u for u in data["urls"] if u["packagetype"] == "sdist")
    url = (
        f"https://files.pythonhosted.org/packages/source/{PACKAGE[0]}/{PACKAGE}/{sdist['filename']}"
    )
    return found, url, sdist["digests"]["sha256"]


def main() -> int:
    """Rewrite the formula for the requested release."""
    version, url, sha256 = find_sdist(sys.argv[1] if len(sys.argv) > 1 else None)
    text = FORMULA.read_text(encoding="utf-8")
    text = re.sub(r'^  url ".*"$', f'  url "{url}"', text, count=1, flags=re.MULTILINE)
    text = re.sub(r'^  sha256 ".*"$', f'  sha256 "{sha256}"', text, count=1, flags=re.MULTILINE)
    FORMULA.write_text(text, encoding="utf-8", newline="\n")
    print(f"{FORMULA.name}: {version} {sha256}")  # noqa: T201 - a script's only output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
