"""KPI logic on a tiny hand-made daily table where the answer is known."""
import pandas as pd

from observability.kpi import coverage_gaps, monthly_kpis


def _row(ds, day, crit=True, lin=False, mon=False, run=0, passed=0):
    return {"dataset_id": ds, "domain": "card", "day": day, "is_critical": crit, "has_lineage": lin, "is_monitored": mon,
            "checks_run": run, "checks_passed": passed,
            **{f"{t}_run": run // 3 for t in ("consistency", "validity", "timeliness")},
            **{f"{t}_passed": passed // 3 for t in ("consistency", "validity", "timeliness")}}


def _fact():
    rows = [_row("A", "2026-08-01", run=3, passed=3), _row("A", "2026-08-31", lin=True, mon=True),
            _row("B", "2026-08-01"), _row("B", "2026-08-31", lin=True),
            _row("C", "2026-08-01", crit=False), _row("C", "2026-08-31", crit=False, lin=True, mon=True)]
    return pd.DataFrame(rows)


def test_fully_covered_counts_only_critical_with_all_three():
    k = monthly_kpis(_fact()).iloc[0]
    assert k["critical_datasets"] == 2          # C is not critical
    assert k["fully_covered_pct"] == 50.0       # only A has lineage + quality + monitoring
    assert k["lineage_pct"] == 100.0 and k["monitoring_pct"] == 50.0 and k["quality_pct"] == 50.0


def test_gap_list_names_what_is_missing():
    g = coverage_gaps(_fact())
    assert list(g["dataset_id"]) == ["B"] and g.iloc[0]["missing"] == "quality, monitoring"
