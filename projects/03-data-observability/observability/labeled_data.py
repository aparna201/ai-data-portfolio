"""Synthetic pipeline metrics WITH answer labels, so detectors can be scored.

Each series is a daily metric (row count, spend, latency...) with a weekly rhythm, noise,
and a few injected problems. We know exactly which days are anomalies, so we can measure
precision and recall instead of eyeballing charts.
"""
import numpy as np
import pandas as pd

N_SERIES = 40
DAYS = 120
ANOMALIES_PER_SERIES = 3
FIRST_ANOMALY_DAY = 30      # leave enough history before the first problem


def make_labeled_series(n_series: int = N_SERIES, days: int = DAYS, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for sid in range(n_series):
        level = 10 ** rng.uniform(2, 5)                      # metrics live on very different scales
        weekly = 0.04 * level * np.sin(2 * np.pi * np.arange(days) / 7 + rng.uniform(0, 6.28))
        noise = rng.normal(0, 0.015 * level, days)
        values = level + weekly + noise

        # Pick problem days at least 5 days apart.
        days_hit: list[int] = []
        while len(days_hit) < ANOMALIES_PER_SERIES:
            d = int(rng.integers(FIRST_ANOMALY_DAY, days))
            if all(abs(d - other) > 5 for other in days_hit):
                days_hit.append(d)
        labels = np.zeros(days, dtype=int)
        for d in days_hit:
            size = rng.uniform(0.12, 0.50) * level            # from subtle to obvious
            values[d] += size * rng.choice([-1, 1])
            labels[d] = 1

        rows.append(pd.DataFrame({"series_id": sid, "day": np.arange(days),
                                  "value": values.round(3), "is_anomaly": labels}))
    return pd.concat(rows, ignore_index=True)
