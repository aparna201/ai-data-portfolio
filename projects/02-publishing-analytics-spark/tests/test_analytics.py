import pandas as pd

from publishing_etl.analytics import engine_share, monthly_kpis
from publishing_etl.sample_data import make_events


def daily(rows):
    return pd.DataFrame(rows, columns=["publish_date", "platform", "channel", "engine", "files", "messages"])


def test_mom_uses_per_day_average_so_month_length_does_not_distort():
    d = daily([("2026-09-01", "managed", "api", "spark", 1, 3000),     # Sep: 30 days, 3000 total -> 100/day if 30 days
               ("2026-10-01", "managed", "api", "spark", 1, 3000)])    # Oct: 3000 over 1 observed day each
    k = monthly_kpis(d)
    assert list(k["messages_per_day"]) == [3000, 3000] and k["messages_mom_pct"].iloc[1] == 0.0


def test_mom_percent_change_per_engine():
    d = daily([("2026-09-01", "m", "api", "spark", 2, 100), ("2026-10-01", "m", "api", "spark", 3, 150),
               ("2026-09-01", "m", "api", "legacy", 4, 400), ("2026-10-01", "m", "api", "legacy", 2, 200)])
    k = monthly_kpis(d, ["engine"]).set_index(["engine", "month"])
    assert k.loc[("spark", "2026-10"), "messages_mom_pct"] == 50.0
    assert k.loc[("legacy", "2026-10"), "messages_mom_pct"] == -50.0
    assert pd.isna(k.loc[("spark", "2026-09"), "messages_mom_pct"])      # first month has no prior


def test_engine_share_sums_to_100():
    d = daily([("2026-09-01", "m", "api", "spark", 1, 300), ("2026-09-02", "m", "api", "legacy", 1, 100)])
    assert engine_share(d).loc["2026-09"].sum() == 100.0


def test_synthetic_story_spark_share_grows():
    raw, _ = make_events()
    raw = raw[(raw["platform"] != "") & (raw["message_count"].astype(int) >= 0) & (raw["published_ts"] != "not-a-date")]
    raw = raw.drop_duplicates("file_id").assign(publish_date=lambda x: x["published_ts"].str[:10],
                                                 files=1, messages=lambda x: x["message_count"].astype(int))
    share = engine_share(raw)["spark"]
    assert share.is_monotonic_increasing and share.iloc[-1] > share.iloc[0] + 20


def test_per_day_average_uses_all_days_in_the_month_not_just_the_engines_active_days():
    d = daily([("2026-10-01", "m", "api", "legacy", 1, 100), ("2026-10-02", "m", "api", "spark", 1, 100),
               ("2026-10-03", "m", "api", "spark", 1, 100), ("2026-10-04", "m", "api", "spark", 1, 100)])
    k = monthly_kpis(d, ["engine"]).set_index("engine")
    assert k.loc["legacy", "days"] == 4 and k.loc["legacy", "messages_per_day"] == 25
