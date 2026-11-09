"""Step 4: tuning and speed. No ML here, so "model selection" means choosing how to run the pipeline.

    python scripts/04_benchmark.py            # about a minute or two on a laptop

Two questions, answered with timings on a larger synthetic file (default 300,000 raw rows):
  1. How many shuffle partitions should the aggregation use?  (Spark defaults to 200; this data is small.)
  2. How much faster is answering the monthly question from the daily table than from the raw files?
Timings are from this machine with a local 2-core Spark. They show the pattern, not production numbers.
"""
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyspark.sql import functions as F  # noqa: E402

from publishing_etl.pipeline import run  # noqa: E402
from publishing_etl.sample_data import generate_sample  # noqa: E402
from publishing_etl.spark import get_spark  # noqa: E402
from publishing_etl.transform import RAW_SCHEMA, dedupe_events, parse_and_validate  # noqa: E402

FILES_PER_DAY = 2500            # x 92 days x growth = about 300,000 files
PARTITIONS = [2, 4, 8, 32, 200]
REPEATS = 3


def timed(fn) -> float:
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def best_of(fn, n=REPEATS) -> float:
    return min(timed(fn) for _ in range(n))


def main() -> None:
    spark = get_spark("benchmark")
    spark.sparkContext.setLogLevel("ERROR")
    work = Path(tempfile.mkdtemp(prefix="publishing_bench_"))
    path, counts = generate_sample(work / "raw", files_per_day=FILES_PER_DAY)
    print(f"{counts['rows_in']:,} raw rows ({path.stat().st_size / 1e6:.0f} MB CSV)")

    # 1. shuffle partitions
    run(work / "raw", work / "warm", spark)                              # warm-up (JIT, file cache)
    results = {}
    for n in PARTITIONS:
        spark.conf.set("spark.sql.shuffle.partitions", str(n))
        results[n] = best_of(lambda: run(work / "raw", work / f"wh_{n}", spark))
        print(f"  shuffle partitions {n:>3}: {results[n]:.2f} s")
    best_n = min(results, key=results.get)

    # 2. raw scan vs daily table for the monthly question
    spark.conf.set("spark.sql.shuffle.partitions", str(best_n))
    run(work / "raw", work / "wh", spark)
    daily_path = str(work / "wh" / "daily_publishing")

    def from_raw():
        raw = spark.read.option("header", True).schema(RAW_SCHEMA).csv(str(work / "raw" / "*.csv"))
        clean = dedupe_events(parse_and_validate(raw))
        clean.groupBy(F.date_format("publish_date", "yyyy-MM").alias("month"), "engine").agg(
            F.sum("message_count")).collect()

    def from_daily():
        spark.read.parquet(daily_path).groupBy(F.date_format("publish_date", "yyyy-MM").alias("month"), "engine").agg(
            F.sum("messages")).collect()

    raw_s, daily_s = best_of(from_raw), best_of(from_daily)
    print(f"monthly-by-engine question: raw files {raw_s:.2f} s | daily table {daily_s:.2f} s "
          f"({raw_s / daily_s:.1f}x faster)")

    out = {"raw_rows": counts["rows_in"], "csv_mb": round(path.stat().st_size / 1e6, 1),
           "shuffle_partition_seconds": {str(k): round(v, 2) for k, v in results.items()},
           "chosen_shuffle_partitions": best_n,
           "monthly_question_seconds": {"from_raw": round(raw_s, 2), "from_daily_table": round(daily_s, 2),
                                        "speedup_x": round(raw_s / daily_s, 1)},
           "note": "best of 3 runs, local 2-core Spark, synthetic data"}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "benchmark.json").write_text(json.dumps(out, indent=2))
    spark.stop()


if __name__ == "__main__":
    main()
