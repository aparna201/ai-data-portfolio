"""Run the pipeline on generated sample data.

    python -m publishing_etl --input data/raw --warehouse warehouse --generate-sample
"""
import argparse

from .pipeline import DataQualityError, run
from .sample_data import generate_sample


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="data/raw", help="folder of raw CSV files")
    p.add_argument("--warehouse", default="warehouse", help="output folder")
    p.add_argument("--generate-sample", action="store_true", help="write synthetic raw data into --input first")
    p.add_argument("--max-invalid-ratio", type=float, default=0.2)
    a = p.parse_args()
    if a.generate_sample:
        path, counts = generate_sample(a.input)
        print(f"Sample data written to {path} ({counts['rows_in']} rows)")
    try:
        m = run(a.input, a.warehouse, max_invalid_ratio=a.max_invalid_ratio)
    except DataQualityError as exc:
        raise SystemExit(f"FAILED quality gate: {exc}")
    print(f"rows in {m['rows_in']} | invalid {m['invalid_rows']} | duplicates {m['duplicate_rows']} | rows out {m['rows_out']}")
    print(f"reconciled: {m['reconciliation']['files_match'] and m['reconciliation']['messages_match']}")
    print(f"partitions written: {len(m['partitions_written'])} days")


if __name__ == "__main__":
    main()
