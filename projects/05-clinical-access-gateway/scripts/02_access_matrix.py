"""Run every persona against every resource and write who-can-see-what to reports/access_matrix.csv.

    python scripts/02_access_matrix.py
Target patient is #1 (on Dr Rao's list, ward A), so the matrix also shows the row-level rules.
"""
import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway import Gateway  # noqa: E402
from gateway.predict import NoShowScorer  # noqa: E402
from gateway.users import TOKENS  # noqa: E402

CALLS = [("patient_record", "read", {"patient_id": 1}), ("lab_results", "read", {"patient_id": 1}),
         ("or_availability", "read", {"date": "2026-11-10"}), ("no_show_risk", "read", {})]


def main() -> None:
    audit = Path(tempfile.mkdtemp()) / "audit.jsonl"
    rows = []
    for token, user in TOKENS.items():
        for resource, action, params in CALLS:
            gw = Gateway(audit, scorer=NoShowScorer())
            r = gw.request(token, resource, action, params)
            rows.append({"user": user.user_id, "role": user.role, "ward": user.ward or "", "resource": resource,
                         "result": "allowed" if r.ok else "denied", "fields": ",".join(r.rows[0]) if r.rows else ""})
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    with (out / "access_matrix.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['user']:8s} {r['role']:12s} {r['resource']:16s} {r['result']:8s} {r['fields']}")


if __name__ == "__main__":
    main()
