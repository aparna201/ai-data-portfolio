import pandas as pd
import pytest

from chiller_opt import default_plant, optimize_dispatch
from chiller_opt.data import generate_cooling_load
from chiller_opt.forecast import make_features, split_by_time, tune_and_select


def test_generated_data_is_deterministic_and_in_range():
    a, b = generate_cooling_load(days=10, seed=5), generate_cooling_load(days=10, seed=5)
    pd.testing.assert_frame_equal(a, b)
    assert a["load_kw"].between(250, 2300).all()
    assert len(a) == 240


def test_features_do_not_peek_at_the_last_24_hours():
    raw = generate_cooling_load(days=20)
    feats = make_features(raw)
    row = feats.iloc[100]
    t = row["timestamp"]
    load_at = raw.set_index("timestamp")["load_kw"]
    assert row["lag_24"] == load_at[t - pd.Timedelta(hours=24)]
    assert row["lag_168"] == load_at[t - pd.Timedelta(hours=168)]
    # the rolling mean must end 24 hours back, not at t
    window = load_at[t - pd.Timedelta(hours=47): t - pd.Timedelta(hours=24)]
    assert row["mean_24_lagged"] == pytest.approx(window.mean())


def test_split_is_chronological_with_no_overlap():
    feats = make_features(generate_cooling_load(days=30))
    train, val, test = split_by_time(feats)
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()
    assert len(train) + len(val) + len(test) == len(feats)


def test_a_tuned_model_beats_the_naive_baseline_on_validation():
    feats = make_features(generate_cooling_load(days=60))
    train, val, _ = split_by_time(feats)
    table, winner, fitted = tune_and_select(train, val, quick=True)
    ml_mae = table.loc[table["model"] == winner, "val_mae_kw"].iloc[0]
    naive_mae = table.loc[table["model"] == "same_hour_yesterday", "val_mae_kw"].iloc[0]
    assert ml_mae < naive_mae
    assert winner in fitted


def test_both_solvers_find_the_same_answer():
    plant = default_plant()
    fast = optimize_dispatch(plant, 1200, solver="slsqp")
    slow = optimize_dispatch(plant, 1200, solver="de")
    assert slow.power_kw == pytest.approx(fast.power_kw, rel=0.01)


def test_on_set_restricts_which_units_run():
    plant = default_plant()
    only_ch1 = optimize_dispatch(plant, 700, on_set=["CH-1"])
    assert list(only_ch1.loads_kw) == ["CH-1"]
    with pytest.raises(ValueError):
        optimize_dispatch(plant, 700, on_set=["CH-3"])   # CH-3 only has 500 kW of capacity
