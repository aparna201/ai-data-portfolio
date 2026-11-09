"""Generates the two n8n workflow files from the pieces kept in this repo.

    python n8n/build_workflows.py

Sources of truth: agent1_aging_analyser.js (Code node) and prompts/*.md (Gemini agents).
Output: workflows/patient_collections_v1.json and patient_collections_v2.json, plus sample_sheet/*.xlsx.

These files were written from the build guide, NOT exported from a running n8n, and were imported into
n8n 2.35.7 with `n8n import:workflow` (format accepted) but never opened in the editor or executed. They contain no credentials: n8n asks you to pick them after import. Placeholders to
replace: REPLACE_WITH_SHEET_ID, billing-mailbox and manager addresses.
"""
import csv
import json
import re
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHEET_ID = "REPLACE_WITH_SHEET_ID"
MANAGER = "REPLACE_WITH_MANAGER_EMAIL"
MODEL = "models/gemini-3.5-flash-lite"      # model ID taken from the build guide; confirm in Google AI Studio

_ids = iter(range(1, 10_000))


def nid() -> str:
    return str(uuid.UUID(int=next(_ids)))     # deterministic ids so regenerating gives identical files


def prompt_parts(filename: str) -> dict:
    text = (HERE / "prompts" / filename).read_text()
    return {
        "system": re.search(r"\*\*System message:\*\*\s*`([^`]+)`", text).group(1),
        "prompt": re.search(r"```\n(.*?)```", text, re.S).group(1).strip(),
        "example": re.search(r"\*\*Output parser example:\*\*\s*`(.*)`", text).group(1),
    }


def sheet_ref() -> dict:
    return {"__rl": True, "value": SHEET_ID, "mode": "id"}


def tab(name: str) -> dict:
    return {"__rl": True, "mode": "name", "value": name}


def node(name, type_, params, pos, version=1, **extra):
    n = {"parameters": params, "id": nid(), "name": name, "type": type_, "typeVersion": version,
         "position": list(pos)}
    n.update(extra)
    return n


def if_node(name, left, pos, op="true", strict=False):
    cond = {"leftValue": left, "operator": {"type": "boolean", "operation": op, "singleValue": True}}
    return node(name, "n8n-nodes-base.if", {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "",
                                   "typeValidation": "strict" if strict else "loose", "version": 1},
                       "conditions": [cond], "combinator": "and"}, "options": {}}, pos, 2.3)


def sheet_node(name, op, tab_name, mapping, pos, match=None):
    cols = {"mappingMode": "defineBelow", "value": mapping, "schema": []}
    if match:
        cols["matchingColumns"] = [match]
    params = {"documentId": sheet_ref(), "sheetName": tab(tab_name), "columns": cols, "options": {}}
    if op:
        params["operation"] = op
    return node(name, "n8n-nodes-base.googleSheets", params, pos, 4.7, onError="continueRegularOutput")


def agent(name, parts, temp, pos):
    """An AI agent plus its Gemini model and structured output parser. Returns (nodes, connections)."""
    a = node(name, "@n8n/n8n-nodes-langchain.agent", {
        "promptType": "define", "text": "=" + parts["prompt"].lstrip("="), "hasOutputParser": True,
        "options": {"systemMessage": parts["system"], "maxIterations": 3}}, pos, 3.1,
        onError="continueRegularOutput")
    llm = node(f"Gemini for {name}", "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
               {"modelName": MODEL, "options": {"temperature": temp}}, (pos[0] - 80, pos[1] + 220), 1.1)
    parser = node(f"Parser {name}", "@n8n/n8n-nodes-langchain.outputParserStructured",
                  {"jsonSchemaExample": parts["example"]}, (pos[0] + 80, pos[1] + 220), 1.3)
    conns = {llm["name"]: {"ai_languageModel": [[{"node": name, "type": "ai_languageModel", "index": 0}]]},
             parser["name"]: {"ai_outputParser": [[{"node": name, "type": "ai_outputParser", "index": 0}]]}}
    return [a, llm, parser], conns


def link(conns, src, dst, out=0):
    slots = conns.setdefault(src, {"main": []})["main"]
    while len(slots) <= out:
        slots.append([])
    slots[out].append({"node": dst, "type": "main", "index": 0})


def gmail_send(name, to, subject, message, pos):
    return node(name, "n8n-nodes-base.gmail", {"sendTo": to, "subject": subject, "emailType": "text",
                "message": message, "options": {"appendAttribution": False}}, pos, 2.2,
                onError="continueRegularOutput")


def count_expr():
    return "={{ Number($('Read AR Sheet').item.json.reminder_count || 0) + 1 }}"


