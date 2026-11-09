import pandas as pd

from gateway import Gateway
from gateway.predict import FEATURES, NoShowScorer, evaluate, make_appointments, split_by_time, top_share


def test_split_is_chronological_and_has_no_overlap():
    df = make_appointments(1000)
    tr, va, te = split_by_time(df)
    assert tr["appt_date"].max() <= va["appt_date"].min() and va["appt_date"].max() <= te["appt_date"].min()
    assert len(tr) + len(va) + len(te) == 1000


def test_model_beats_a_single_feature_baseline_on_unseen_data():
    r = evaluate(make_appointments())
    assert r["test"]["auc"] > r["test"]["baseline_prior_no_shows_only_auc"] + 0.1
    assert r["test"]["top20_captures_no_shows"] > 0.30       # random scoring would capture 0.20


def test_top_share_random_is_about_the_fraction():
    y = [1, 0, 0, 0, 0] * 200
    assert abs(top_share(y, list(range(1000)), 0.2) - 0.2) < 0.01


def test_risk_scores_are_probabilities_and_reflect_history():
    risk = NoShowScorer(make_appointments(3000)).risk_by_patient()
    assert all(0 <= v <= 1 for v in risk.values())
    assert risk[6] > risk[1]            # 3 prior no-shows, far away, no reminder vs a regular nearby patient


def test_only_front_desk_gets_risk_scores(tmp_path):
    gw = Gateway(tmp_path / "a.jsonl", scorer=NoShowScorer(make_appointments(2000)))
    assert gw.request("tok-desk", "no_show_risk", "read", {}).ok
    for tok in ("tok-rao", "tok-nurse-a", "tok-lab", "tok-clean", "tok-pat1"):
        assert not gw.request(tok, "no_show_risk", "read", {}).ok
