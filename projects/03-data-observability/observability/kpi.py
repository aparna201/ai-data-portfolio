"""Monthly KPIs from the unified daily table. Plain pandas: the monthly view is small.

Coverage KPI (the monthly-review style metric): of the CRITICAL datasets, what share is covered by lineage,
by quality checks, by monitoring, and by ALL THREE at month end? Plus pass rates by check type, and the list
of critical datasets that still have a gap.
"""
import pandas as pd

CHECKS = ("consistency", "validity", "timeliness")


def _prep(fact: pd.DataFrame) -> pd.DataFrame:
    f = fact.copy()
    f["day"] = pd.to_datetime(f["day"])
    f["month"] = f["day"].dt.to_period("M").astype(str)
    return f


def month_end_state(fact: pd.DataFrame) -> pd.DataFrame:
    """One row per dataset per month: lineage and monitoring at the last day, quality = any check ran that month."""
    f = _prep(fact)
    last = f.groupby("month")["day"].transform("max")
    end = f[f["day"] == last][["month", "dataset_id", "domain", "is_critical", "has_lineage", "is_monitored"]]
    ran = f.groupby(["month", "dataset_id"])["checks_run"].sum().gt(0).rename("has_quality").reset_index()
    out = end.merge(ran, on=["month", "dataset_id"])
    out["fully_covered"] = out[["has_lineage", "has_quality", "is_monitored"]].all(axis=1)
    return out


def monthly_kpis(fact: pd.DataFrame) -> pd.DataFrame:
    state = month_end_state(fact)
    crit = state[state["is_critical"]]
    cov = crit.groupby("month").agg(
        critical_datasets=("dataset_id", "count"),
        lineage_pct=("has_lineage", "mean"), quality_pct=("has_quality", "mean"),
        monitoring_pct=("is_monitored", "mean"), fully_covered_pct=("fully_covered", "mean"))
    cov[["lineage_pct", "quality_pct", "monitoring_pct", "fully_covered_pct"]] *= 100

    f = _prep(fact)
    sums = f.groupby("month")[[c for t in CHECKS for c in (f"{t}_run", f"{t}_passed")]
                              + ["checks_run", "checks_passed"]].sum()
    for t in CHECKS:
        cov[f"{t}_pass_pct"] = (sums[f"{t}_passed"] / sums[f"{t}_run"] * 100).reindex(cov.index)
    cov["overall_pass_pct"] = (sums["checks_passed"] / sums["checks_run"] * 100).reindex(cov.index)
    cov = cov.round(1)
    cov["fully_covered_change_pts"] = cov["fully_covered_pct"].diff().round(1)
    return cov.reset_index()


def coverage_gaps(fact: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    """Critical datasets missing at least one product at month end, with what is missing."""
    state = month_end_state(fact)
    month = month or state["month"].max()
    g = state[(state["month"] == month) & state["is_critical"] & ~state["fully_covered"]].copy()
    g["missing"] = g.apply(lambda r: ", ".join(n for n, ok in (("lineage", r["has_lineage"]), ("quality", r["has_quality"]),
                                                               ("monitoring", r["is_monitored"])) if not ok), axis=1)
    return g[["month", "dataset_id", "domain", "missing"]].sort_values(["domain", "dataset_id"]).reset_index(drop=True)
