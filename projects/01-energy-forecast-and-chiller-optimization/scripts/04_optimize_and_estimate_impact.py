"""Step 4: turn the forecast into plant decisions and estimate the energy and cost impact.

    python scripts/04_optimize_and_estimate_impact.py

Three ways to run the plant over the test block:
  baseline         naive fixed-order rule, load shared by capacity
  forecast-planned the units are chosen from the FORECAST, then load is split for the ACTUAL demand
  oracle           the units are chosen knowing the actual demand (the best that is possible)

The gap between the last two is what forecast error costs. The tariff below is an
assumption for illustration. Replace it with the facility's real rate.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chiller_opt import baseline_dispatch, default_plant, optimize_dispatch  # noqa: E402

TARIFF_USD_PER_KWH = 0.12   # ASSUMPTION - illustrative only
HOURS_PER_YEAR = 8760
MIN_DEMAND, MAX_DEMAND = 250.0, 2400.0


def main() -> None:
    plant = default_plant()
    pred = pd.read_csv(ROOT / "reports" / "test_predictions.csv", parse_dates=["timestamp"])
    actual = pred["load_kw"].clip(MIN_DEMAND, MAX_DEMAND)
    forecast = pred["forecast_kw"].clip(MIN_DEMAND, MAX_DEMAND)

    base_kwh = oracle_kwh = planned_kwh = 0.0
    fallbacks = 0
    for a, f in zip(actual, forecast):
        base_kwh += baseline_dispatch(plant, a).power_kw
        oracle_kwh += optimize_dispatch(plant, a).power_kw
        plan = optimize_dispatch(plant, f)
        try:
            planned_kwh += optimize_dispatch(plant, a, on_set=list(plan.loads_kw)).power_kw
        except ValueError:                       # the planned units cannot carry the real load
            planned_kwh += optimize_dispatch(plant, a).power_kw
            fallbacks += 1

    scale = HOURS_PER_YEAR / len(pred)
    rows = []
    for name, kwh in [("baseline", base_kwh), ("forecast-planned", planned_kwh), ("oracle", oracle_kwh)]:
        saved = base_kwh - kwh
        rows.append({"strategy": name, "kwh_in_test_block": round(kwh),
                     "saving_vs_baseline_pct": round(100 * saved / base_kwh, 2),
                     "annualised_kwh_saved": round(saved * scale),
                     "annualised_usd_saved": round(saved * scale * TARIFF_USD_PER_KWH)})
    table = pd.DataFrame(rows)
    print(f"Test block: {len(pred)} hours. Tariff assumption: ${TARIFF_USD_PER_KWH}/kWh")
    print(table.to_string(index=False))
    print(f"Hours where the forecast plan had to be overridden: {fallbacks} of {len(pred)}")
    lost = oracle_kwh - planned_kwh
    print(f"Energy given up to forecast error (oracle vs forecast-planned): {-lost:,.0f} kWh in the block")

    # Compare the two solvers on one day.
    day = actual.iloc[:24]
    solver_rows = []
    for solver in ("slsqp", "de"):
        start = time.perf_counter()
        kwh = sum(optimize_dispatch(plant, d, solver=solver).power_kw for d in day)
        solver_rows.append({"solver": solver, "kwh_over_24h": round(kwh, 1),
                            "seconds": round(time.perf_counter() - start, 2)})
    solvers = pd.DataFrame(solver_rows)
    print("\nSolver comparison on 24 hours:")
    print(solvers.to_string(index=False))

    table.to_csv(ROOT / "reports" / "impact.csv", index=False)
    solvers.to_csv(ROOT / "reports" / "solver_comparison.csv", index=False)
    (ROOT / "reports" / "impact_assumptions.json").write_text(json.dumps(
        {"tariff_usd_per_kwh": TARIFF_USD_PER_KWH, "note": "assumption, not a measured rate",
         "fallback_hours": fallbacks, "test_hours": len(pred)}, indent=2))


if __name__ == "__main__":
    main()
