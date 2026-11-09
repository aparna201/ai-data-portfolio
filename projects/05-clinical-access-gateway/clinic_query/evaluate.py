"""Scoring the translator, and attacking the policy layer.

Translator score: for each labeled question, does the plan match the expected one (plan match),
and does running it give the same rows as the expected plan (answer match)? A question the system
should refuse ("what is the weather") counts as correct only if it refuses.
"""
import json
import sqlite3
from pathlib import Path

from .plan import Filter, QueryPlan, build_sql, plan_from_json
from .service import ClinicQuery


def load(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text())


def _norm(plan: QueryPlan) -> tuple:
    return (plan.table, plan.aggregate, plan.sum_column if plan.aggregate == "sum" else None,
            tuple(sorted((f.column, f.op, f.value) for f in plan.filters)))


def _expected_plan(item: dict) -> QueryPlan:
    return QueryPlan(item["table"], filters=[Filter(*f) for f in item["filters"]],
                     aggregate=item["aggregate"], sum_column=item["sum_column"])


class _Fixed:
    def __init__(self, plan: QueryPlan):
        self.plan = plan

    def parse(self, _):
        return self.plan


def score_translator(items: list[dict], translator, db_path: str | Path, audit_path: str | Path) -> dict:
    results = []
    for item in items:
        q, role = item["question"], item["role"]
        try:
            got = translator.parse(q)
        except ValueError:
            got = None
        if item.get("refuse"):
            plan_ok = answer_ok = got is None
        else:
            want = _expected_plan(item)
            plan_ok = got is not None and _norm(got) == _norm(want)
            gold = ClinicQuery(db_path, audit_path, _Fixed(want)).ask(role, q)
            pred = ClinicQuery(db_path, audit_path, _Fixed(got)).ask(role, q) if got else None
            answer_ok = pred is not None and (gold.ok, gold.rows) == (pred.ok, pred.rows)
        results.append({"question": q, "role": role, "plan_ok": plan_ok, "answer_ok": answer_ok})
    n = len(results)
    return {"n": n, "plan_accuracy": round(sum(r["plan_ok"] for r in results) / n, 3),
            "answer_accuracy": round(sum(r["answer_ok"] for r in results) / n, 3),
            "misses": [r["question"] for r in results if not r["answer_ok"]]}


# Each attack is (description, role, plan as JSON-like dict, what must happen).
ATTACKS = [
    ("role reads a table outside its policy", "front_desk", {"table": "invoices"}, "denied"),
    ("billing asks for a hidden column", "billing", {"table": "patients", "columns": ["phone"]}, "denied"),
    ("hidden column used only in a filter", "billing",
     {"table": "patients", "filters": [{"column": "phone", "op": "=", "value": "555-0101"}]}, "denied"),
    ("SQL in the operator", "front_desk",
     {"table": "patients", "filters": [{"column": "name", "op": "=; DROP TABLE patients;--", "value": "x"}]}, "denied"),
    ("SQL in the filter column", "front_desk",
     {"table": "patients", "filters": [{"column": "1=1 OR name", "op": "=", "value": "x"}]}, "denied"),
    ("SQL in a selected column", "front_desk", {"table": "patients", "columns": ["name; DROP TABLE patients"]}, "denied"),
    ("read the database's own catalogue", "doctor", {"table": "sqlite_master"}, "denied"),
    ("unsupported aggregate", "billing", {"table": "invoices", "aggregate": "drop"}, "denied"),
    ("sum over a hidden column", "billing", {"table": "invoices", "aggregate": "sum", "sum_column": "phone"}, "denied"),
    ("unknown role", "intern", {"table": "patients"}, "denied"),
    ("injection text as a value", "front_desk",
     {"table": "patients", "filters": [{"column": "name", "op": "=", "value": "x'; DROP TABLE patients;--"}]}, "harmless"),
    ("huge row limit", "front_desk", {"table": "patients", "limit": 10_000_000}, "capped"),
]


def run_attacks(db_path: str | Path) -> list[dict]:
    def count_rows() -> int:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as c:
            return sum(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("patients", "appointments", "invoices"))

    before = count_rows()
    out = []
    for desc, role, raw, expect in ATTACKS:
        try:
            sql, params = build_sql(plan_from_json(raw), role)
            denied, outcome = False, "built"
            if expect == "capped":
                passed = params[-1] == 100
            elif expect == "harmless":
                passed = "DROP" not in sql and any("DROP" in str(p) for p in params)
            else:
                passed = False
        except (PermissionError, ValueError, KeyError):
            passed = expect == "denied"
        out.append({"attack": desc, "expected": expect, "passed": passed})
    out.append({"attack": "database contents unchanged after all attacks", "expected": "same",
                "passed": count_rows() == before})
    return out
