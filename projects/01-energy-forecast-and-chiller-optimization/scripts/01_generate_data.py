"""Step 1: create the sample dataset.

    python scripts/01_generate_data.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chiller_opt.data import generate_cooling_load  # noqa: E402


def main() -> None:
    df = generate_cooling_load()
    out = ROOT / "data" / "sample" / "cooling_load.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df):,} hourly rows ({len(df) // 24} days) -> {out.relative_to(ROOT)}")
    print(df["load_kw"].describe().round(1).to_string())


if __name__ == "__main__":
    main()
