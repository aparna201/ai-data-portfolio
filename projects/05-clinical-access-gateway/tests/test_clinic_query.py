import json
import sqlite3

import pytest

from clinic_query import ClinicQuery, Filter, QueryPlan, build_sql, plan_from_json
from clinic_query.db import connect_read_only, create_demo_db


@pytest.fixture
def svc(tmp_path):
    db = tmp_path / "clinic.db"
    create_demo_db(db)
    return ClinicQuery(db, tmp_path / "audit.jsonl")


def test_billing_counts_unpaid_invoices(svc):
    answer = svc.ask("billing", "how many unpaid invoices")
    assert answer.ok and answer.rows == [(3,)]


def test_billing_sums_unpaid_invoices(svc):
    answer = svc.ask("billing", "total unpaid invoices")
    assert answer.ok and answer.rows == [(3450.0,)]


def test_front_desk_lists_only_requested_doctor(svc):
    answer = svc.ask("front_desk", "list appointments for Dr Rao")
    assert answer.ok and len(answer.rows) == 3
    assert {row[answer.columns.index("doctor")] for row in answer.rows} == {"Dr. Rao"}


def test_role_cannot_reach_other_tables(svc):
    answer = svc.ask("front_desk", "how many unpaid invoices")
    assert not answer.ok and "cannot access" in answer.error


def test_role_cannot_use_hidden_columns_even_to_filter():
    # billing may not see phone numbers; also may not probe them via a filter
    with pytest.raises(PermissionError):
        build_sql(plan_from_json({"table": "patients", "columns": ["phone"]}), "billing")
    with pytest.raises(PermissionError):
        build_sql(QueryPlan("patients", filters=[Filter("phone", "=", "555-0101")]), "billing")


def test_unknown_role_is_denied():
    with pytest.raises(PermissionError):
        build_sql(QueryPlan("patients"), "intern")


def test_injection_text_is_just_a_value(svc):
    plan = QueryPlan("patients", filters=[Filter("name", "=", "x'; DROP TABLE patients;--")])
    sql, params = build_sql(plan, "front_desk")
    assert "DROP" not in sql and params[0].startswith("x'")
    assert svc.ask("front_desk", "list patients").ok  # table still exists


def test_database_connection_is_read_only(tmp_path):
    db = tmp_path / "clinic.db"
    create_demo_db(db)
    with connect_read_only(db) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM patients")


def test_every_request_is_audited(svc, tmp_path):
    svc.ask("billing", "how many unpaid invoices")
    svc.ask("front_desk", "how many unpaid invoices")
    records = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [r["ok"] for r in records] == [True, False]
    assert records[0]["role"] == "billing"
