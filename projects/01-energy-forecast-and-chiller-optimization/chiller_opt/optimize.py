"""Dispatch optimization: which chillers to run, and how to split the load.

This is a small mixed-integer nonlinear program (MINLP):
  * integer part  - which chillers are ON (enumerated; fine for a handful of units)
  * nonlinear part - how to split the cooling demand across the ON chillers (SLSQP)
"""
from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import differential_evolution, minimize

from .plant import Chiller


@dataclass
class Dispatch:
    loads_kw: dict[str, float]   # chiller name -> cooling load (ON units only)
    power_kw: float              # total electrical power


def _total_power(x, active: list[Chiller]) -> float:
    return sum(c.power_kw(load) for c, load in zip(active, x))


def baseline_dispatch(chillers: list[Chiller], demand_kw: float) -> Dispatch:
    """Naive rule: switch units on in fixed order until capacity covers demand,
    then split load in proportion to capacity."""
    active, capacity = [], 0.0
    for c in chillers:
        active.append(c)
        capacity += c.capacity_kw
        if capacity >= demand_kw:
            break
    if capacity < demand_kw:
        raise ValueError(f"Demand {demand_kw:.0f} kW exceeds plant capacity {capacity:.0f} kW")
    loads = [demand_kw * c.capacity_kw / capacity for c in active]
    return Dispatch({c.name: l for c, l in zip(active, loads)}, _total_power(loads, active))


def _split_slsqp(active, demand_kw, bounds):
    """Gradient-based split of the demand across the ON units. Fast; finds a local optimum."""
    hi = sum(c.capacity_kw for c in active)
    x0 = [demand_kw * c.capacity_kw / hi for c in active]
    balance = {"type": "eq", "fun": lambda x, d=demand_kw: np.sum(x) - d}
    res = minimize(_total_power, x0, args=(active,), method="SLSQP",
                   bounds=bounds, constraints=[balance])
    return (res.x, float(res.fun)) if res.success else (None, None)


def _split_de(active, demand_kw, bounds):
    """Differential evolution split. Global search, so slower. The last unit takes
    whatever the others leave, which keeps the load balance exact."""
    if len(active) == 1:
        lo, hi = bounds[0]
        return ([demand_kw], _total_power([demand_kw], active)) if lo <= demand_kw <= hi else (None, None)

    def objective(z):
        last = demand_kw - float(np.sum(z))
        lo, hi = bounds[-1]
        penalty = 1e6 * max(lo - last, last - hi, 0.0)
        return _total_power([*z, last], active) + penalty

    res = differential_evolution(objective, bounds[:-1], seed=0, maxiter=60, popsize=10,
                                 tol=1e-8, polish=False)
    x = np.array([*res.x, demand_kw - float(np.sum(res.x))])
    lo_last, hi_last = bounds[-1]
    if not lo_last - 1e-6 <= x[-1] <= hi_last + 1e-6:
        return None, None
    return x, float(_total_power(x, active))


SOLVERS = {"slsqp": _split_slsqp, "de": _split_de}


def optimize_dispatch(chillers: list[Chiller], demand_kw: float,
                      on_set: list[str] | None = None, solver: str = "slsqp") -> Dispatch:
    """Return the lowest-power feasible dispatch for the given demand.

    on_set: only consider running exactly these chillers (used when the plan was fixed
            earlier from a forecast). solver: "slsqp" or "de".
    """
    split = SOLVERS[solver]
    best: Dispatch | None = None
    for on in product([0, 1], repeat=len(chillers)):
        active = [c for c, flag in zip(chillers, on) if flag]
        if not active:
            continue
        if on_set is not None and {c.name for c in active} != set(on_set):
            continue
        lo = sum(c.min_plr * c.capacity_kw for c in active)
        hi = sum(c.capacity_kw for c in active)
        if not lo <= demand_kw <= hi:
            continue  # this ON/OFF combination cannot serve the demand

        bounds = [(c.min_plr * c.capacity_kw, c.capacity_kw) for c in active]
        x, power = split(active, demand_kw, bounds)
        if x is not None and abs(np.sum(x) - demand_kw) < 1e-3:
            if best is None or power < best.power_kw:
                best = Dispatch({c.name: float(l) for c, l in zip(active, x)}, power)

    if best is None:
        raise ValueError(f"No feasible dispatch for demand {demand_kw:.0f} kW")
    return best
