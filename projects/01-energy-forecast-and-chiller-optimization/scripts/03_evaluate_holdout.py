"""Step 3: run the chosen model once on the held-out test block and score it.

    python scripts/03_evaluate_holdout.py
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

from chiller_opt.forecast import BASELINES, FEATURES, TARGET, make_features, metrics, split_by_time  # noqa: E402


def main() -> None:
    raw = pd.read_csv(ROOT / "data" / "sample" / "cooling_load.csv", parse_dates=["timestamp"])
    _, _, test = split_by_time(make_features(raw))
    model = joblib.load(ROOT / "models" / "best_model.joblib")
    winner = json.loads((ROOT / "reports" / "split_info.json").read_text())["winner"]

    test = test.copy()
    test["forecast_kw"] = model.predict(test[FEATURES])

    scores = {winner: metrics(test[TARGET], test["forecast_kw"])}
    for name, column in BASELINES.items():
        scores[name] = metrics(test[TARGET], test[column])

    print(f"Test block: {test['timestamp'].min()} to {test['timestamp'].max()} ({len(test)} hours)\n")
    print(pd.DataFrame(scores).T.round(2).to_string())
    best_baseline = min(BASELINES, key=lambda b: scores[b]["mae_kw"])
    gain = 100 * (1 - scores[winner]["mae_kw"] / scores[best_baseline]["mae_kw"])
    print(f"\n{winner} cuts MAE by {gain:.0f}% versus the best simple baseline ({best_baseline}).")

    (ROOT / "reports" / "test_metrics.json").write_text(json.dumps(
        {"winner": winner, "scores": scores, "mae_gain_vs_best_baseline_pct": round(gain, 1)}, indent=2))
    test[["timestamp", TARGET, "forecast_kw"]].to_csv(ROOT / "reports" / "test_predictions.csv", index=False)

    week = test.iloc[: 24 * 7]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(week["timestamp"], week[TARGET], label="actual", color="#222222", linewidth=1.6)
    ax.plot(week["timestamp"], week["forecast_kw"], label=winner, color="#1f77b4", linewidth=1.2)
    ax.plot(week["timestamp"], week["lag_168"], label="same hour last week", color="#bbbbbb",
            linewidth=1, linestyle="--")
    ax.set_ylabel("cooling load (kW)")
    ax.set_title("Held-out test week: actual vs forecast")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    (ROOT / "reports" / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(ROOT / "reports" / "figures" / "test_forecast.png", dpi=130)
    print("Saved reports/test_metrics.json, test_predictions.csv and figures/test_forecast.png")


if __name__ == "__main__":
    main()
