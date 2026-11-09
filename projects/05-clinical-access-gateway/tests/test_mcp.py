import asyncio
import json

import pytest

pytest.importorskip("mcp.server.mcpserver")       # needs mcp 2.x; skipped otherwise


def call(name, args):
    from gateway.mcp_server import mcp
    r = asyncio.run(mcp.call_tool(name, args))
    return json.loads(r.content[0].text)


def test_tools_are_listed_and_enforce_policy(tmp_path, monkeypatch):
    from gateway import mcp_server
    from gateway.gateway import Gateway
    monkeypatch.setattr(mcp_server, "gw", Gateway(tmp_path / "audit.jsonl"))
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"read_patient_record", "check_or_availability", "book_or"} <= names
    assert call("read_patient_record", {"token": "tok-rao", "patient_id": 1})["ok"]
    assert not call("read_patient_record", {"token": "tok-rao", "patient_id": 3})["ok"]
    assert not call("read_patient_record", {"token": "tok-clean", "patient_id": 1})["ok"]
