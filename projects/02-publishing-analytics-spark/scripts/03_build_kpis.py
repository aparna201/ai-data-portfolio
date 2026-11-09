"""Step 3: month-over-month KPIs by engine, plus the chart a dashboard tile would show.

    python scripts/03_build_kpis.py
"""
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from publishing_etl.analytics import engine_share, monthly_kpis  # noqa: E402
from publishing_etl.spark import get_spark  # noqa: E402

COLORS = {"legacy": "#8a8f98", "spark": "#1f77b4"}


def main() -> None:
    spark = get_spark("kpis")
    rows = spark.read.parquet(str(ROOT / "warehouse" / "daily_publishing")).collect()
    daily = pd.DataFrame([r.asDict() for r in rows])

    by_engine = monthly_kpis(daily, ["engine"])
    total = monthly_kpis(daily)
    share = engine_share(daily)
    out = ROOT / "reports"
    by_engine.to_csv(out / "monthly_kpis_by_engine.csv", index=False)
    total.to_csv(out / "monthly_kpis_total.csv", index=False)
    share.to_csv(out / "engine_share.csv")

    print("Total, all engines (MoM on per-day average):")
    print(total[["month", "files", "messages", "messages_per_day", "messages_mom_pct"]].to_string(index=False))
    print("\nBy engine:")
    print(by_engine[["month", "engine", "files", "messages", "messages_per_day", "messages_mom_pct"]].to_string(index=False))
    print("\nSpark engine share of messages (%):")
    print(share.to_string())

    months = sorted(by_engine["month"].unique())
    fig, ax = plt.subplots(figsize=(8, 4.2))
    width = 0.38
    for i, engine in enumerate(["legacy", "spark"]):
        d = by_engine[by_engine["engine"] == engine].set_index("month").reindex(months)
        xs = [m + (i - 0.5) * width for m in range(len(months))]
        ax.bar(xs, d["messages_per_day"] / 1e3, width, color=COLORS[engine], label=engine)
        for x, v, mom in zip(xs, d["messages_per_day"] / 1e3, d["messages_mom_pct"]):
            label = f"{v:,.0f}K" + ("" if pd.isna(mom) else f"\n{mom:+.0f}% MoM")
            ax.text(x, v, label, ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(months)), months)
    ax.set_ylabel("messages per day (thousands)")
    ax.set_title("Daily messages published, by execution engine (synthetic data)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    fig.tight_layout()
    (out / "figures").mkdir(exist_ok=True)
    fig.savefig(out / "figures" / "mom_messages_by_engine.png", dpi=140)
    print("\nSaved reports/monthly_kpis_*.csv, engine_share.csv and figures/mom_messages_by_engine.png")
    spark.stop()


if __name__ == "__main__":
    main()
