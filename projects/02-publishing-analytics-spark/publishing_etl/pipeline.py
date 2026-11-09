"""The pipeline: read raw files, validate, deduplicate, aggregate, write, reconcile, report.

    raw CSV --> parse_and_validate --> dedupe_events --> daily_publishing --> parquet (by day)
                     |                                          |                    |
              quality gate (stop if too             reconciliation: do the    run manifest (JSON)
              many bad rows)                        daily totals equal the
                                                    cleaned totals?
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .spark import get_spark
from .transform import RAW_SCHEMA, daily_publishing, dedupe_events, parse_and_validate


class DataQualityError(ValueError):
    """Raised when too many raw rows are invalid to trust the load."""


def run(input_dir: str | Path, warehouse_dir: str | Path, spark: SparkSession | None = None,
        max_invalid_ratio: float = 0.2) -> dict:
    """Process every CSV in `input_dir` and write the daily table under `warehouse_dir`.

    Re-running with the same input gives the same result: each day's partition is replaced, not
    appended to. Returns the run manifest (also saved as _manifest.json).
    """
    spark = spark or get_spark()
    warehouse = Path(warehouse_dir)
    warehouse.mkdir(parents=True, exist_ok=True)

    source = Path(input_dir)
    source = source / "*.csv" if source.is_dir() else source          # read only CSVs, ignore other files
    raw = spark.read.option("header", True).schema(RAW_SCHEMA).csv(str(source))
    rows_in = raw.count()
    valid = parse_and_validate(raw).cache()
    rows_valid = valid.count()
    deduped = dedupe_events(valid).cache()
    clean = deduped.agg(F.count("*").alias("files"), F.sum("message_count").alias("messages")).first()
    rows_out = clean["files"]

    manifest = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "rows_in": rows_in,
        "invalid_rows": rows_in - rows_valid,
        "duplicate_rows": rows_valid - rows_out,
        "rows_out": rows_out,
        "status": "success",
        "partitions_written": [],
    }

    invalid_ratio = manifest["invalid_rows"] / rows_in if rows_in else 1.0
    if invalid_ratio > max_invalid_ratio:
        manifest["status"] = "failed"
        manifest["reason"] = f"invalid ratio {invalid_ratio:.1%} exceeds limit {max_invalid_ratio:.1%}"
        _save(warehouse, manifest)
        valid.unpersist(), deduped.unpersist()
        raise DataQualityError(manifest["reason"])

    table_path = str(warehouse / "daily_publishing")
    daily = daily_publishing(deduped)
    daily.write.mode("overwrite").partitionBy("publish_date").parquet(table_path)
    manifest["partitions_written"] = sorted(
        r["publish_date"].isoformat() for r in daily.select("publish_date").distinct().collect())

    # Reconciliation: re-read what was written and compare totals with the cleaned data.
    written = spark.read.parquet(table_path).agg(F.sum("files").alias("f"), F.sum("messages").alias("m")).first()
    manifest["reconciliation"] = {"files_match": written["f"] == clean["files"],
                                  "messages_match": written["m"] == clean["messages"],
                                  "total_files": clean["files"], "total_messages": clean["messages"]}
    if not all([manifest["reconciliation"]["files_match"], manifest["reconciliation"]["messages_match"]]):
        manifest["status"] = "failed"
        manifest["reason"] = "daily table totals do not match cleaned data"

    valid.unpersist(), deduped.unpersist()
    _save(warehouse, manifest)
    return manifest


def _save(warehouse: Path, manifest: dict) -> None:
    (warehouse / "_manifest.json").write_text(json.dumps(manifest, indent=2))
