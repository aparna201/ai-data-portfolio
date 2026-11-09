"""Step 1: create the labeled sample metrics.

    python scripts/alerts_01_generate_data.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observability.labeled_data import make_labeled_series  # noqa: E402


def main() -> None:
    df = make_labeled_series()
    out = ROOT / "data" / "sample" / "labeled_metrics.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{df['series_id'].nunique()} series x {df['day'].nunique()} days = {len(df):,} rows")
    print(f"{int(df['is_anomaly'].sum())} labeled anomalies ({df['is_anomaly'].mean():.1%} of days)")
    print(f"written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
