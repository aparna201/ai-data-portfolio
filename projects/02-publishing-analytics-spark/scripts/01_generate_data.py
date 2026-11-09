"""Step 1: create the sample raw publish events (92 days, with known problems).

    python scripts/01_generate_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from publishing_etl.sample_data import generate_sample  # noqa: E402


def main() -> None:
    path, counts = generate_sample(ROOT / "data" / "sample")
    (ROOT / "data" / "sample" / "injected_counts.json").write_text(json.dumps(counts, indent=2))
    print(f"{counts['rows_in']} raw rows written to {path.relative_to(ROOT)}")
    print(f"  {counts['good_rows']} good | {counts['duplicates']} duplicate deliveries | "
          f"{counts['invalid_rows']} invalid ({counts['missing_platform']} no platform, "
          f"{counts['negative_messages']} negative count, {counts['bad_timestamp']} bad timestamp)")


if __name__ == "__main__":
    main()
