"""Step 3: monthly coverage and quality KPIs, a coverage-gap list and a chart, from the unified daily table.

    python scripts/03_monthly_kpis.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from observability.kpi import coverage_gaps, monthly_kpis  # noqa: E402


def main() -> None:
    fact = pd.concat(pd.read_csv(p) for p in (ROOT / "warehouse" / "daily_fact").glob("part-*.csv"))
    out = ROOT / "reports" / "unified"
    out.mkdir(parents=True, exist_ok=True)
    k = monthly_kpis(fact)
    k.to_csv(out / "monthly_kpis.csv", index=False)
    coverage_gaps(fact).to_csv(out / "coverage_gaps.csv", index=False)
    print(k.to_string(index=False))

    fig, ax = plt.subplots(figsize=(7, 4))
    for col, label in (("lineage_pct", "lineage"), ("quality_pct", "quality checks"),
                       ("monitoring_pct", "monitoring"), ("fully_covered_pct", "all three")):
        ax.plot(k["month"], k[col], marker="o", lw=3 if col == "fully_covered_pct" else 1.5, label=label)
    ax.set_ylabel("% of critical datasets (month end)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False)
    ax.set_title("Coverage of critical datasets (synthetic)")
    fig.tight_layout()
    (out / "figures").mkdir(exist_ok=True)
    fig.savefig(out / "figures" / "coverage.png", dpi=150)


if __name__ == "__main__":
    main()
