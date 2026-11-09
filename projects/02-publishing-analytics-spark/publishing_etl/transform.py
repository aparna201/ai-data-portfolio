"""The transformations. Each takes a DataFrame and returns one, so each is testable alone.

A "publish event" is one file published to a platform: which platform and channel it came through,
which execution engine processed it, when, and how many messages (records) it carried.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

TS_FORMAT = "yyyy-MM-dd HH:mm:ss"
ENGINES = ("legacy", "spark")

# Raw files arrive as text. Everything is read as a string, then typed and checked here.
RAW_SCHEMA = StructType([
    StructField(name, StringType(), True)
    for name in ("file_id", "platform", "channel", "engine", "published_ts", "message_count")
])


def _present(column: str):
    return F.col(column).isNotNull() & (F.col(column) != "")


def parse_and_validate(raw: DataFrame) -> DataFrame:
    """Type the raw columns and keep only valid rows.

    Valid = has file id, platform and channel; a known engine; a parseable timestamp;
    and a non-negative whole-number message count.
    """
    typed = (
        raw.withColumn("file_id", F.trim("file_id"))
        .withColumn("platform", F.lower(F.trim("platform")))
        .withColumn("channel", F.lower(F.trim("channel")))
        .withColumn("engine", F.lower(F.trim("engine")))
        .withColumn("published_ts", F.to_timestamp("published_ts", TS_FORMAT))
        .withColumn("message_count", F.col("message_count").cast("long"))
    )
    return (
        typed.filter(
            _present("file_id") & _present("platform") & _present("channel")
            & F.col("engine").isin(*ENGINES)
            & F.col("published_ts").isNotNull()
            & F.col("message_count").isNotNull() & (F.col("message_count") >= 0)
        )
        .withColumn("publish_date", F.to_date("published_ts"))
    )


def dedupe_events(df: DataFrame) -> DataFrame:
    """Drop repeated deliveries of the same file. Assumes repeats are exact copies."""
    return df.dropDuplicates(["file_id"])


def daily_publishing(df: DataFrame) -> DataFrame:
    """One row per day, platform, channel and engine: files published and messages carried."""
    return df.groupBy("publish_date", "platform", "channel", "engine").agg(
        F.count("*").alias("files"),
        F.sum("message_count").alias("messages"),
    )
