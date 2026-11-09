"""Agent 1 (aging analyser) in Python.

This is the same rule set as `n8n/agent1_aging_analyser.js`, the Code node used in the n8n
workflow. Keeping both lets the rules be unit-tested here and checked against the JavaScript
(see tests/test_js_parity.py). Dates are exact, so no LLM is used for this step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

CLOSED_STATUSES = {"paid", "paid_claimed", "closed", "waived"}
ESCALATE_FROM_DAYS = 60       # manager alert starts here
ESCALATION_GAP_DAYS = 7       # at most one manager alert per bill per week


@dataclass
class Decision:
    days_overdue: int | None
    aging_bucket: str
    tone_grade: str
    should_remind: bool
    escalate_now: bool
    cooldown_reason: str


def parse_day(text: str | None) -> date | None:
    text = (text or "").strip()
    return datetime.strptime(text[:10], "%Y-%m-%d").date() if text else None


def bucket_for(days: int) -> tuple[str, str, int | None]:
    """(bucket, tone, gap in days between reminders)."""
    if days < 0:
        return "not_due", "none", None
    if days <= 15:
        return "0-15", "gentle", 7
    if days <= 30:
        return "16-30", "firm", 5
    if days <= 60:
        return "31-60", "urgent", 3
    if days <= 90:
        return "61-90", "final_notice", 7
    return "90+", "escalate", None


def classify(row: dict, today: date) -> Decision:
    due = parse_day(row.get("due_date"))
    if due is None:
        return Decision(None, "invalid_date", "none", False, False, "missing or invalid due_date")

    days = (today - due).days
    bucket, tone, gap = bucket_for(days)

    status = (row.get("status") or "").lower()
    closed = status in CLOSED_STATUSES
    paused_until = parse_day(row.get("paused_until"))
    paused = bool(paused_until and today < paused_until)
    last_reminded = parse_day(row.get("last_reminded_at"))
    last_escalated = parse_day(row.get("last_escalated_at"))
    since_reminder = (today - last_reminded).days if last_reminded else None
    since_escalation = (today - last_escalated).days if last_escalated else None

    should, reason = False, ""
    if closed:
        reason = f"status is {status}"
    elif paused:
        reason = f"paused until {paused_until} (patient replied)"
    elif days < 0:
        reason = "not yet due"
    elif tone == "escalate":
        reason = "over 90 days: staff handle directly"
    elif since_reminder is None or since_reminder >= gap:
        should = True
    else:
        reason = "cooldown active"

    escalate = (not closed and not paused and days >= ESCALATE_FROM_DAYS
                and (since_escalation is None or since_escalation >= ESCALATION_GAP_DAYS))
    return Decision(days, bucket, tone, should, escalate, reason)
