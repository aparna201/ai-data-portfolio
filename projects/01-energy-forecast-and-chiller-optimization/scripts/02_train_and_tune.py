"""Step 2: split the data, tune each model, pick a winner on the validation block.

    python scripts/02_train_and_tune.py

The test block is not touched here. It is used once, in step 3.
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chiller_opt.forecast import FEATURES, TARGET, make_features, split_by_time, tune_and_select  # noqa: E402


def main() -> None:
    raw = pd.read_csv(ROOT / "data" / "sample" / "cooling_load.csv", parse_dates=["timestamp"])
    data = make_features(raw)
    train, val, test = split_by_time(data)
    print(f"train {len(train)} rows | validation {len(val)} | test {len(test)} (held out)")
    print(f"train ends {train['timestamp'].max()} | test starts {test['timestamp'].min()}\n")

    table, winner, fitted = tune_and_select(train, val)
    print(table.drop(columns="best_params").round(2).to_string(index=False))
    print(f"\nWinner on validation MAE: {winner}")
    print(f"Winner parameters: {table[table['model'] == winner].iloc[0]['best_params']}")

    # Refit the winner on train + validation before the final test, using the tuned settings.
    final = clone(fitted[winner]).fit(pd.concat([train, val])[FEATURES],
                                      pd.concat([train, val])[TARGET])

    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    joblib.dump(final, ROOT / "models" / "best_model.joblib")
    table.to_csv(ROOT / "reports" / "model_comparison.csv", index=False)
    (ROOT / "reports" / "split_info.json").write_text(json.dumps({
        "winner": winner,
        "train_rows": len(train), "validation_rows": len(val), "test_rows": len(test),
        "test_start": str(test["timestamp"].min()), "test_end": str(test["timestamp"].max()),
    }, indent=2))
    print("\nSaved models/best_model.joblib and reports/model_comparison.csv")


if __name__ == "__main__":
    main()
