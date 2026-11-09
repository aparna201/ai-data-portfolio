from observability import build_report, find_anomalies
from observability.sample_data import (NULL_SPIKE_DAY, ROW_COUNT_DROP_DAY, STALE_DAY,
                                       make_metrics)


def test_injected_problems_are_detected():
    found = {(a.metric, a.index) for a in find_anomalies(make_metrics())}
    assert ("clean_transactions.row_count", ROW_COUNT_DROP_DAY) in found
    assert ("clean_transactions.null_rate", NULL_SPIKE_DAY) in found
    assert ("daily_summary.freshness_hours", STALE_DAY) in found


def test_stable_series_has_no_anomalies():
    series = {"m": [10, 10.1, 9.9, 10.05, 9.95] * 6}
    assert find_anomalies(series) == []


def test_flat_series_with_one_jump_is_flagged():
    series = {"m": [100.0] * 25 + [160.0]}
    anomalies = find_anomalies(series)
    assert [a.index for a in anomalies] == [25]


def test_report_lists_anomalies_and_handles_none():
    report = build_report(find_anomalies(make_metrics()))
    assert "Anomalies found" in report and "| Metric |" in report
    assert "within normal range" in build_report([])
