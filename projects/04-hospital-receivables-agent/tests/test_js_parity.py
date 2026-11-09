"""The n8n Code node (JavaScript) and the Python rules must give identical decisions."""
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from receivables_agent import classify
from receivables_agent.agent import _read

N8N = Path(__file__).parent.parent / "n8n"
DATA = Path(__file__).parent.parent / "data" / "bills.csv"

pytestmark = pytest.mark.skipif(
    not shutil.which("node") or not (N8N / "node_modules" / "luxon").exists(),
    reason="needs node and `npm install` in projects/04-hospital-receivables-agent/n8n")


@pytest.mark.parametrize("as_of", [date(2026, 11, 8), date(2026, 11, 15), date(2026, 12, 20)])
def test_js_matches_python(as_of):
    js = json.loads(subprocess.run(["node", "run_agent1.js", str(DATA), as_of.isoformat()], cwd=N8N,
                                   capture_output=True, text=True, check=True).stdout)
    _, rows = _read(DATA)
    assert len(js) == len(rows)
    for j, row in zip(js, rows):
        d = classify(row, as_of)
        assert j["days_overdue"] == d.days_overdue, row["invoice_no"]
        assert (j["aging_bucket"], j["tone_grade"]) == (d.aging_bucket, d.tone_grade), row["invoice_no"]
        assert (j["should_remind"], j["escalate_now"]) == (d.should_remind, d.escalate_now), row["invoice_no"]
        assert j["cooldown_reason"] == d.cooldown_reason, row["invoice_no"]
