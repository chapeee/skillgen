"""Secret and personal-data scan for anything that leaves the developer's machine.

Flags tokens, keys, private keys, real-looking email addresses, phone numbers and
source paths. Reserved example domains and 555-01xx numbers are allowed, because
generated examples use them on purpose.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

# Domains reserved for documentation (RFC 2606, RFC 6761) and local hosts.
SAFE_EMAIL_DOMAINS = re.compile(
    r"@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|example|test|invalid|localhost)$", re.IGNORECASE
)
# Fictional numbers: 555-0100 to 555-0199.
SAFE_PHONE = re.compile(r"555[-.\s]?01\d\d")

_PATTERNS: dict[str, re.Pattern[str]] = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "Anthropic or OpenAI key": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "JSON web token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    ),
    "bearer token": re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._~+/-]{20,}=*"),
    "password assignment": re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]{6,}['\"]"
    ),
    "source path": re.compile(
        r"(?:^|[\s(`'\"])(?:src|app|lib|resources)/[\w./-]+\.(?:py|tsx?|jsx?|vue|php|rb|svelte|go|java|cs)\b"
    ),
}
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{8,}\d(?![\w-])")


@dataclass(frozen=True)
class Finding:
    """One suspicious match.

    Attributes:
        path: The file it was found in.
        line: The 1-based line number.
        kind: What it looks like, such as "GitHub token".
        excerpt: The match, shortened so the report does not repeat a secret.
    """

    path: str
    line: int
    kind: str
    excerpt: str


def _mask(text: str) -> str:
    """Show only the start of a match so reports never contain the full secret."""
    return text[:6] + "…" if len(text) > 8 else text


def _is_phone_like(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    # Dates, versions and ranges also match the loose pattern; real numbers have 9+ digits
    # and no ISO-date shape. A run of one repeated digit (e.g. "0000000000") is a
    # validation-rule constant or placeholder mask, never a real phone number.
    if (
        len(digits) < 9
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text.strip())
        or len(set(digits)) == 1
    ):
        return False
    return not SAFE_PHONE.search(text)


def scan_line(line: str) -> list[tuple[str, str]]:
    """Find secrets and personal data in one line.

    Args:
        line: The text.

    Returns:
        (kind, excerpt) pairs.
    """
    hits = [
        (kind, _mask(m.group(0).strip()))
        for kind, pattern in _PATTERNS.items()
        for m in pattern.finditer(line)
    ]
    hits += [
        ("email address", _mask(m.group(0)))
        for m in _EMAIL.finditer(line)
        if not SAFE_EMAIL_DOMAINS.search(m.group(0))
    ]
    hits += [
        ("phone number", _mask(m.group(0)))
        for m in _PHONE.finditer(line)
        if _is_phone_like(m.group(0))
    ]
    return hits


def scan_files(files: Mapping[str, str]) -> list[Finding]:
    """Scan file contents for secrets and personal data.

    Args:
        files: Text by path.

    Returns:
        Every finding, in path and line order.
    """
    findings = []
    for path in sorted(files):
        for number, line in enumerate(files[path].splitlines(), start=1):
            findings += [Finding(path, number, kind, excerpt) for kind, excerpt in scan_line(line)]
    return findings
