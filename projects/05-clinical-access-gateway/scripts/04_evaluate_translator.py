"""Score the keyword translator on labeled questions, then run the security checks.

    python scripts/04_evaluate_translator.py [dev|test|attacks|all]

Method: rules were written first, then scored on the DEV set; only dev misses were used to improve the
rules; the TEST set is run once afterwards. A real LLM translator would be scored the same way.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clinic_query.db import create_demo_db  # noqa: E402
from clinic_query.evaluate import load, run_attacks, score_translator  # noqa: E402
from clinic_query.translate import RuleBasedTranslator  # noqa: E402


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "clinic.db"
    create_demo_db(db)
    report = {}
    for name in ("dev", "test"):
        if which in (name, "all"):
            r = score_translator(load(ROOT / "data" / f"questions_{name}.json"), RuleBasedTranslator(), db, tmp / "audit.jsonl")
            report[name] = r
            print(f"{name.upper():5s} n={r['n']}  plan accuracy {r['plan_accuracy']:.0%}  answer accuracy {r['answer_accuracy']:.0%}")
            for m in r["misses"]:
                print(f"      missed: {m}")
    if which in ("attacks", "all"):
        res = run_attacks(db)
        report["attacks"] = res
        print(f"\nSecurity checks: {sum(r['passed'] for r in res)}/{len(res)} passed")
        for r in res:
            print(f"  {'PASS' if r['passed'] else 'FAIL'}  {r['attack']}")
    if which == "all":
        (ROOT / "reports").mkdir(exist_ok=True)
        (ROOT / "reports" / "evaluation.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
