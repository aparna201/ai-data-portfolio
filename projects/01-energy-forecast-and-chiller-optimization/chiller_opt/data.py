"""Synthetic hourly cooling-load data for a made-up facility.

Real data would come from the plant historian (see docs/architecture.md). This generator
mimics the patterns that matter: a daily cycle, a weekday/weekend difference, and a
dependence on outdoor temperature.
"""
import numpy as np
import pandas as pd


def generate_cooling_load(days: int = 120, seed: int = 21) -> pd.DataFrame:
    """Return hourly rows: timestamp, temp_c, temp_forecast_c, load_kw."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-05-01", periods=days * 24, freq="h")
    hour = idx.hour.to_numpy()
    weekday = idx.dayofweek.to_numpy() < 5

    # Outdoor temperature: a daily swing peaking mid-afternoon, a slow warming drift, some noise.
    temp = 27 + 5 * np.sin((hour - 9) / 24 * 2 * np.pi) + 0.02 * np.arange(len(idx)) / 24 \
        + rng.normal(0, 1.0, len(idx))
    # The weather forecast the planner would have had the day before is slightly off.
    temp_forecast = temp + rng.normal(0, 0.8, len(idx))

    # Occupancy: busy working hours on weekdays, quiet weekends.
    busy = np.exp(-((hour - 13) / 4.5) ** 2)
    occupancy = np.where(weekday, 0.5 + 0.5 * busy, 0.3 + 0.2 * busy)

    load = 300 + 900 * occupancy + 55 * (temp - 24) + rng.normal(0, 60, len(idx))
    return pd.DataFrame({
        "timestamp": idx,
        "temp_c": temp.round(2),
        "temp_forecast_c": temp_forecast.round(2),
        "load_kw": np.clip(load, 250, 2300).round(1),
    })
