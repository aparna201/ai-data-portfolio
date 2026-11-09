"""Tier 2: compare no-show models on synthetic appointments (chronological train / validation / test).

    python scripts/03_evaluate_no_show.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.predict import evaluate, make_appointments  # noqa: E402


def main() -> None:
    df = make_appointments()
    df.to_csv(ROOT / "data" / "appointments_synthetic.csv", index=False)
    result = evaluate(df)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "no_show_evaluation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
