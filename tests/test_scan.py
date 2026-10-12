import pytest

from skillgen.assets import read_fill_engine
from skillgen.generate.folder import build_skill_files
from skillgen.validate.scan import scan_files, scan_line
from tests.helpers import load_bench_page

# Assembled at run time so the repository itself never contains a real-looking secret.
FAKE_GITHUB = "ghp_" + "a1B2" * 9
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        (f"token = {FAKE_GITHUB}", "GitHub token"),
        (f"key {FAKE_AWS}", "AWS access key"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private key"),
        ("contact jane.doe@realcompany.io", "email address"),
        ("call +44 20 7946 1234", "phone number"),
        ("password = 'hunter2hunter2'", "password assignment"),
        ("see src/pages/Signup.tsx for details", "source path"),
    ],
)
def test_scan_line_finds_secrets_and_personal_data(line, kind):
    assert kind in [found for found, _ in scan_line(line)]


@pytest.mark.parametrize(
    "line",
    [
        "write to alex@example.com",
        "call 555-0100",
        "date 1990-01-15",
        "range 1–10 · 11–50",
        "http://localhost:8765/apply",
    ],
)
def test_scan_line_allows_synthetic_values(line):
    assert scan_line(line) == []


def test_scan_line_masks_excerpt():
    ((_, excerpt),) = scan_line(f"t {FAKE_GITHUB}")
    assert FAKE_GITHUB not in excerpt


def test_scan_files_passes_generated_bench_skill():
    assert scan_files(build_skill_files(load_bench_page(), read_fill_engine())) == []


def test_scan_files_reports_path_and_line():
    findings = scan_files({"a.md": "ok\nmail bob@corp.io\n"})
    assert [(f.path, f.line, f.kind) for f in findings] == [("a.md", 2, "email address")]
