"""Access rules, break-glass, writes, and audit integrity for the gateway."""
import json

import pytest

from gateway import Gateway
from gateway.policy import POLICY


@pytest.fixture
def gw(tmp_path):
    return Gateway(tmp_path / "audit.jsonl")


def rec(gw, token, pid, **kw):
    return gw.request(token, "patient_record", "read", {"patient_id": pid}, **kw)


# ---- who sees which rows ------------------------------------------------------------------------------
def test_doctor_sees_own_patient_not_others(gw):
    assert rec(gw, "tok-rao", 1).ok
    assert not rec(gw, "tok-rao", 3).ok             # Dr Iyer's patient


def test_nurse_sees_own_ward_only(gw):
    assert rec(gw, "tok-nurse-a", 1).ok and not rec(gw, "tok-nurse-a", 3).ok


def test_patient_sees_only_self(gw):
    assert rec(gw, "tok-pat1", 1).ok and not rec(gw, "tok-pat1", 2).ok


def test_list_request_returns_only_what_you_may_see(gw):
    r = gw.request("tok-rao", "lab_results", "read", {})
    assert sorted({x["patient_id"] for x in r.rows}) == [1, 2, 5]
    r = gw.request("tok-pat2", "patient_record", "read", {})
    assert [x["patient_id"] for x in r.rows] == [2]


def test_missing_and_forbidden_look_the_same(gw):
    """A caller must not be able to learn which patient ids exist."""
    assert rec(gw, "tok-rao", 3).error == rec(gw, "tok-rao", 999).error


# ---- who sees which fields ----------------------------------------------------------------------------
def test_each_role_gets_only_its_fields(gw):
    assert "diagnosis" in rec(gw, "tok-rao", 1).rows[0]
    assert "diagnosis" not in rec(gw, "tok-nurse-a", 1).rows[0]
    assert set(rec(gw, "tok-desk", 1).rows[0]) == {"patient_id", "name", "phone"}
    lab = gw.request("tok-lab", "lab_results", "read", {"patient_id": 1}).rows[0]
    assert "value" not in lab and "name" not in lab


def test_housekeeping_never_sees_patient_data(gw):
    for resource in ("patient_record", "lab_results", "no_show_risk"):
        assert not gw.request("tok-clean", resource, "read", {"patient_id": 1}).ok
    rows = gw.request("tok-clean", "or_availability", "read", {"date": "2026-11-10"}).rows
    assert all(set(r) == {"room", "date", "slot", "state"} for r in rows)


def test_every_policy_row_only_lists_fields_that_exist(gw):
    for (role, resource), rule in POLICY.items():
        assert isinstance(rule["fields"], list)


# ---- deny by default ----------------------------------------------------------------------------------
def test_unknown_token_and_unlisted_combination_denied(gw):
    assert not gw.request("nope", "patient_record", "read", {"patient_id": 1}).ok
    assert not gw.request("tok-rao", "billing", "read", {}).ok
    assert not gw.request("tok-nurse-a", "or_booking", "book", {"room": "OR-1", "date": "d", "slot": "10:00", "patient_id": 1}).ok
    assert not gw.request("tok-rao", "patient_record", "delete", {"patient_id": 1}).ok


def test_bad_parameters_are_denied_not_crashed(gw):
    assert not gw.request("tok-rao", "patient_record", "read", {"patient_id": "1; DROP TABLE patients"}).ok
    assert not gw.request("tok-rao", "or_availability", "read", {}).ok


# ---- break glass --------------------------------------------------------------------------------------
def test_break_glass_needs_a_reason_and_is_flagged(gw):
    assert not rec(gw, "tok-rao", 3).ok
    assert not rec(gw, "tok-rao", 3, break_glass_reason="short").ok
    r = rec(gw, "tok-rao", 3, break_glass_reason="ER arrival, unconscious, covering Dr Iyer")
    assert r.ok and r.break_glass
    assert set(r.rows[0]) == {"patient_id", "name", "dob", "ward", "diagnosis", "medications", "allergies"}   # role fields only
    q = gw.break_glass_review_queue()
    assert len(q) == 1 and q[0]["user"] == "d_rao" and "ER arrival" in q[0]["reason"]


def test_break_glass_not_available_to_other_roles(gw):
    for token in ("tok-clean", "tok-pat1", "tok-lab"):
        assert not rec(gw, token, 3, break_glass_reason="I really need it, honestly").ok
    assert not gw.request("tok-pat1", "patient_record", "read", {"patient_id": 2},
                          break_glass_reason="I am worried about my neighbour").ok


# ---- writes -------------------------------------------------------------------------------------------
def test_doctor_books_for_own_patient_only_and_no_double_booking(gw):
    book = lambda tok, pid, slot: gw.request(tok, "or_booking", "book", {"room": "OR-1", "date": "2026-11-10", "slot": slot, "patient_id": pid})
    assert book("tok-rao", 1, "10:00").ok
    assert not book("tok-rao", 2, "10:00").ok            # already taken
    assert not book("tok-rao", 3, "12:00").ok            # not Dr Rao's patient
    states = {r["slot"]: r["state"] for r in gw.request("tok-nurse-a", "or_availability", "read", {"date": "2026-11-10"}).rows if r["room"] == "OR-1"}
    assert states["10:00"] == "booked"


def test_cannot_book_a_room_that_needs_cleaning_until_housekeeping_clears_it(gw):
    book = lambda: gw.request("tok-rao", "or_booking", "book", {"room": "OR-2", "date": "2026-11-10", "slot": "10:00", "patient_id": 1})
    assert not book().ok
    assert gw.request("tok-clean", "or_cleaning", "mark_cleaned", {"room": "OR-2", "date": "2026-11-10", "slot": "10:00"}).ok
    assert book().ok


# ---- audit --------------------------------------------------------------------------------------------
def test_denials_are_audited_and_chain_verifies(gw):
    rec(gw, "tok-rao", 1)
    rec(gw, "tok-rao", 3)
    gw.request("bad", "patient_record", "read", {})
    e = gw.audit.entries()
    assert [x["ok"] for x in e] == [True, False, False]
    assert gw.audit.verify() == (True, None)


def test_tampering_with_the_audit_log_is_detected(gw):
    for pid in (1, 2, 3, 5):
        rec(gw, "tok-rao", pid)
    lines = gw.audit.path.read_text().splitlines()
    forged = json.loads(lines[2])
    forged["ok"] = True
    lines[2] = json.dumps(forged)
    gw.audit.path.write_text("\n".join(lines) + "\n")
    assert gw.audit.verify() == (False, 2)


def test_deleting_a_line_is_detected(gw):
    for pid in (1, 2, 5):
        rec(gw, "tok-rao", pid)
    lines = gw.audit.path.read_text().splitlines()
    gw.audit.path.write_text("\n".join(lines[:1] + lines[2:]) + "\n")
    assert gw.audit.verify()[0] is False
