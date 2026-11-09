"""Synthetic daily pipeline metrics with three injected problems."""
import numpy as np

DAYS = 30
ROW_COUNT_DROP_DAY = 27
NULL_SPIKE_DAY = 25
STALE_DAY = 29


def make_metrics(seed: int = 7) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    row_count = rng.normal(100_000, 1_500, DAYS)
    null_rate = rng.normal(0.010, 0.0008, DAYS)
    freshness = rng.normal(2.0, 0.15, DAYS)

    row_count[ROW_COUNT_DROP_DAY] = 52_000   # half the rows went missing
    null_rate[NULL_SPIKE_DAY] = 0.060        # a column suddenly full of nulls
    freshness[STALE_DAY] = 9.5               # data arrived hours late

    return {
        "clean_transactions.row_count": row_count.tolist(),
        "clean_transactions.null_rate": null_rate.tolist(),
        "daily_summary.freshness_hours": freshness.tolist(),
    }
