"""Score the offline keyword classifier on the labeled sample replies.

    python scripts/evaluate_reply_classifier.py

The same `evaluate()` works for an LLM: pass any function `text -> intent`.
The n8n workflow uses Gemini for this step; no Gemini results are reported here because none were run.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from receivables_agent import evaluate  # noqa: E402


def main() -> None:
    with open(ROOT / "data" / "labeled_replies.csv", newline="") as f:
        samples = [(r["text"], r["intent"]) for r in csv.DictReader(f)]
    out = evaluate(samples)
    print(f"{out['n']} labeled replies | accuracy {out['accuracy']:.0%} | "
          f"needs-a-human recall {out['needs_human_recall']:.0%}\n")
    print("Recall per intent:")
    for k, v in out["per_intent_recall"].items():
        print(f"  {k:20s} {v:.0%}")
    print("\nMisclassified:")
    for text, truth, pred in out["errors"]:
        print(f"  [{truth} -> {pred}] {text}")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "reply_classifier_baseline.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
