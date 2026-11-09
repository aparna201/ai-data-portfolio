"""Local SparkSession for the demo. On Databricks or EMR the session already exists; skip this file."""
from pyspark.sql import SparkSession


def get_spark(app_name: str = "observability", shuffle_partitions: int = 4) -> SparkSession:
    spark = (SparkSession.builder.master("local[2]").appName(app_name)
             .config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
             .config("spark.sql.ansi.enabled", "false").getOrCreate())
    spark.conf.set("spark.sql.shuffle.partitions", str(shuffle_partitions))
    return spark
