import json

import pytest

pytest.importorskip("pyspark")  # the other projects' tests do not need Spark

from publishing_etl.pipeline import DataQualityError, run  # noqa: E402
from publishing_etl.sample_data import generate_sample  # noqa: E402
from publishing_etl.spark import get_spark  # noqa: E402
from publishing_etl.transform import (RAW_SCHEMA, daily_publishing, dedupe_events,  # noqa: E402
                                      parse_and_validate)


@pytest.fixture(scope="session")
def spark():
    session = get_spark("tests")
    yield session
    session.stop()


def frame(spark, rows):
    return spark.createDataFrame(rows, RAW_SCHEMA)


GOOD = ("F1", "Managed", "API", "Spark", "2026-10-01 10:00:00", "1000")


def test_validation_keeps_good_rows_and_rejects_bad_ones(spark):
    df = frame(spark, [
        GOOD,
        ("F2", None, "api", "spark", "2026-10-01 10:00:00", "5"),            # no platform
        ("F3", "managed", "api", "spark", "2026-10-01 10:00:00", "-5"),      # negative messages
        ("F4", "managed", "api", "spark", "yesterday", "5"),                 # bad timestamp
        ("F5", "managed", "api", "spark", "2026-10-01 10:00:00", "abc"),     # non-numeric
        ("F6", "managed", "api", "mystery", "2026-10-01 10:00:00", "5"),     # unknown engine
    ])
    kept = parse_and_validate(df).collect()
    assert [r["file_id"] for r in kept] == ["F1"]
    assert (kept[0]["platform"], kept[0]["engine"]) == ("managed", "spark")      # normalised to lower case
    assert kept[0]["publish_date"].isoformat() == "2026-10-01"


def test_dedupe_removes_repeated_file_ids(spark):
    df = parse_and_validate(frame(spark, [GOOD, GOOD, ("F2", "managed", "api", "legacy", "2026-10-01 11:00:00", "1")]))
    assert dedupe_events(df).count() == 2


def test_daily_publishing_sums_per_day_and_keys(spark):
    df = parse_and_validate(frame(spark, [
        ("F1", "managed", "api", "spark", "2026-10-01 10:00:00", "100"),
        ("F2", "managed", "api", "spark", "2026-10-01 23:00:00", "250"),
        ("F3", "managed", "api", "legacy", "2026-10-01 23:30:00", "40"),
        ("F4", "managed", "api", "spark", "2026-10-02 00:30:00", "10"),
    ]))
    got = {(r["publish_date"].isoformat(), r["engine"]): (r["files"], r["messages"])
           for r in daily_publishing(df).collect()}
    assert got == {("2026-10-01", "spark"): (2, 350), ("2026-10-01", "legacy"): (1, 40),
                   ("2026-10-02", "spark"): (1, 10)}


@pytest.fixture(scope="module")
def sample_run(spark, tmp_path_factory):
    base = tmp_path_factory.mktemp("run")
    _, counts = generate_sample(base / "raw")
    return base, counts, run(base / "raw", base / "wh", spark)


def test_pipeline_reports_exact_counts_for_sample_data(sample_run):
    _, counts, m = sample_run
    assert m["rows_in"] == counts["rows_in"]
    assert m["invalid_rows"] == counts["invalid_rows"]
    assert m["duplicate_rows"] == counts["duplicates"]
    assert m["rows_out"] == counts["good_rows"]
    assert len(m["partitions_written"]) == 92 and m["status"] == "success"


def test_daily_table_reconciles_with_cleaned_data(sample_run):
    base, counts, m = sample_run
    assert m["reconciliation"]["files_match"] and m["reconciliation"]["messages_match"]
    assert m["reconciliation"]["total_files"] == counts["good_rows"]
    assert json.loads((base / "wh" / "_manifest.json").read_text())["status"] == "success"


def test_rerunning_does_not_double_count(spark, tmp_path):
    _, counts = generate_sample(tmp_path / "raw")
    run(tmp_path / "raw", tmp_path / "wh", spark)
    run(tmp_path / "raw", tmp_path / "wh", spark)
    table = spark.read.parquet(str(tmp_path / "wh" / "daily_publishing"))
    assert table.agg({"files": "sum"}).collect()[0][0] == counts["good_rows"]


def test_quality_gate_stops_the_load(spark, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "bad.csv").write_text("file_id,platform,channel,engine,published_ts,message_count\n"
                                 "F1,,api,spark,2026-10-01 10:00:00,1\nF2,managed,api,spark,not-a-date,1\n")
    with pytest.raises(DataQualityError):
        run(raw, tmp_path / "wh", spark)
    assert json.loads((tmp_path / "wh" / "_manifest.json").read_text())["status"] == "failed"
    assert not (tmp_path / "wh" / "daily_publishing").exists()
