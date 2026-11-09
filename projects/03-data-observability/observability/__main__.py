"""Demo: detect the injected anomalies and write report.md.

    python -m observability --out report.md
"""
import argparse
from pathlib import Path

from .detect import find_anomalies
from .report import build_report
from .sample_data import make_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="report.md")
    args = parser.parse_args()

    report = build_report(find_anomalies(make_metrics()))
    Path(args.out).write_text(report)
    print(report)


if __name__ == "__main__":
    main()
