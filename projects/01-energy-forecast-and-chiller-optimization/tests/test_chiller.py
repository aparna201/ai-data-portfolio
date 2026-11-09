import pytest

from chiller_opt import baseline_dispatch, default_plant, optimize_dispatch


@pytest.mark.parametrize("demand", range(300, 2401, 100))
def test_optimized_never_worse_than_baseline(demand):
    plant = default_plant()
    base = baseline_dispatch(plant, demand)
    opt = optimize_dispatch(plant, demand)
    assert opt.power_kw <= base.power_kw * (1 + 1e-6)


@pytest.mark.parametrize("demand", [300, 900, 1750, 2400])
def test_loads_meet_demand_and_respect_limits(demand):
    plant = {c.name: c for c in default_plant()}
    opt = optimize_dispatch(list(plant.values()), demand)
    assert sum(opt.loads_kw.values()) == pytest.approx(demand, abs=1e-2)
    for name, load in opt.loads_kw.items():
        c = plant[name]
        assert c.min_plr * c.capacity_kw - 1e-6 <= load <= c.capacity_kw + 1e-6


def test_demand_above_capacity_is_rejected():
    with pytest.raises(ValueError):
        optimize_dispatch(default_plant(), 5000)
    with pytest.raises(ValueError):
        baseline_dispatch(default_plant(), 5000)
