"""Ask a question as a given role.

    python -m clinic_query --role billing "how many unpaid invoices"
    python -m clinic_query --role front_desk "list appointments for Dr Rao"
    python -m clinic_query --role front_desk "total unpaid invoices"     # denied
"""
import argparse
from pathlib import Path

from .db import create_demo_db
from .policy import POLICY
from .service import ClinicQuery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--role", required=True, choices=sorted(POLICY))
    parser.add_argument("--db", default="demo.db")
    parser.add_argument("--audit", default="audit.jsonl")
    args = parser.parse_args()

    if not Path(args.db).exists():
        create_demo_db(args.db)

    answer = ClinicQuery(args.db, args.audit).ask(args.role, args.question)
    if not answer.ok:
        print(f"Denied or not understood: {answer.error}")
        return
    print(" | ".join(answer.columns))
    for row in answer.rows:
        print(" | ".join(str(v) for v in row))


if __name__ == "__main__":
    main()
