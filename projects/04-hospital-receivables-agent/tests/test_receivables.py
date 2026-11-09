import csv
import shutil
from datetime import date
from pathlib import Path

import pytest

from receivables_agent import agent, apply_reply, classify, classify_keywords, evaluate, run
from receivables_agent.aging import bucket_for

DATA = Path(__file__).parent.parent / "data" / "bills.csv"
AS_OF = date(2026, 11, 8)


def rows():
    with open(DATA, newline="") as f:
        return {r["invoice_no"]: r for r in csv.DictReader(f)}


@pytest.mark.parametrize("days,bucket,tone,gap", [
    (-1, "not_due", "none", None), (0, "0-15", "gentle", 7), (15, "0-15", "gentle", 7),
    (16, "16-30", "firm", 5), (30, "16-30", "firm", 5), (31, "31-60", "urgent", 3),
    (60, "31-60", "urgent", 3), (61, "61-90", "final_notice", 7), (90, "61-90", "final_notice", 7),
    (91, "90+", "escalate", None)])
def test_bucket_boundaries(days, bucket, tone, gap):
    assert bucket_for(days) == (bucket, tone, gap)


EXPECTED = {   # invoice -> (should_remind, escalate_now, why skipped)
    "INV-2026-1001": (False, False, "not yet due"),
    "INV-2026-1002": (True, False, ""),
    "INV-2026-1003": (True, False, ""),
    "INV-2026-1004": (False, False, "cooldown active"),
    "INV-2026-1005": (True, True, ""),
    "INV-2026-1006": (False, True, "over 90 days: staff handle directly"),
    "INV-2026-1007": (True, False, ""),                         # escalated 3 days ago: no second alert
    "INV-2026-1008": (False, False, "paused until 2026-11-20 (patient replied)"),
    "INV-2026-1009": (False, False, "status is paid_claimed"),
    "INV-2026-1010": (False, False, "missing or invalid due_date"),
}


@pytest.mark.parametrize("inv", EXPECTED)
def test_each_case_in_the_test_plan(inv):
    d = classify(rows()[inv], AS_OF)
    assert (d.should_remind, d.escalate_now, d.cooldown_reason) == EXPECTED[inv]


def test_run_scope_and_counts(tmp_path):
    r = run(DATA, AS_OF, outbox=tmp_path)
    assert sorted(m.invoice_no for m in r.reminders) == ["INV-2026-1002", "INV-2026-1003", "INV-2026-1005", "INV-2026-1007"]
    assert sorted(m.invoice_no for m in r.alerts) == ["INV-2026-1005", "INV-2026-1006"]
    assert r.skipped["INV-2026-1011"].startswith("out of scope")      # insurance bill is not chased
    assert len(list(tmp_path.glob("*.txt"))) == 6


def test_dry_run_leaves_sheet_untouched(tmp_path):
    bills = tmp_path / "bills.csv"
    shutil.copy(DATA, bills)
    before = bills.read_text()
    run(bills, AS_OF, outbox=tmp_path / "o")
    assert bills.read_text() == before


def test_emails_never_contain_department_or_contact_and_keep_bill_number(tmp_path):
    r = run(DATA, AS_OF, outbox=tmp_path)
    for m in r.reminders:
        assert m.invoice_no in m.subject                 # V2 matches replies on this
        assert "Dept" not in m.body and "90000" not in m.body
    assert all("90000" in m.body for m in r.alerts)       # staff alert does carry the phone number


def test_send_updates_sheet_and_second_run_is_quiet(tmp_path, monkeypatch):
    bills = tmp_path / "bills.csv"
    shutil.copy(DATA, bills)
    sent = []
    monkeypatch.setattr(agent, "_send", sent.append)
    run(bills, AS_OF, send=True)
    assert len(sent) == 6
    again = run(bills, AS_OF, outbox=tmp_path / "o")
    assert again.reminders == [] and again.alerts == []   # cooldowns now apply
    later = run(bills, date(2026, 11, 15), outbox=tmp_path / "o")
    assert {m.invoice_no for m in later.alerts} == {"INV-2026-1005", "INV-2026-1006", "INV-2026-1007"}


def test_reminder_count_is_numeric_after_update(tmp_path, monkeypatch):
    bills = tmp_path / "bills.csv"
    shutil.copy(DATA, bills)
    monkeypatch.setattr(agent, "_send", lambda m: None)
    run(bills, AS_OF, send=True)
    assert {r["invoice_no"]: r["reminder_count"] for r in csv.DictReader(open(bills))}["INV-2026-1003"] == "2"


def test_indian_comma_format():
    assert agent._inr(125000) == "1,25,000" and agent._inr(12500) == "12,500" and agent._inr(950) == "950"


def test_reply_pauses_and_paid_claim_is_not_paid():
    row = rows()["INV-2026-1003"]
    assert apply_reply(row, "paying_soon", AS_OF)["paused_until"] == "2026-11-23"
    claimed = apply_reply(row, "already_paid", AS_OF)
    assert claimed["status"] == "paid_claimed" and classify(claimed, AS_OF).should_remind is False
    assert apply_reply(row, "angry", AS_OF)["paused_until"] == "2026-11-15"   # reference build paused 0 days


def test_paused_bill_resumes_after_window():
    row = apply_reply(rows()["INV-2026-1003"], "silent_ack", AS_OF)          # paused 5 days
    assert classify(row, date(2026, 11, 12)).should_remind is False
    assert classify(row, date(2026, 11, 13)).should_remind is True


def test_keyword_classifier_basics():
    assert classify_keywords("We already paid this on 12 September") == "already_paid"
    assert classify_keywords("The patient has passed away") == "wrong_contact"
    assert classify_keywords("hmm") == "unclear"


def test_evaluate_reports_metrics():
    out = evaluate([("We already paid", "already_paid"), ("hmm", "angry")])
    assert out["n"] == 2 and out["accuracy"] == 0.5 and len(out["errors"]) == 1
