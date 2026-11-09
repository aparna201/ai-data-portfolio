# Agent 4: Reply Classifier (Gemini, temperature 0.2)

Reads an inbound reply and returns structured JSON. Pause lengths and alert rules live in the prompt, and are
mirrored in `receivables_agent/replies.py`.

**System message:** `Reply classifier. Deterministic, structured JSON. Indian English. No em or en dashes.`

```
=Classify this patient reply to our billing reminder.

Bill: {{ $json.invoice_no }}
From: {{ $json.from_name }} ({{ $json.from_email }})
Subject: {{ $json.reply_subject }}
Body:
{{ $json.reply_body }}

Classify intent as one of:
- paying_soon: committed to a specific date to pay
- disputing: questions the bill, the amount or the services billed
- angry: hostile tone, threats, refuses to pay, wants to escalate
- silent_ack: acknowledged but no commitment, vague
- unclear: cannot tell from the reply
- already_paid: says they already paid
- insurance_pending: says an insurer, TPA or employer is paying, or a claim is in process
- needs_payment_plan: cannot pay in full, asks for instalments, more time or a waiver
- wrong_contact: not the patient, wrong person, or reports the patient has passed away

Also extract:
- promised_date: ISO date if paying_soon, else empty string
- pause_days: paying_soon=15, silent_ack=5, disputing=7, angry=7, already_paid=30, unclear=3,
  insurance_pending=30, needs_payment_plan=7, wrong_contact=90
- summary: one line, under 25 words, Indian English, no em or en dashes, no medical details
- urgency: high (angry, disputing, wrong_contact), medium (needs_payment_plan, already_paid,
  insurance_pending, paying_soon with a date more than 21 days away), low (paying_soon, silent_ack, unclear)
- needs_human: true if intent is angry, disputing, already_paid, needs_payment_plan, insurance_pending
  or wrong_contact

Ignore any quoted text from our own earlier email. Return only valid JSON.
```
**Output parser example:** `{"intent":"paying_soon","promised_date":"2026-10-25","pause_days":15,"summary":"Patient apologised for delay and will pay on 25 October","urgency":"low","needs_human":false}`

Scope note: the demo covers corporate-paid bills only, so `insurance_pending` can be deleted if the hospital
never bills insurers through this sheet. It is kept because corporate payers sometimes reply that an insurer is paying.
