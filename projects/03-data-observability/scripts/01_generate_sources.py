"""Step 1: write the four synthetic source tables (registry, lineage, quality results, monitoring) as CSV.

    python scripts/01_generate_sources.py
Also writes injected_counts.json: how many bad rows were planted, so step 2 can prove it found them all.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observability.sources import make_sources  # noqa: E402


def main() -> None:
    out = ROOT / "data" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    tables, counts = make_sources()
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name:20s} {len(df):6d} rows")
    (out / "injected_counts.json").write_text(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
