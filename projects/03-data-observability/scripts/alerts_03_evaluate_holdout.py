"""Step 3: score every method, with its tuned threshold, on the unseen test series.

    python scripts/alerts_03_evaluate_holdout.py
"""
import json
import sys
from pathlib import Path

import joblib
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observability.benchmark import METHODS, evaluate, score_all  # noqa: E402

TEST_IDS = range(32, 40)


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "sample" / "labeled_metrics.csv")
    test = df[df["series_id"].isin(TEST_IDS)]
    cfg = json.loads((ROOT / "reports" / "chosen_thresholds.json").read_text())
    forest = joblib.load(ROOT / "models" / "isolation_forest.joblib")

    rows, scored_by_method = [], {}
    for method in METHODS:
        scored = score_all(test, method, forest if method == "isolation_forest" else None)
        scored_by_method[method] = scored
        rows.append({"method": method, **evaluate(scored, cfg["thresholds"][method])})
    table = pd.DataFrame(rows).sort_values("f1", ascending=False).reset_index(drop=True)

    print(f"Test series {TEST_IDS.start}-{TEST_IDS.stop - 1}: {int(test['is_anomaly'].sum())} real anomalies\n")
    print(table.to_string(index=False))
    table.to_csv(ROOT / "reports" / "test_comparison.csv", index=False)

    best = table.iloc[0]["method"]
    scored = scored_by_method[best]
    sid = int(scored[scored["is_anomaly"] == 1]["series_id"].iloc[0])
    g = scored[scored["series_id"] == sid]
    flagged = g[g["score"] > cfg["thresholds"][best]]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(g["day"], g["value"], color="#444444", linewidth=1)
    ax.scatter(g[g["is_anomaly"] == 1]["day"], g[g["is_anomaly"] == 1]["value"], s=90,
               facecolors="none", edgecolors="#2ca02c", linewidths=2, label="real anomaly")
    ax.scatter(flagged["day"], flagged["value"], marker="x", color="#d62728", label=f"flagged ({best})")
    ax.set_xlabel("day")
    ax.set_ylabel("metric value")
    ax.set_title(f"Held-out test series {sid}")
    ax.legend(frameon=False)
    fig.tight_layout()
    (ROOT / "reports" / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(ROOT / "reports" / "figures" / "test_series.png", dpi=130)
    print(f"\nBest on test: {best}. Saved reports/test_comparison.csv and figures/test_series.png")


if __name__ == "__main__":
    main()
