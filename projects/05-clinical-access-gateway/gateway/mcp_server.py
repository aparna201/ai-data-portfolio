"""Expose the gateway as MCP tools, so any MCP-capable AI client talks to the hospital systems only through it.

    python -m gateway.mcp_server            (needs: pip install "mcp>=2"; written against the 2.x SDK)

Identity: the caller's token is passed on every tool call. In production the token comes from the hospital's single
sign-on and is bound to the MCP session, never typed by a model. The model has no way to widen its own access: the
policy table in policy.py decides, and every call is audited.
"""
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .gateway import Gateway

mcp = MCPServer("clinical-access-gateway")
gw = Gateway(Path("audit.jsonl"))


def _out(r):
    return {"ok": r.ok, "rows": r.rows, "error": r.error, "break_glass": r.break_glass}


@mcp.tool()
def read_patient_record(token: str, patient_id: int, break_glass_reason: str | None = None) -> dict:
    """Read one patient's record. Fields and rows depend on the caller's role."""
    return _out(gw.request(token, "patient_record", "read", {"patient_id": patient_id}, break_glass_reason))


@mcp.tool()
def read_lab_results(token: str, patient_id: int | None = None, break_glass_reason: str | None = None) -> dict:
    """Read lab results. Without patient_id, returns only those the caller may see."""
    params = {} if patient_id is None else {"patient_id": patient_id}
    return _out(gw.request(token, "lab_results", "read", params, break_glass_reason))


@mcp.tool()
def check_or_availability(token: str, date: str) -> dict:
    """Which operating rooms and slots are free, booked or being cleaned on a date (YYYY-MM-DD)."""
    return _out(gw.request(token, "or_availability", "read", {"date": date}))


@mcp.tool()
def book_or(token: str, room: str, date: str, slot: str, patient_id: int) -> dict:
    """Book an operating room slot for one of the caller's own patients (doctors only)."""
    return _out(gw.request(token, "or_booking", "book", {"room": room, "date": date, "slot": slot, "patient_id": patient_id}))


@mcp.tool()
def mark_or_cleaned(token: str, room: str, date: str, slot: str) -> dict:
    """Housekeeping marks a room cleaned."""
    return _out(gw.request(token, "or_cleaning", "mark_cleaned", {"room": room, "date": date, "slot": slot}))


if __name__ == "__main__":
    mcp.run()
