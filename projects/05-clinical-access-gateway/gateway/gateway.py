"""The front door. Every request goes through the same eight steps, in this order:

 1 who is this (token)   2 may this role do this action on this resource   3 which rows are in scope
 4 fetch from the source system   5 keep only the permitted fields   6 do the action (book / mark cleaned)
 7 audit the outcome   8 return.  A denial is audited too.
"""
from dataclasses import dataclass, field
from pathlib import Path

from .audit import AuditLog
from .policy import BREAK_GLASS, MIN_REASON_CHARS, POLICY
from .predict import NoShowScorer
from .systems import Systems
from .users import TOKENS, User

DENY = "Not permitted or not found."      # one message for both, so a caller cannot probe which patients exist


@dataclass
class Response:
    ok: bool
    rows: list[dict] = field(default_factory=list)
    error: str | None = None
    break_glass: bool = False


class Gateway:
    def __init__(self, audit_path: str | Path, systems: Systems | None = None, scorer: NoShowScorer | None = None) -> None:
        self.systems = systems or Systems()
        self.audit = AuditLog(audit_path)
        self.scorer = scorer

    # ---- scope -------------------------------------------------------------------------------------------
    def _in_scope(self, user: User, scope: str, patient_id: int) -> bool:
        if scope == "all":
            return True
        if scope == "care_team":
            return patient_id in self.systems.care_teams.get(user.user_id, set())
        if scope == "ward":
            return user.ward is not None and self.systems.records.ward_of(patient_id) == user.ward
        if scope == "own":
            return user.patient_id == patient_id
        return False

    # ---- single entry point --------------------------------------------------------------------------------
    def request(self, token: str, resource: str, action: str = "read", params: dict | None = None,
                break_glass_reason: str | None = None) -> Response:
        params = params or {}
        user = TOKENS.get(token)
        if user is None:
            self.audit.write(user="unknown", role=None, resource=resource, action=action, params=params, ok=False, why="bad token")
            return Response(False, error="Unauthenticated.")
        rule = POLICY.get((user.role, resource))
        if rule is None or action not in rule["actions"]:
            return self._deny(user, resource, action, params, "role has no such permission")
        try:
            resp = self._dispatch(user, rule, resource, action, params, break_glass_reason)
        except (KeyError, ValueError, TypeError):
            return self._deny(user, resource, action, params, "bad parameters")
        self.audit.write(user=user.user_id, role=user.role, resource=resource, action=action, params=params, ok=resp.ok,
                         why=resp.error, break_glass=resp.break_glass, reason=break_glass_reason if resp.break_glass else None,
                         rows=len(resp.rows))
        return resp

    def _deny(self, user: User, resource, action, params, why) -> Response:
        self.audit.write(user=user.user_id, role=user.role, resource=resource, action=action, params=params, ok=False, why=why)
        return Response(False, error=DENY)

    def _fail(self, error: str = DENY) -> Response:
        return Response(False, error=error)

    # ---- resources -----------------------------------------------------------------------------------------
    def _dispatch(self, user, rule, resource, action, params, reason) -> Response:
        if resource in ("patient_record", "lab_results"):
            return self._read_patient_data(user, rule, resource, params, reason)
        if resource == "or_availability":
            date = str(params["date"])
            rows = self.systems.scheduler.availability(date)
            return Response(True, [{k: r[k] for k in rule["fields"]} for r in rows])
        if resource == "or_booking":
            pid = int(params["patient_id"])
            if not self._in_scope(user, rule["scope"], pid):
                return self._fail()
            ok = self.systems.scheduler.book(str(params["room"]), str(params["date"]), str(params["slot"]), pid, user.user_id)
            return Response(ok, [{"booked": True}] if ok else [], None if ok else "Slot unavailable.")
        if resource == "or_cleaning":
            ok = self.systems.scheduler.mark_cleaned(str(params["room"]), str(params["date"]), str(params["slot"]))
            return Response(ok, [{"cleaned": True}] if ok else [], None if ok else "Nothing to clean there.")
        if resource == "no_show_risk":
            if self.scorer is None:
                return self._fail("Prediction not enabled.")
            return Response(True, [{"patient_id": int(p), "risk": r} for p, r in self.scorer.risk_by_patient().items()])
        return self._fail()

    def _read_patient_data(self, user, rule, resource, params, reason) -> Response:
        source = self.systems.records if resource == "patient_record" else self.systems.lab
        pid = params.get("patient_id")
        rows = source.get(int(pid) if pid is not None else None)
        # patients can only ever ask about themselves, even without a filter
        if rule["scope"] == "own" and pid is None:
            rows = [r for r in rows if r["patient_id"] == user.patient_id]
        allowed = [r for r in rows if self._in_scope(user, rule["scope"], r["patient_id"])]
        glass = False
        if len(allowed) < len(rows):                 # something was out of scope
            if pid is None:
                rows = allowed                       # a list request just returns what you may see
            elif (user.role, resource) in BREAK_GLASS and reason and len(reason.strip()) >= MIN_REASON_CHARS:
                rows, glass = rows, True             # emergency override, will be reviewed
            else:
                return self._fail()
        elif not rows and pid is not None:
            return self._fail()
        return Response(True, [{k: r[k] for k in rule["fields"]} for r in rows], break_glass=glass)

    # ---- for the compliance reviewer ------------------------------------------------------------------------
    def break_glass_review_queue(self) -> list[dict]:
        return [e for e in self.audit.entries() if e.get("break_glass")]