def v1() -> dict:
    R, A1 = "$('Read AR Sheet').item.json", "$('Agent 1 Aging Analyser').item.json.output"
    nodes, c = [], {}
    nodes += [
        node("Manual Trigger", "n8n-nodes-base.manualTrigger", {}, (-1400, -100)),
        node("Daily 9AM IST", "n8n-nodes-base.scheduleTrigger",
             {"rule": {"interval": [{"triggerAtHour": 9}]}}, (-1400, 80), 1.3),
        node("Read AR Sheet", "n8n-nodes-base.googleSheets",
             {"documentId": sheet_ref(), "sheetName": tab("AR"), "options": {}}, (-1180, 0), 4.7),
        node("Agent 1 Aging Analyser", "n8n-nodes-base.code",
             {"mode": "runOnceForEachItem", "jsCode": (HERE / "agent1_aging_analyser.js").read_text()},
             (-960, 0), 2),
        if_node("Should Remind?", "={{ $json.output.should_remind }}", (-740, -100)),
        if_node("Escalate Now?", "={{ $json.output.escalate_now }}", (-740, 300)),
    ]
    a2, c2 = agent("Agent 2 Reminder Writer", prompt_parts("agent2_reminder_writer.md"), 0.4, (-500, -100))
    a3, c3 = agent("Agent 3 Escalation Writer", prompt_parts("agent3_escalation_writer.md"), 0.2, (-500, 300))
    nodes += a2 + a3
    c.update(c2), c.update(c3)
    nodes += [
        gmail_send("Send Reminder Email", f"={{{{ {R}.payer_email }}}}", "={{ $json.output.email_subject }}",
                   "={{ $json.output.email_body }}", (-240, -100)),
        sheet_node("Update AR Sheet", "appendOrUpdate", "AR", {
            "invoice_no": f"={{{{ {R}.invoice_no }}}}", "last_reminded_at": "={{ $now.toISO() }}",
            "reminder_count": count_expr(), "aging_bucket": f"={{{{ {A1}.aging_bucket }}}}",
            "days_overdue": f"={{{{ {A1}.days_overdue }}}}"}, (0, -100), match="invoice_no"),
        sheet_node("Log Reminder", "append", "Reminders Log", {
            "invoice_no": f"={{{{ {R}.invoice_no }}}}", "patient_name": f"={{{{ {R}.patient_name }}}}",
            "sent_at": "={{ $now.toISO() }}", "aging_bucket": f"={{{{ {A1}.aging_bucket }}}}",
            "tone_grade": f"={{{{ {A1}.tone_grade }}}}",
            "email_subject": "={{ $('Agent 2 Reminder Writer').item.json.output.email_subject }}",
            "email_body": "={{ $('Agent 2 Reminder Writer').item.json.output.email_body }}",
            "reminder_count": count_expr()}, (240, -100)),
        gmail_send("Send Manager Alert", MANAGER, "={{ $json.output.alert_subject }}",
                   "={{ $json.output.alert_body }}", (-240, 300)),
        sheet_node("Mark Escalated", "appendOrUpdate", "AR", {
            "invoice_no": f"={{{{ {R}.invoice_no }}}}", "last_escalated_at": "={{ $now.toISO() }}"},
            (0, 300), match="invoice_no"),
        sheet_node("Log Escalation", "append", "Escalations", {
            "invoice_no": f"={{{{ {R}.invoice_no }}}}", "patient_name": f"={{{{ {R}.patient_name }}}}",
            "patient_contact_no": f"={{{{ {R}.patient_contact_no }}}}", "department": f"={{{{ {R}.department }}}}",
            "invoice_amount": f"={{{{ {R}.invoice_amount }}}}", "days_overdue": f"={{{{ {A1}.days_overdue }}}}",
            "escalated_at": "={{ $now.toISO() }}",
            "manager_action_needed": "={{ $('Agent 3 Escalation Writer').item.json.output.alert_body }}"},
            (240, 300)),
        node("Sticky Note", "n8n-nodes-base.stickyNote", {"content": (
            "## Patient Collections Follow-Up V1\nReads the AR sheet daily, sends tone-graded reminders to the "
            "corporate payer, alerts the Patient Accounts Manager at 60+ days.\n\n**Before running:** replace "
            "REPLACE_WITH_SHEET_ID (all Sheets nodes) and REPLACE_WITH_MANAGER_EMAIL, attach Google Sheets, "
            "Gmail and Gemini credentials, set workflow timezone to Asia/Kolkata, test with dummy rows only."),
            "height": 220, "width": 700, "color": 4}, (-1400, -400)),
    ]
    for s, d in [("Manual Trigger", "Read AR Sheet"), ("Daily 9AM IST", "Read AR Sheet"),
                 ("Read AR Sheet", "Agent 1 Aging Analyser"), ("Agent 1 Aging Analyser", "Should Remind?"),
                 ("Agent 1 Aging Analyser", "Escalate Now?"), ("Agent 2 Reminder Writer", "Send Reminder Email"),
                 ("Send Reminder Email", "Update AR Sheet"), ("Update AR Sheet", "Log Reminder"),
                 ("Agent 3 Escalation Writer", "Send Manager Alert"), ("Send Manager Alert", "Mark Escalated"),
                 ("Mark Escalated", "Log Escalation")]:
        link(c, s, d)
    link(c, "Should Remind?", "Agent 2 Reminder Writer", 0)     # true output
    link(c, "Escalate Now?", "Agent 3 Escalation Writer", 0)
    return workflow("Patient Collections Follow-Up V1", nodes, c)


