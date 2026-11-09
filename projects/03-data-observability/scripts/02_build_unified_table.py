"""Step 2: PySpark: validate, dedupe, join the three products into one daily table, reconcile.

    python scripts/02_build_unified_table.py
Needs Java 17 or 21 and PySpark. The table goes to warehouse/ (not committed); the manifest to reports/unified/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from observability.lake_pipeline import run  # noqa: E402
from observability.sources import START  # noqa: E402


def main() -> None:
    inj = json.loads((ROOT / "data" / "sample" / "injected_counts.json").read_text())
    end = (START + pd.Timedelta(days=inj["days"] - 1)).strftime("%Y-%m-%d")
    m = run(ROOT / "data" / "sample", ROOT / "warehouse", START.strftime("%Y-%m-%d"), end)
    found = m["dq_rows_rejected"] == inj["dq_duplicates"] + inj["dq_orphans"] + inj["dq_bad_status"]
    print(f"quality rows in {m['dq_rows_in']} | rejected {m['dq_rows_rejected']} | clean {m['dq_rows_clean']}")
    print(f"rejected equals the problems planted in step 1: {found}")
    print(f"daily table: {m['fact_rows']} rows ({m['datasets']} datasets x {inj['days']} days); critical datasets {m['critical_datasets']}")
    print(f"reconciliation: {m['reconciliation']}  status: {m['status']}")
    (ROOT / "reports" / "unified").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "unified" / "run_manifest.json").write_text(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
