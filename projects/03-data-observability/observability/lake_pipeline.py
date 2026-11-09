"""Run the whole unification: read four source CSVs, clean, build the daily fact, reconcile, write, report."""
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .spark import get_spark
from .unify import build_daily_fact, clean_dq, clean_lineage, clean_monitor, with_critical_flag

TABLES = ("registry", "lineage_edges", "dq_results", "monitor_enrollment")


def _read(spark, folder: Path, name: str):
    return spark.read.option("header", True).csv(str(folder / f"{name}.csv"))


def run(source_dir: str | Path, out_dir: str | Path, start: str, end: str, spark: SparkSession | None = None) -> dict:
    spark = spark or get_spark()
    src, out = Path(source_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw = {t: _read(spark, src, t) for t in TABLES}
    registry = raw["registry"].select(
        "dataset_id", "domain",
        *[F.col(c).cast("boolean").alias(c) for c in ("feeds_high_priority_use", "tagged_data_product", "has_high_priority_elements")])

    dq = clean_dq(raw["dq_results"], registry).cache()
    lineage = clean_lineage(raw["lineage_edges"], registry)
    monitor = clean_monitor(raw["monitor_enrollment"], registry)
    fact = build_daily_fact(spark, registry, lineage, dq, monitor, start, end).cache()

    dq_in, dq_out = raw["dq_results"].count(), dq.count()
    totals = fact.agg(F.sum("checks_run").alias("run"), F.sum("checks_passed").alias("passed")).first()
    clean_pass = dq.filter(F.col("status") == "pass").count()
    manifest = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "dq_rows_in": dq_in, "dq_rows_rejected": dq_in - dq_out, "dq_rows_clean": dq_out,
        "lineage_datasets": lineage.count(), "monitored_datasets": monitor.count(),
        "fact_rows": fact.count(), "datasets": registry.count(),
        "critical_datasets": with_critical_flag(registry).filter("is_critical").count(),
        # Reconciliation: every clean quality check must appear in the daily fact, no more and no fewer.
        "reconciliation": {"checks_match": totals["run"] == dq_out, "passes_match": totals["passed"] == clean_pass},
    }
    manifest["status"] = "success" if all(manifest["reconciliation"].values()) else "failed"
    fact.coalesce(1).write.mode("overwrite").option("header", True).csv(str(out / "daily_fact"))
    (out / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    dq.unpersist(), fact.unpersist()
    return manifest
