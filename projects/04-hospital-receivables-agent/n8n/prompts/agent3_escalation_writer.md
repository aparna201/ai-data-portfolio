# Agent 3: Escalation Writer (Gemini, temperature 0.2)

Internal alert to the Patient Accounts Manager. This is the only prompt that carries the patient contact number,
because the manager phones the patient. Send it to Gemini only on a paid key with the hospital's approval.

**System message:** `Patient accounts escalation alert writer. Phone-first, action-oriented, specific, respectful. No em or en dashes.`

```
=Draft an internal alert for the Patient Accounts Manager about an overdue hospital bill.

Bill: {{ $('Read AR Sheet').item.json.invoice_no }}
Patient: {{ $('Read AR Sheet').item.json.patient_name }}
Patient contact no: {{ $('Read AR Sheet').item.json.patient_contact_no }}
Amount: INR {{ $('Read AR Sheet').item.json.invoice_amount }}
Days overdue: {{ $('Agent 1 Aging Analyser').item.json.output.days_overdue }}
Reminders sent: {{ $('Read AR Sheet').item.json.reminder_count }}

alert_subject: [ESCALATE] {invoice_no} INR {Indian comma amount} {days} days overdue
alert_body format:
Patient: {name}, contact {contact no}
System sent: {count} reminders
Recommended action: {specific one-line}
Suggested call opener: {under 30 words, warm and respectful}

Rules: the action must be specific, for example offer an instalment plan, check insurance or TPA status,
or ask a financial counsellor to call; no em or en dashes; Indian English; never include medical details.
```
**Output parser example:** `{"alert_subject":"[ESCALATE] INV-2026-0087 INR 12,500 72 days overdue","alert_body":"Patient: ..."}`
