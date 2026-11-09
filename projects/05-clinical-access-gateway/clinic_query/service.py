"""The service: question + role -> checked SQL -> rows, with an audit trail."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .db import connect_read_only
from .plan import build_sql
from .translate import RuleBasedTranslator


@dataclass
class Answer:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    sql: str | None = None
    error: str | None = None


class ClinicQuery:
    def __init__(self, db_path: str | Path, audit_path: str | Path = "audit.jsonl",
                 translator=None) -> None:
        self.db_path = db_path
        self.audit_path = Path(audit_path)
        self.translator = translator or RuleBasedTranslator()

    def ask(self, role: str, question: str) -> Answer:
        sql, params = None, []
        try:
            plan = self.translator.parse(question)
            sql, params = build_sql(plan, role)
            with connect_read_only(self.db_path) as conn:
                cur = conn.execute(sql, params)
                answer = Answer(True, [d[0] for d in cur.description], cur.fetchall(), sql)
        except (PermissionError, ValueError) as exc:
            answer = Answer(False, sql=sql, error=str(exc))
        self._audit(role, question, sql, params, answer)
        return answer

    def _audit(self, role, question, sql, params, answer: Answer) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), "role": role,
                  "question": question, "sql": sql, "params": params,
                  "ok": answer.ok, "error": answer.error}
        with self.audit_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
