"""Step 2: tune a threshold for each method on validation series, then pick the best method.

    python scripts/alerts_02_tune_and_select.py

Series 0-23 are training, 24-31 validation, 32-39 test. Splitting by SERIES (not by day)
means the test series are metrics the detector has never seen at all. The test series are
not used in this step.
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observability.benchmark import (METHODS, candidate_thresholds, evaluate, fit_forest,  # noqa: E402
                                     score_all)

TRAIN_IDS, VAL_IDS = range(0, 24), range(24, 32)


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "sample" / "labeled_metrics.csv")
    train = df[df["series_id"].isin(TRAIN_IDS)]
    val = df[df["series_id"].isin(VAL_IDS)]
    forest = fit_forest(train)

    rows, chosen = [], {}
    for method in METHODS:
        f = forest if method == "isolation_forest" else None
        train_scores = score_all(train, method, f)["score"].to_numpy()
        val_scored = score_all(val, method, f)
        results = [evaluate(val_scored, t) for t in candidate_thresholds(method, train_scores)]
        best = max(results, key=lambda r: (r["f1"], -r["false_alarms_per_series_month"]))
        chosen[method] = best["threshold"]
        rows.append({"method": method, **best})

    table = pd.DataFrame(rows).sort_values("f1", ascending=False).reset_index(drop=True)
    print("Best threshold per method, chosen on validation series:\n")
    print(table.drop(columns=["tp", "fp", "fn"]).to_string(index=False))
    winner = table.iloc[0]["method"]
    print(f"\nBest on validation F1: {winner}")

    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    joblib.dump(forest, ROOT / "models" / "isolation_forest.joblib")
    table.to_csv(ROOT / "reports" / "validation_comparison.csv", index=False)
    (ROOT / "reports" / "chosen_thresholds.json").write_text(
        json.dumps({"winner": winner, "thresholds": chosen}, indent=2))


if __name__ == "__main__":
    main()
