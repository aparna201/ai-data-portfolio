"""Reminder cycle (workflow V1) as a plain Python program.

For every corporate-paid bill in the sheet: classify it (Agent 1), email the corporate accounts
team with a tone that matches how overdue it is (Agent 2), and alert the Patient Accounts Manager
when it is 60+ days overdue (Agent 3). Dry run by default: drafts go to `outbox/`, nothing is
sent and the sheet is not changed.

Agents 2 and 3 are Gemini calls in n8n. Here they are templates so the demo runs offline; pass
`writer` to plug in an LLM. Patient details sent to any LLM are limited to name, bill number,
amount and dates. Department and diagnosis never leave this file.
"""
from __future__ import annotations

import csv
import os
import re
import smtplib
from dataclasses import dataclass, field
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from .aging import Decision, classify

TONE_LINES = {
    "gentle": "This is a courteous reminder, as it may have been overlooked.",
    "firm": "Our records show this bill is now overdue, and we would be grateful for your help in settling it.",
    "urgent": "Please arrange payment, or call us, within 2 working days.",
    "final_notice": "This is our last reminder before the account is referred to our Patient Accounts Manager.",
}
MANAGER_ACTIONS = {
    "final_notice": "Phone the corporate accounts contact and confirm a payment date.",
    "escalate": "Phone the patient or corporate contact today and offer an instalment plan if needed.",
}


@dataclass
class Message:
    to: str
    subject: str
    body: str
    kind: str          # "reminder" or "manager_alert"
    invoice_no: str


@dataclass
class RunResult:
    reminders: list[Message] = field(default_factory=list)
    alerts: list[Message] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)      # invoice_no -> reason


def _inr(x: float) -> str:
    """Indian digit grouping: 1,25,000."""
    s = f"{int(round(x))}"
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return f"{head},{tail}" if head else tail


def draft_reminder(row: dict, d: Decision, manager_email: str, writer: Callable[[str], str] | None) -> Message:
    inv = row["invoice_no"]
    body = "\n".join([
        f"Dear Accounts Team,", "",
        f"Bill {inv} for patient {row['patient_name']} (INR {_inr(float(row['invoice_amount']))}) "
        f"is {d.days_overdue} days overdue.", "",
        TONE_LINES[d.tone_grade],
        "We are happy to help with payment options, instalments or any query on this bill. "
        f"Please write to {manager_email}.", "",
        "Regards,", "Patient Accounts Team, the hospital (demo)"])
    return Message(row["payer_email"], f"Payment reminder: Bill {inv}", writer(body) if writer else body,
                   "reminder", inv)


def draft_alert(row: dict, d: Decision, manager_email: str) -> Message:
    inv = row["invoice_no"]
    action = MANAGER_ACTIONS["escalate" if d.tone_grade == "escalate" else "final_notice"]
    body = "\n".join([
        f"Patient: {row['patient_name']}, contact {row['patient_contact_no']}",
        f"System sent: {row.get('reminder_count') or 0} reminders",
        f"Recommended action: {action}",
        "Suggested call opener: Good morning, we are calling about your hospital bill and "
        "would like to help find an easy way to settle it."])
    return Message(manager_email, f"[ESCALATE] {inv} INR {_inr(float(row['invoice_amount']))} "
                   f"{d.days_overdue} days overdue", body, "manager_alert", inv)


def _send(m: Message) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ["MAIL_FROM"], m.to, m.subject
    msg.set_content(m.body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)


def _read(path: str | Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames), list(r)


def run(bills_path: str | Path, as_of: date, outbox: str | Path = "outbox", send: bool = False,
        manager_email: str = "accounts-manager@example.com",
        writer: Callable[[str], str] | None = None) -> RunResult:
    fields, rows = _read(bills_path)
    result = RunResult()
    for row in rows:
        inv = row["invoice_no"]
        if row["payer_type"] != "corporate":
            result.skipped[inv] = "out of scope: not corporate-paid"
            continue
        d = classify(row, as_of)
        # Draft from the row as read, like n8n does: counts and dates update only afterwards.
        reminder = draft_reminder(row, d, manager_email, writer) if d.should_remind else None
        alert = draft_alert(row, d, manager_email) if d.escalate_now else None
        if reminder:
            result.reminders.append(reminder)
            row["last_reminded_at"] = as_of.isoformat()
            row["reminder_count"] = str(int(row.get("reminder_count") or 0) + 1)
        elif d.cooldown_reason:
            result.skipped[inv] = d.cooldown_reason
        if alert:
            result.alerts.append(alert)
            row["last_escalated_at"] = as_of.isoformat()

    out = list(result.reminders) + list(result.alerts)
    if send:
        for m in out:
            _send(m)
        with open(bills_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    else:
        box = Path(outbox)
        box.mkdir(parents=True, exist_ok=True)
        for m in out:
            (box / f"{m.kind}_{m.invoice_no}.txt").write_text(f"To: {m.to}\nSubject: {m.subject}\n\n{m.body}\n")
    return result
