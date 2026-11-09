"""Synthetic publish events with known problems, so tests can assert exact counts.

The story baked into the data: work is moving from a legacy engine to a Spark engine month by month,
and volume grows slowly. Real volumes were billions of records a day; here they are tiny.
"""
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["file_id", "platform", "channel", "engine", "published_ts", "message_count"]
PLATFORMS, PLATFORM_P = ["managed", "distributed"], [0.65, 0.35]
CHANNELS, CHANNEL_P = ["batch_file", "api", "stream"], [0.5, 0.3, 0.2]
CHANNEL_MESSAGES = {"batch_file": 50_000, "api": 8_000, "stream": 20_000}   # typical messages per file
START = pd.Timestamp("2026-08-01")

DUPLICATE_RATE, MISSING_PLATFORM_RATE, NEGATIVE_RATE, BAD_TS_RATE = 0.03, 0.01, 0.005, 0.005


def make_events(days: int = 92, files_per_day: int = 4, seed: int = 11) -> tuple[pd.DataFrame, dict]:
    """Returns (raw table including problem rows, counts of what was injected)."""
    rng = np.random.default_rng(seed)
    day_idx = np.repeat(np.arange(days), rng.poisson(files_per_day * (1 + 0.5 * np.arange(days) / days)))
    n = len(day_idx)

    spark_share = 0.30 + 0.45 * day_idx / max(days - 1, 1)             # 30% -> 75% over the period
    engine = np.where(rng.random(n) < spark_share, "spark", "legacy")
    platform = rng.choice(PLATFORMS, n, p=PLATFORM_P)
    channel = rng.choice(CHANNELS, n, p=CHANNEL_P)
    base = np.array([CHANNEL_MESSAGES[c] for c in channel], dtype=float)
    messages = (base * np.where(engine == "spark", 1.1, 1.0) * rng.lognormal(0, 0.6, n)).astype(np.int64)
    ts = START + pd.to_timedelta(day_idx, unit="D") + pd.to_timedelta(rng.integers(0, 86_400, n), unit="s")

    good = pd.DataFrame({"file_id": [f"F{i:07d}" for i in range(n)], "platform": platform, "channel": channel,
                         "engine": engine, "published_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                         "message_count": messages.astype(str)})

    counts = {"good_rows": n, "duplicates": round(DUPLICATE_RATE * n),
              "missing_platform": max(1, round(MISSING_PLATFORM_RATE * n)),
              "negative_messages": max(1, round(NEGATIVE_RATE * n)),
              "bad_timestamp": max(1, round(BAD_TS_RATE * n))}
    counts["invalid_rows"] = counts["missing_platform"] + counts["negative_messages"] + counts["bad_timestamp"]

    dupes = good.sample(counts["duplicates"], random_state=seed)               # re-deliveries
    damaged, next_id = [], n
    for key, column, value in (("missing_platform", "platform", ""), ("negative_messages", "message_count", "-5"),
                               ("bad_timestamp", "published_ts", "not-a-date")):
        rows = good.sample(counts[key], random_state=seed + next_id).copy()
        rows["file_id"] = [f"F{next_id + i:07d}" for i in range(len(rows))]
        rows[column] = value
        next_id += len(rows)
        damaged.append(rows)
    raw = pd.concat([good, dupes, *damaged], ignore_index=True).sample(frac=1, random_state=seed)
    counts["rows_in"] = len(raw)
    return raw[COLUMNS], counts


def generate_sample(directory: str | Path, **kwargs) -> tuple[Path, dict]:
    raw, counts = make_events(**kwargs)
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "publish_events.csv"
    raw.to_csv(path, index=False)
    return path, counts
