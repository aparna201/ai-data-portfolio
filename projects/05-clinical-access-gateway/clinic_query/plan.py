"""Query plans and the SQL builder.

The language model (or rule-based translator) never writes SQL. It produces a small
structured `QueryPlan`. This module checks the plan against the caller's role and
builds the SQL itself: names come from the allow-list, values are bound parameters.
That makes SQL injection and out-of-policy access impossible by construction.
"""
from dataclasses import dataclass, field

from .policy import POLICY

ALLOWED_OPS = {"=", ">", "<", ">=", "<=", "like"}
MAX_ROWS = 100


@dataclass
class Filter:
    column: str
    op: str
    value: str | int | float


@dataclass
class QueryPlan:
    table: str
    columns: list[str] | None = None        # None = every column the role may see
    filters: list[Filter] = field(default_factory=list)
    aggregate: str | None = None            # None | "count" | "sum"
    sum_column: str | None = None
    limit: int = 50


def plan_from_json(data: dict) -> QueryPlan:
    """Parse the JSON an LLM returns, e.g.
    {"table": "invoices", "aggregate": "count", "filters": [{"column": "status", "op": "=", "value": "unpaid"}]}"""
    return QueryPlan(
        table=data["table"],
        columns=data.get("columns"),
        filters=[Filter(f["column"], f["op"], f["value"]) for f in data.get("filters", [])],
        aggregate=data.get("aggregate"),
        sum_column=data.get("sum_column"),
        limit=int(data.get("limit", 50)),
    )


def build_sql(plan: QueryPlan, role: str) -> tuple[str, list]:
    """Validate `plan` for `role` and return (sql, params). Raises PermissionError if not allowed."""
    tables = POLICY.get(role)
    if tables is None:
        raise PermissionError(f"Unknown role: {role}")
    if plan.table not in tables:
        raise PermissionError(f"Role '{role}' cannot access '{plan.table}'")
    allowed = tables[plan.table]

    def check(column: str) -> str:
        if column not in allowed:
            raise PermissionError(f"Role '{role}' cannot use column '{plan.table}.{column}'")
        return column

    where, params = [], []
    for f in plan.filters:
        if f.op.lower() not in ALLOWED_OPS:
            raise ValueError(f"Operator not allowed: {f.op}")
        where.append(f"{check(f.column)} {f.op.upper()} ?")
        params.append(f.value)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""

    if plan.aggregate == "count":
        return f"SELECT COUNT(*) AS count FROM {plan.table}{where_sql}", params
    if plan.aggregate == "sum":
        col = check(plan.sum_column or "")
        return f"SELECT SUM({col}) AS total FROM {plan.table}{where_sql}", params
    if plan.aggregate is not None:
        raise ValueError(f"Aggregate not supported: {plan.aggregate}")

    columns = [check(c) for c in (plan.columns or allowed)]
    limit = min(max(plan.limit, 1), MAX_ROWS)
    return (f"SELECT {', '.join(columns)} FROM {plan.table}{where_sql} LIMIT ?", params + [limit])
