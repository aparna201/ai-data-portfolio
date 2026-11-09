"""Demo: compare the naive dispatch with the optimized one over a synthetic day.

    python -m chiller_opt --out results/dispatch.csv
"""
import argparse
import csv
from pathlib import Path

import numpy as np

from .optimize import baseline_dispatch, optimize_dispatch
from .plant import default_plant


def synthetic_load(hours: int = 24, seed: int = 3) -> np.ndarray:
    """A made-up daily cooling-demand curve (kW), peaking mid-afternoon."""
    rng = np.random.default_rng(seed)
    t = np.arange(hours)
    base = 1100 + 800 * np.sin((t - 9) / 24 * 2 * np.pi)
    return np.clip(base + rng.normal(0, 60, hours), 300, 2300)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="results/dispatch.csv")
    args = parser.parse_args()

    plant = default_plant()
    rows, base_kwh, opt_kwh = [], 0.0, 0.0
    for hour, demand in enumerate(synthetic_load()):
        base = baseline_dispatch(plant, demand)
        opt = optimize_dispatch(plant, demand)
        base_kwh += base.power_kw   # 1-hour steps, so kW == kWh
        opt_kwh += opt.power_kw
        rows.append({
            "hour": hour,
            "demand_kw": round(demand, 1),
            "baseline_kw": round(base.power_kw, 1),
            "optimized_kw": round(opt.power_kw, 1),
            "units_on": " ".join(opt.loads_kw),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    saving = 100 * (base_kwh - opt_kwh) / base_kwh
    print(f"Baseline : {base_kwh:,.0f} kWh/day")
    print(f"Optimized: {opt_kwh:,.0f} kWh/day")
    print(f"Saving   : {saving:.1f}%  (synthetic plant and load - illustrative only)")
    print(f"Hourly detail written to {out}")


if __name__ == "__main__":
    main()