def v2() -> dict:
    X = "$('Extract Invoice Ref').item.json"
    C = "$('Agent 4 Reply Classifier').item.json.output"
    inv = "($json.subject || '').match(/INV-\\d{4}-\\d+/i)"
    nodes, c = [], {}
    nodes += [
        node("Gmail Reply Trigger", "n8n-nodes-base.gmailTrigger", {
            "pollTimes": {"item": [{"mode": "everyMinute"}]}, "simple": False,
            "filters": {"labelIds": ["INBOX"], "q": "subject:INV- -from:me", "readStatus": "unread",
                        "includeSpamTrash": False, "includeDrafts": False}, "options": {}},
            (-1400, -100), 1.4),
        node("Extract Invoice Ref", "n8n-nodes-base.set", {"assignments": {"assignments": [
            {"id": nid(), "name": "invoice_no", "type": "string",
             "value": f"={{{{ {inv} ? {inv}[0].toUpperCase() : '' }}}}"},
            {"id": nid(), "name": "from_email", "type": "string",
             "value": "={{ $json.from && $json.from.value && $json.from.value[0] ? $json.from.value[0].address : '' }}"},
            {"id": nid(), "name": "from_name", "type": "string",
             "value": "={{ $json.from && $json.from.value && $json.from.value[0] ? $json.from.value[0].name : '' }}"},
            {"id": nid(), "name": "reply_subject", "type": "string", "value": "={{ $json.subject }}"},
            {"id": nid(), "name": "reply_body", "type": "string",
             "value": "={{ ($json.text || '').substring(0, 2000) }}"},
            {"id": nid(), "name": "received_at", "type": "string", "value": "={{ $json.date || $now.toISO() }}"}]},
            "options": {}}, (-1180, -100), 3.4),
        node("Has Invoice Ref?", "n8n-nodes-base.if", {"conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 1},
            "conditions": [{"leftValue": "={{ $json.invoice_no }}",
                            "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
            "combinator": "and"}, "options": {}}, (-960, -100), 2.3),
    ]
    a4, c4 = agent("Agent 4 Reply Classifier", prompt_parts("agent4_reply_classifier.md"), 0.2, (-720, -100))
    nodes += a4
    c.update(c4)
    nodes += [
        node("Compute Pause Date", "n8n-nodes-base.set", {"assignments": {"assignments": [
            {"id": nid(), "name": "paused_until", "type": "string",
             "value": "={{ $now.plus({ days: $json.output.pause_days }).toFormat('yyyy-MM-dd') }}"}]},
            "includeOtherFields": True, "options": {}}, (-440, -100), 3.4),
        sheet_node("Update AR Pause", "appendOrUpdate", "AR", {
            "invoice_no": f"={{{{ {X}.invoice_no }}}}", "paused_until": "={{ $json.paused_until }}",
            "last_reply_at": f"={{{{ {X}.received_at }}}}", "reply_summary": "={{ $json.output.summary }}",
            "status": "={{ $json.output.intent === 'already_paid' ? 'paid_claimed' : 'overdue' }}"},
            (-200, -100), match="invoice_no"),
        sheet_node("Log Reply", "append", "Replies Log", {
            "invoice_no": f"={{{{ {X}.invoice_no }}}}", "from_name": f"={{{{ {X}.from_name }}}}",
            "from_email": f"={{{{ {X}.from_email }}}}", "received_at": f"={{{{ {X}.received_at}}}}",
            "subject": f"={{{{ {X}.reply_subject }}}}",
            "body_preview": f"={{{{ ({X}.reply_body || '').substring(0, 300) }}}}",
            "intent": f"={{{{ {C}.intent }}}}", "promised_date": f"={{{{ {C}.promised_date }}}}",
            "pause_days": f"={{{{ {C}.pause_days }}}}", "summary": f"={{{{ {C}.summary }}}}",
            "urgency": f"={{{{ {C}.urgency }}}}", "needs_human": f"={{{{ {C}.needs_human }}}}"}, (40, -100)),
        if_node("Needs Human?", f"={{{{ {C}.needs_human }}}}", (280, -100), strict=True),
        gmail_send("Send Team Alert", MANAGER,
                   f"=[REPLY-{{{{ {C}.urgency.toUpperCase() }}}}] {{{{ {X}.invoice_no }}}} : {{{{ {C}.intent }}}}",
                   (f"=Bill: {{{{ {X}.invoice_no }}}}\nFrom: {{{{ {X}.from_name }}}} ({{{{ {X}.from_email }}}})\n"
                    f"Received: {{{{ {X}.received_at }}}}\nIntent: {{{{ {C}.intent }}}}\n"
                    f"Urgency: {{{{ {C}.urgency }}}}\n\nAI summary:\n{{{{ {C}.summary }}}}\n\nOriginal reply:\n"
                    f"{{{{ {X}.reply_body }}}}\n\nSystem action: reminders paused for this bill until "
                    f"{{{{ $('Compute Pause Date').item.json.paused_until }}}}.\n\nRecommended: a team member "
                    "should reply or call personally within 1 working day."), (520, -100)),
        node("Sticky Note", "n8n-nodes-base.stickyNote", {"content": (
            "## Patient Collections Follow-Up V2: reply detection\nPolls the billing inbox for replies whose subject "
            "carries a bill number, classifies them, pauses reminders in the AR sheet, and alerts a person only "
            "when needed.\n\n**Before running:** replace REPLACE_WITH_SHEET_ID and REPLACE_WITH_MANAGER_EMAIL, "
            "attach credentials. Replies can contain health details: restrict the Replies Log tab."),
            "height": 200, "width": 700, "color": 5}, (-1400, -380)),
    ]
    for s, d in [("Gmail Reply Trigger", "Extract Invoice Ref"), ("Extract Invoice Ref", "Has Invoice Ref?"),
                 ("Has Invoice Ref?", "Agent 4 Reply Classifier"), ("Agent 4 Reply Classifier", "Compute Pause Date"),
                 ("Compute Pause Date", "Update AR Pause"), ("Update AR Pause", "Log Reply"),
                 ("Log Reply", "Needs Human?"), ("Needs Human?", "Send Team Alert")]:
        link(c, s, d)
    return workflow("Patient Collections Follow-Up V2 - Reply Detection", nodes, c)


def workflow(name, nodes, connections) -> dict:
    return {"id": "PatientCollections" + ("V1" if name.endswith("V1") else "V2"), "name": name, "nodes": nodes, "pinData": {}, "connections": connections, "active": False,
            "settings": {"executionOrder": "v1", "timezone": "Asia/Kolkata"}, "tags": []}


def sample_sheet() -> None:
    from openpyxl import Workbook
    with open(HERE.parent / "data" / "bills.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    ar_cols = ["invoice_no", "patient_name", "patient_contact_no", "payer_type", "payer_org", "payer_email",
               "department", "invoice_amount", "currency", "due_date", "status", "notes", "last_reminded_at",
               "reminder_count", "paused_until", "last_reply_at", "reply_summary", "days_overdue",
               "aging_bucket", "last_escalated_at"]
    wb = Workbook()
    ws = wb.active
    ws.title = "AR"
    ws.append(ar_cols)
    for r in rows:
        ws.append([float(r[c]) if c == "invoice_amount" else int(r[c]) if c == "reminder_count" and r[c]
                   else r.get(c, "") for c in ar_cols])
    for title, cols in [
            ("Reminders Log", "invoice_no patient_name sent_at aging_bucket tone_grade email_subject email_body reminder_count"),
            ("Escalations", "invoice_no patient_name patient_contact_no department invoice_amount days_overdue escalated_at manager_action_needed"),
            ("Replies Log", "invoice_no from_name from_email received_at subject body_preview intent promised_date pause_days summary urgency needs_human")]:
        wb.create_sheet(title).append(cols.split())
    wb.save(HERE / "sample_sheet" / "Patient_Collections_AR.xlsx")


if __name__ == "__main__":
    out = HERE / "workflows"
    out.mkdir(exist_ok=True)
    for fname, wf in [("patient_collections_v1.json", v1()), ("patient_collections_v2.json", v2())]:
        (out / fname).write_text(json.dumps(wf, indent=2) + "\n")
        print(f"{fname}: {len(wf['nodes'])} nodes")
    sample_sheet()
    print("sample_sheet/Patient_Collections_AR.xlsx written")
