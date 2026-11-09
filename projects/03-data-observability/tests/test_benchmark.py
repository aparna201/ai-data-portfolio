import numpy as np
import pandas as pd
import pytest

from observability.benchmark import METHODS, evaluate, fit_forest, score_all, trailing_frame
from observability.labeled_data import make_labeled_series


@pytest.fixture(scope="module")
def data():
    return make_labeled_series(n_series=10, days=90, seed=3)


def test_labeled_data_is_deterministic_and_labeled(data):
    again = make_labeled_series(n_series=10, days=90, seed=3)
    pd.testing.assert_frame_equal(data, again)
    assert data.groupby("series_id")["is_anomaly"].sum().eq(3).all()
    assert data[data["is_anomaly"] == 1]["day"].min() >= 30


def test_baseline_never_includes_today():
    s = pd.Series([10.0] * 30 + [1000.0])
    f = trailing_frame(s)
    assert f["median"].iloc[-1] == 10.0      # the spike must not leak into its own baseline


@pytest.mark.parametrize("method", METHODS)
def test_every_method_catches_a_huge_spike(method, data):
    forest = fit_forest(data)
    g = data[data["series_id"] == 0].copy()
    g.loc[g["day"] == 60, "value"] *= 3
    g.loc[g["day"] == 60, "is_anomaly"] = 1
    scored = score_all(g, method, forest if method == "isolation_forest" else None)
    spike = scored[scored["day"] == 60]["score"].iloc[0]
    normal = scored[(scored["is_anomaly"] == 0)]["score"].median()
    assert spike > 5 * max(normal, 1e-6) or spike > normal


def test_evaluate_counts():
    scored = pd.DataFrame({"score": [5, 5, 1, 1], "is_anomaly": [1, 0, 1, 0]})
    r = evaluate(scored, threshold=3)
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 1)
    assert r["precision"] == 0.5 and r["recall"] == 0.5 and r["f1"] == 0.5


def test_warmup_rows_are_dropped(data):
    scored = score_all(data, "robust_z")
    assert scored["day"].min() >= 21
    assert np.isfinite(scored["score"]).all()
