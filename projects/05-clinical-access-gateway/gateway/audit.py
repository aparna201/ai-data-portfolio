"""Tamper-evident audit log: each line carries the hash of the previous line.

Editing, deleting or reordering any line breaks every hash after it, and verify() points at the first bad line.
(A real deployment also ships the latest hash to a separate system so the log owner cannot rewrite the whole chain.)
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _last_hash(self) -> str:
        if not self.path.exists() or not self.path.read_text().strip():
            return GENESIS
        return json.loads(self.path.read_text().strip().splitlines()[-1])["hash"]

    def write(self, **event) -> None:
        body = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        prev = self._last_hash()
        with self.path.open("a") as f:
            f.write(json.dumps({**body, "prev": prev, "hash": _hash(prev, body)}) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def verify(self) -> tuple[bool, int | None]:
        """(True, None) if intact, else (False, index of the first line that does not fit the chain)."""
        prev = GENESIS
        for i, e in enumerate(self.entries()):
            body = {k: v for k, v in e.items() if k not in ("prev", "hash")}
            if e["prev"] != prev or e["hash"] != _hash(prev, body):
                return False, i
            prev = e["hash"]
        return True, None
