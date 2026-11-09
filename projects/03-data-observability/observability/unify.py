"""Bring three separate product databases into ONE daily table, in PySpark.

    registry ----------------------+
    lineage_edges --clean--> first day each dataset had lineage ---+
    dq_results ----clean--> checks run and passed per dataset-day -+--> daily fact: one row per dataset per day
    monitor_enrollment -clean-> first day each dataset was monitored +

The daily fact answers, for any dataset on any day: is it critical, does it have lineage, is it monitored,
how many quality checks ran, how many passed, by check type. Everything the monthly KPIs need comes from it.
"""
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

CHECK_TYPES = ("consistency", "validity", "timeliness")


def with_critical_flag(registry: DataFrame) -> DataFrame:
    """Critical = feeds a high-priority use, OR tagged to a data product, OR holds high-priority elements."""
    return registry.withColumn("is_critical", F.col("feeds_high_priority_use") | F.col("tagged_data_product")
                               | F.col("has_high_priority_elements"))


def clean_dq(dq: DataFrame, registry: DataFrame) -> DataFrame:
    """Keep rows with a known dataset, a valid check type and status and a real date; drop repeated result ids."""
    known = registry.select("dataset_id")
    return (dq.withColumn("run_date", F.to_date("run_date"))
            .filter(F.col("status").isin("pass", "fail") & F.col("check_type").isin(*CHECK_TYPES)
                    & F.col("run_date").isNotNull())
            .join(known, "dataset_id", "left_semi")
            .dropDuplicates(["result_id"]))


def clean_lineage(lineage: DataFrame, registry: DataFrame) -> DataFrame:
    """Drop edges to or from unknown datasets and self-loops. Result: first captured date per dataset."""
    known = registry.select("dataset_id")
    return (lineage.withColumn("captured_date", F.to_date("captured_date"))
            .filter((F.col("dataset_id") != F.col("upstream_dataset_id")) & F.col("captured_date").isNotNull())
            .join(known, "dataset_id", "left_semi")
            .groupBy("dataset_id").agg(F.min("captured_date").alias("lineage_from")))


def clean_monitor(monitor: DataFrame, registry: DataFrame) -> DataFrame:
    """One row per monitored dataset: the earliest enrolment date (repeats collapse)."""
    return (monitor.withColumn("enrolled_date", F.to_date("enrolled_date"))
            .join(registry.select("dataset_id"), "dataset_id", "left_semi")
            .groupBy("dataset_id").agg(F.min("enrolled_date").alias("monitored_from")))


def build_daily_fact(spark: SparkSession, registry: DataFrame, lineage_first: DataFrame, dq_clean: DataFrame,
                     monitor_first: DataFrame, start: str, end: str) -> DataFrame:
    days = spark.sql(f"SELECT explode(sequence(to_date('{start}'), to_date('{end}'), interval 1 day)) AS day")
    base = with_critical_flag(registry).select("dataset_id", "domain", "is_critical").crossJoin(days)

    per_day = dq_clean.groupBy("dataset_id", F.col("run_date").alias("day")).agg(
        F.count("*").alias("checks_run"),
        F.sum((F.col("status") == "pass").cast("int")).alias("checks_passed"),
        *[F.sum((F.col("check_type") == c).cast("int")).alias(f"{c}_run") for c in CHECK_TYPES],
        *[F.sum(((F.col("check_type") == c) & (F.col("status") == "pass")).cast("int")).alias(f"{c}_passed")
          for c in CHECK_TYPES])

    fact = (base.join(lineage_first, "dataset_id", "left").join(monitor_first, "dataset_id", "left")
            .join(per_day, ["dataset_id", "day"], "left"))
    counters = [c for c in per_day.columns if c not in ("dataset_id", "day")]
    for c in counters:
        fact = fact.withColumn(c, F.coalesce(F.col(c), F.lit(0)))
    return (fact.withColumn("has_lineage", F.col("lineage_from").isNotNull() & (F.col("day") >= F.col("lineage_from")))
            .withColumn("is_monitored", F.col("monitored_from").isNotNull() & (F.col("day") >= F.col("monitored_from")))
            .drop("lineage_from", "monitored_from"))
