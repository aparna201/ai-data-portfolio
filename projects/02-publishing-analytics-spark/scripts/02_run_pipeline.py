"""Step 2: run the PySpark pipeline: validate, dedupe, aggregate to a daily table, reconcile.

    python scripts/02_run_pipeline.py
Needs Java 17 or 21 and PySpark. Output goes to warehouse/ (not committed); the manifest is copied to reports/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from publishing_etl.pipeline import run  # noqa: E402


def main() -> None:
    m = run(ROOT / "data" / "sample", ROOT / "warehouse")
    expected = json.loads((ROOT / "data" / "sample" / "injected_counts.json").read_text())
    ok = (m["invalid_rows"], m["duplicate_rows"], m["rows_out"]) == (
        expected["invalid_rows"], expected["duplicates"], expected["good_rows"])
    print(f"rows in {m['rows_in']} | invalid {m['invalid_rows']} | duplicates {m['duplicate_rows']} | rows out {m['rows_out']}")
    print(f"matches the problems injected in step 1: {ok}")
    print(f"daily table reconciles with cleaned data: {m['reconciliation']['files_match'] and m['reconciliation']['messages_match']}")
    print(f"{len(m['partitions_written'])} daily partitions written")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "run_manifest.json").write_text(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
