# What changed from the reference build, and why

The reference workflows were read node by node. These are the problems found and what the hospital version does.

| # | Reference behaviour | Problem | Hospital version |
|---|---|---|---|
| 1 | Agent 1 asked Gemini to do date arithmetic | LLM dates can be wrong; one API call per row | Code node with the same output fields (`n8n/agent1_aging_analyser.js`) |
| 2 | `Should Remind?` dropped `escalate`; `Is Escalation?` sat after the email send | Bills over 90 days got no email and no alert | Parallel `Escalate Now?` branch |
| 3 | Manager alert after every reminder at 60+ days | A new alert every 2 days for the same bill | `last_escalated_at`, 7-day gap |
| 4 | V1 never read `status` | V2 could set `paid` but V1 kept chasing | Code node skips paid, paid_claimed, closed, waived |
| 5 | V2 set `paid` when a patient said "already paid" | A claim is not proof | Writes `paid_claimed`; staff confirm the receipt |
| 6 | `angry` paused 0 days | Next reminder reached an angry patient | Pauses 7 days and alerts a human |
| 7 | `reminder_count + 1` on a sheet value | Text can concatenate to "11" | `Number(...)` wrapper |
| 8 | Gmail trigger had no label or sender filter | Could process the reminders it sent | `INBOX` label and `-from:me` |
| 9 | V2 accepts any sender with a bill number in the subject | A relative or anyone could pause a bill | Not built. Optional: compare `from_email` with the AR row |
| 10 | Founder email and Sheet ID hard-coded | Imported JSON would alert the author | Built by hand with own addresses |
| 11 | Model `gemini-2.5-flash` | Restricted for new projects | Newer Flash-Lite model ID |
| 12 | 9 AM relied on server timezone | Reminders at the wrong hour | Workflow timezone Asia/Kolkata |

Also new for hospitals: three intents (`insurance_pending`, `needs_payment_plan`, `wrong_contact`), a softer
tone ladder (no "48 hour ask" or "final warning"), and manager rather than founder escalation.

## Decisions taken with the hospital side

- Corporate-paid bills only; emails go to the corporate payer's accounts team.
- Data source: a Google Sheet the billing team updates daily.
- After 60 days overdue, reminders repeat every 7 days.
- Demo uses a personal Gmail for sending and alerts; hosting decision postponed.
- Still open: WhatsApp/SMS, whether patient names may go to a paid Gemini key, language and volume.

## Test plan (run with dummy patients and your own email addresses)

| # | Test | Expected |
|---|---|---|
| 1 | Run V1 with 6 to 8 dummy rows across all buckets | Not-due row skipped; others get a tone matching days overdue |
| 2 | Open Reminders Log | One row per email, subject has the bill number |
| 3 | Open AR | `last_reminded_at`, `reminder_count` 1, `days_overdue`, `aging_bucket` filled |
| 4 | Run V1 again straight away | No new emails (cooldown) |
| 5 | A row at 70 days | Reminder plus one manager alert; Escalations row; `last_escalated_at` set |
| 6 | A row at 100 days | No patient email; manager alert only |
| 7 | Run V1 again | No second manager alert within 7 days |
| 8 | Reply "I will pay on 25 October" | Replies Log intent `paying_soon`, `paused_until` 15 days ahead |
| 9 | Reply "This bill is wrong" | `disputing`, manager alert `[REPLY-HIGH]` |
| 10 | Reply "I already paid on 12 September" | status `paid_claimed`; V1 skips it |
| 11 | Run V1 after 8 to 10 | Paused, paid_claimed and disputing rows skipped |

Tests 1 to 7 are mirrored by `tests/test_receivables.py` (Python) and checked against the n8n Code node by
`tests/test_js_parity.py`. Tests 8 to 11 need live Gemini and Gmail; the Python version covers the pause and
status rules only.
