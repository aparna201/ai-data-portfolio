"""Command line entry point.

    python -m receivables_agent --bills data/bills.csv --as-of 2026-11-08      # dry run (default)
    python -m receivables_agent --bills data/bills.csv --send                  # real send
"""
import argparse
from datetime import date, datetime

from .agent import run


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--bills", required=True)
    p.add_argument("--as-of", help="YYYY-MM-DD (default: today)")
    p.add_argument("--outbox", default="outbox")
    p.add_argument("--manager-email", default="accounts-manager@example.com")
    p.add_argument("--send", action="store_true",
                   help="send via SMTP (needs MAIL_FROM, SMTP_HOST, SMTP_USER, SMTP_PASSWORD) and update the sheet")
    a = p.parse_args()
    as_of = datetime.strptime(a.as_of, "%Y-%m-%d").date() if a.as_of else date.today()
    r = run(a.bills, as_of, a.outbox, a.send, a.manager_email)
    mode = "sent" if a.send else "drafted (dry run)"
    print(f"{len(r.reminders)} reminder(s) and {len(r.alerts)} manager alert(s) {mode}")
    for m in r.reminders + r.alerts:
        print(f"  {m.kind:13s} {m.invoice_no}  -> {m.to}")
    for inv, why in r.skipped.items():
        print(f"  skipped       {inv}  ({why})")


if __name__ == "__main__":
    main()
