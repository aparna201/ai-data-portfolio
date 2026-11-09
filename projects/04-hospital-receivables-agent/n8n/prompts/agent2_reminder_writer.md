# Agent 2: Reminder Writer (Gemini, temperature 0.4)

Sends to the corporate payer's accounts team. Gets bill number, patient name, amount, dates and tone only.
Department, diagnosis and phone number are never put in this prompt.

**System message:** `Indian English patient billing email writer. Courteous, tone-graded. No em or en dashes. No medical details.`

**Prompt (n8n expression mode, keep the leading `=`):**
```
=Draft a polite billing reminder email to the accounts team of a corporate that owes a hospital bill.

Corporate payer: {{ $('Read AR Sheet').item.json.payer_org }}, patient: {{ $('Read AR Sheet').item.json.patient_name }}
Bill number: {{ $('Read AR Sheet').item.json.invoice_no }}
Amount due: INR {{ $('Read AR Sheet').item.json.invoice_amount }}
Due date: {{ $('Read AR Sheet').item.json.due_date }}
Days overdue: {{ $('Agent 1 Aging Analyser').item.json.output.days_overdue }}
Tone grade: {{ $('Agent 1 Aging Analyser').item.json.output.tone_grade }}
Sender: Patient Accounts Team, <hospital name>
Billing help: <billing phone> and <billing email>

Tone rules: gentle = courteous reminder, assume it was overlooked; firm = polite and clear that the bill is
overdue; urgent = direct, ask them to pay or call us within 2 working days; final_notice = formal, last
reminder before the account is referred to our Patient Accounts Manager.

Rules: the subject must contain the bill number exactly as given, for example
'Payment reminder: Bill INV-2026-0087'; start with 'Dear Accounts Team' and name the patient the bill
relates to; line 1 states bill number, amount in Indian comma format and days overdue; offer help with
payment options, instalments or insurance queries and give the billing contact; close with the sender;
under 120 words; Indian English; no em or en dashes; never mention diagnosis, treatment, department or any
medical detail; never threaten or mention legal action.
```
**Output parser example:** `{"email_subject":"Payment reminder: Bill INV-2026-0087","email_body":"Dear Accounts Team, ..."}`

The subject must keep the bill number: workflow V2 matches replies to bills from it.
