"""Tier 2 (the AI tier): appointment no-show risk.

Why this one: an empty slot is lost revenue and a patient who waited longer. Scoring tomorrow's appointments lets the
front desk send reminders to the riskiest first. Everything here is synthetic; the evaluation shows the method works,
not what a real hospital would see.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["lead_days", "prior_no_shows", "age", "distance_km", "reminder_sent", "new_patient", "is_monday"]


def make_appointments(n: int = 6000, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "appt_date": pd.Timestamp("2026-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 300, n)), unit="D"),
        "lead_days": rng.integers(0, 45, n), "prior_no_shows": rng.poisson(0.4, n), "age": rng.integers(18, 85, n),
        "distance_km": rng.gamma(2.0, 6.0, n).round(1), "reminder_sent": rng.integers(0, 2, n),
        "new_patient": rng.integers(0, 2, n)})
    df["is_monday"] = (df["appt_date"].dt.dayofweek == 0).astype(int)
    logit = (-2.6 + 0.05 * df.lead_days + 0.55 * df.prior_no_shows + 0.03 * df.distance_km - 0.9 * df.reminder_sent
             + 0.4 * df.new_patient + 0.3 * df.is_monday - 0.01 * (df.age - 50))
    df["no_show"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


def split_by_time(df: pd.DataFrame):
    a, b = int(len(df) * 0.6), int(len(df) * 0.8)
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


def top_share(y, score, frac: float = 0.2) -> float:
    """Share of all no-shows that fall in the riskiest `frac` of appointments (random scoring would give `frac`)."""
    k = max(1, int(len(y) * frac))
    order = np.argsort(-np.asarray(score))
    return float(np.asarray(y)[order[:k]].sum() / max(1, np.sum(y)))


def candidates():
    for c in (0.01, 0.1, 1.0):
        yield f"logistic C={c}", make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=500))
    for depth in (2, 4):
        for lr in (0.05, 0.1):
            yield f"gradient_boosting depth={depth} lr={lr}", HistGradientBoostingClassifier(
                max_depth=depth, learning_rate=lr, max_iter=150, random_state=0)


def evaluate(df: pd.DataFrame) -> dict:
    train, val, test = split_by_time(df)
    base = float(train["no_show"].mean())
    out = {"rows": {"train": len(train), "val": len(val), "test": len(test)}, "no_show_rate_train": round(base, 3),
           "validation": {}, "test": {}}
    best_name, best_auc, best_model = None, -1, None
    for name, model in candidates():
        model.fit(train[FEATURES], train["no_show"])
        auc = roc_auc_score(val["no_show"], model.predict_proba(val[FEATURES])[:, 1])
        out["validation"][name] = round(auc, 4)
        if auc > best_auc:
            best_name, best_auc, best_model = name, auc, model
    trainval = pd.concat([train, val])
    best_model.fit(trainval[FEATURES], trainval["no_show"])             # refit on train + validation, test untouched so far
    s = best_model.predict_proba(test[FEATURES])[:, 1]
    out["chosen"] = best_name
    out["test"] = {"auc": round(roc_auc_score(test["no_show"], s), 4),
                   "top20_captures_no_shows": round(top_share(test["no_show"], s), 3),
                   "baseline_always_base_rate_auc": 0.5,
                   "baseline_prior_no_shows_only_auc": round(roc_auc_score(test["no_show"], test["prior_no_shows"]), 4),
                   "baseline_prior_no_shows_only_top20": round(top_share(test["no_show"], test["prior_no_shows"]), 3)}
    return out


class NoShowScorer:
    """Scores upcoming appointments. Demo: six upcoming appointments for the demo patients."""

    UPCOMING = pd.DataFrame({"patient_id": [1, 2, 3, 4, 5, 6], "lead_days": [3, 30, 1, 14, 21, 40],
                             "prior_no_shows": [0, 2, 0, 1, 0, 3], "age": [54, 67, 36, 61, 73, 32],
                             "distance_km": [4, 25, 3, 12, 8, 30], "reminder_sent": [1, 0, 1, 0, 1, 0],
                             "new_patient": [0, 0, 1, 0, 0, 1], "is_monday": [0, 1, 0, 0, 0, 1]})

    def __init__(self, df: pd.DataFrame | None = None) -> None:
        df = make_appointments() if df is None else df
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500))   # the validation winner
        self.model.fit(df[FEATURES], df["no_show"])

    def risk_by_patient(self) -> dict[int, float]:
        p = self.model.predict_proba(self.UPCOMING[FEATURES])[:, 1]
        return {int(i): round(float(r), 3) for i, r in zip(self.UPCOMING["patient_id"], p)}
