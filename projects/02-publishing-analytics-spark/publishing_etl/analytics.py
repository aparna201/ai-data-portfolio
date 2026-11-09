"""Month-over-month KPIs from the daily table. Plain pandas: the daily table is small.

Compares execution engines ("legacy" vs "spark") the way a product team would ask:
how much did each engine publish this month, and how did that change from last month?
MoM uses the per-day average (over all days seen in that month) so months of different lengths compare fairly.
"""
import pandas as pd

KEYS = ["publish_date", "platform", "channel", "engine", "files", "messages"]


def monthly_kpis(daily: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """One row per month (and per `by` columns, e.g. ["engine"]) with totals, per-day average and MoM %."""
    by = by or []
    d = daily[KEYS].copy()
    d["publish_date"] = pd.to_datetime(d["publish_date"])
    d["month"] = d["publish_date"].dt.to_period("M").astype(str)
    out = (d.groupby(["month", *by]).agg(files=("files", "sum"), messages=("messages", "sum")).reset_index())
    # Days come from the whole table, not just the rows of one engine: an engine that was quiet on some
    # days must not look busier per day than it was.
    out["days"] = out["month"].map(d.groupby("month")["publish_date"].nunique())
    out["messages_per_day"] = (out["messages"] / out["days"]).round(0)
    out["files_per_day"] = (out["files"] / out["days"]).round(1)
    out["messages_per_file"] = (out["messages"] / out["files"]).round(0)
    out = out.sort_values([*by, "month"]).reset_index(drop=True)
    grp = out.groupby(by) if by else out
    out["messages_mom_pct"] = (grp["messages_per_day"].pct_change() * 100).round(1)
    out["files_mom_pct"] = (grp["files_per_day"].pct_change() * 100).round(1)
    return out


def engine_share(daily: pd.DataFrame) -> pd.DataFrame:
    """Each engine's share of monthly messages, in percent."""
    m = monthly_kpis(daily, ["engine"]).pivot(index="month", columns="engine", values="messages")
    return (m.div(m.sum(axis=1), axis=0) * 100).round(1)
