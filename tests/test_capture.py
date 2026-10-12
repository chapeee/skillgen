"""The probe: pure classification here, and a real probe of the bench page (-m browser)."""

from __future__ import annotations

import json

from skillgen.probe.capture import probed_page_from_dict, probed_page_to_dict
from tests.helpers import BENCH

BENCH_URL = "http://localhost:8765/apply"


def test_bench_probe_capture_round_trips():
    data = json.loads((BENCH / "probe.json").read_text(encoding="utf-8"))
    assert probed_page_to_dict(probed_page_from_dict(data)) == data
