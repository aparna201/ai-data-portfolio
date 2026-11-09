"""Structure checks on the generated n8n workflows. These do NOT prove n8n will import them."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

N8N = Path(__file__).parent.parent / "n8n"
FILES = ["patient_collections_v1.json", "patient_collections_v2.json"]


def load(name):
    return json.loads((N8N / "workflows" / name).read_text())


@pytest.mark.parametrize("name", FILES)
def test_graph_is_consistent(name):
    wf = load(name)
    assert wf["id"]                      # n8n import fails without a top-level id
    names = [n["name"] for n in wf["nodes"]]
    assert len(names) == len(set(names))
    assert len({n["id"] for n in wf["nodes"]}) == len(names)
    for src, kinds in wf["connections"].items():
        assert src in names
        for outputs in kinds.values():
            for slot in outputs:
                for link in slot:
                    assert link["node"] in names


@pytest.mark.parametrize("name", FILES)
def test_everything_is_reachable_from_a_trigger(name):
    wf = load(name)
    triggers = [n["name"] for n in wf["nodes"] if "Trigger" in n["type"] or n["type"].endswith("Trigger")]
    assert triggers
    seen, todo = set(triggers), list(triggers)
    # AI sub-nodes feed INTO an agent; treat that edge as reachable both ways
    edges = {}
    for src, kinds in wf["connections"].items():
        for outputs in kinds.values():
            for slot in outputs:
                for link in slot:
                    edges.setdefault(src, []).append(link["node"])
                    edges.setdefault(link["node"], []).append(src) if "Gemini" in src or "Parser" in src else None
    while todo:
        for nxt in edges.get(todo.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    unreachable = {n["name"] for n in wf["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"} - seen
    assert not unreachable


@pytest.mark.parametrize("name", FILES)
def test_no_credentials_or_real_addresses(name):
    raw = (N8N / "workflows" / name).read_text()
    assert '"credentials"' not in raw
    emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", raw))
    assert not emails, emails            # only REPLACE_WITH_* placeholders allowed
    assert "REPLACE_WITH_SHEET_ID" in raw


def test_v1_wiring_matches_the_guide():
    c = load("patient_collections_v1.json")["connections"]
    to = lambda s, i=0: [l["node"] for l in c[s]["main"][i]]
    assert to("Agent 1 Aging Analyser") == ["Should Remind?", "Escalate Now?"]
    assert to("Should Remind?") == ["Agent 2 Reminder Writer"]
    assert to("Agent 2 Reminder Writer") == ["Send Reminder Email"]
    assert to("Send Reminder Email") == ["Update AR Sheet"] and to("Update AR Sheet") == ["Log Reminder"]
    assert to("Escalate Now?") == ["Agent 3 Escalation Writer"]
    assert to("Agent 3 Escalation Writer") == ["Send Manager Alert"]
    assert to("Send Manager Alert") == ["Mark Escalated"] and to("Mark Escalated") == ["Log Escalation"]


def test_v2_wiring_matches_the_guide():
    c = load("patient_collections_v2.json")["connections"]
    chain = ["Gmail Reply Trigger", "Extract Invoice Ref", "Has Invoice Ref?", "Agent 4 Reply Classifier",
             "Compute Pause Date", "Update AR Pause", "Log Reply", "Needs Human?", "Send Team Alert"]
    for a, b in zip(chain, chain[1:]):
        assert [l["node"] for l in c[a]["main"][0]] == [b]


def test_code_node_is_the_tested_javascript():
    code = next(n for n in load("patient_collections_v1.json")["nodes"] if n["name"] == "Agent 1 Aging Analyser")
    assert code["parameters"]["jsCode"] == (N8N / "agent1_aging_analyser.js").read_text()
    assert code["parameters"]["mode"] == "runOnceForEachItem"


def test_hospital_safety_settings():
    v1, v2 = load("patient_collections_v1.json"), load("patient_collections_v2.json")
    assert v1["settings"]["timezone"] == "Asia/Kolkata"
    trig = next(n for n in v2["nodes"] if n["name"] == "Gmail Reply Trigger")["parameters"]["filters"]
    assert trig["labelIds"] == ["INBOX"] and "-from:me" in trig["q"]
    a2 = next(n for n in v1["nodes"] if n["name"] == "Agent 2 Reminder Writer")["parameters"]["text"]
    assert "department" in a2.lower() and "{{ $('Read AR Sheet').item.json.department" not in a2
    assert "patient_contact_no" not in a2
    a3 = next(n for n in v1["nodes"] if n["name"] == "Agent 3 Escalation Writer")["parameters"]["text"]
    assert "patient_contact_no" in a3          # only the manager alert carries the number
    upd = next(n for n in v2["nodes"] if n["name"] == "Update AR Pause")["parameters"]["columns"]["value"]["status"]
    assert "paid_claimed" in upd and "'paid'" not in upd


def test_generated_files_are_up_to_date(tmp_path):
    before = {f: (N8N / "workflows" / f).read_text() for f in FILES}
    subprocess.run([sys.executable, str(N8N / "build_workflows.py")], check=True, capture_output=True)
    assert before == {f: (N8N / "workflows" / f).read_text() for f in FILES}
