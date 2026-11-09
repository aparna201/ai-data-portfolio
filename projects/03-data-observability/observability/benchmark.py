"""Four ways to score "how unusual is today?", and the tools to compare them fairly.

Every method turns each day into a SCORE (bigger = more unusual) using only the previous
WINDOW days. A day is flagged when its score passes a THRESHOLD. Tuning means choosing
that threshold on validation series, then checking it once on unseen test series.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

WINDOW = 21
METHODS = ["zscore", "robust_z", "iqr", "isolation_forest"]


def _mad(w: np.ndarray) -> float:
    return float(np.median(np.abs(w - np.median(w))))


def trailing_frame(values: pd.Series, window: int = WINDOW) -> pd.DataFrame:
    """Statistics of the previous `window` days. shift(1) keeps today out of its own baseline."""
    roll = values.rolling(window)
    frame = pd.DataFrame({
        "value": values,
        "mean": roll.mean().shift(1),
        "std": roll.std().shift(1),
        "median": roll.median().shift(1),
        "mad": roll.apply(_mad, raw=True).shift(1),
        "q1": roll.quantile(0.25).shift(1),
        "q3": roll.quantile(0.75).shift(1),
    })
    return frame


def _robust_z(f: pd.DataFrame) -> pd.Series:
    scale = np.maximum.reduce([1.4826 * f["mad"], 0.01 * f["median"].abs(), np.full(len(f), 1e-9)])
    return (f["value"] - f["median"]) / scale


def _plain_z(f: pd.DataFrame) -> pd.Series:
    scale = np.maximum(f["std"], 0.005 * f["mean"].abs())
    return (f["value"] - f["mean"]) / scale


def _forest_features(f: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"robust_z": _robust_z(f), "plain_z": _plain_z(f),
                         "pct_dev": (f["value"] - f["median"]) / f["median"].abs()})


def score_series(values: pd.Series, method: str, forest: IsolationForest | None = None) -> pd.Series:
    """Anomaly score per day (NaN for the first WINDOW days, which have no baseline)."""
    f = trailing_frame(values)
    if method == "zscore":
        return _plain_z(f).abs()
    if method == "robust_z":
        return _robust_z(f).abs()
    if method == "iqr":
        iqr = np.maximum(f["q3"] - f["q1"], 0.01 * f["median"].abs())
        return pd.concat([(f["q1"] - f["value"]) / iqr, (f["value"] - f["q3"]) / iqr], axis=1).max(axis=1)
    if method == "isolation_forest":
        feats = _forest_features(f)
        ok = feats.notna().all(axis=1)
        out = pd.Series(np.nan, index=values.index)
        out[ok] = -forest.decision_function(feats[ok])       # higher = more anomalous
        return out
    raise ValueError(method)


def score_all(df: pd.DataFrame, method: str, forest=None) -> pd.DataFrame:
    """Score every series in a long table. Returns the table with a `score` column, warm-up rows dropped."""
    parts = []
    for _, g in df.groupby("series_id"):
        g = g.sort_values("day").copy()
        g["score"] = score_series(g["value"].reset_index(drop=True), method, forest).to_numpy()
        parts.append(g)
    return pd.concat(parts).dropna(subset=["score"])


def fit_forest(train_df: pd.DataFrame, seed: int = 0) -> IsolationForest:
    """Unsupervised: learns what 'normal' feature combinations look like. Labels are not used."""
    feats = []
    for _, g in train_df.groupby("series_id"):
        f = trailing_frame(g.sort_values("day")["value"].reset_index(drop=True))
        feats.append(_forest_features(f).dropna())
    return IsolationForest(n_estimators=200, random_state=seed).fit(pd.concat(feats))


def candidate_thresholds(method: str, train_scores: np.ndarray) -> list[float]:
    if method == "isolation_forest":
        return [float(np.quantile(train_scores, q)) for q in (0.95, 0.97, 0.98, 0.99, 0.995)]
    return [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0]


def evaluate(scored: pd.DataFrame, threshold: float, days_per_month: int = 30) -> dict:
    flagged = scored["score"] > threshold
    truth = scored["is_anomaly"] == 1
    tp, fp, fn = int((flagged & truth).sum()), int((flagged & ~truth).sum()), int((~flagged & truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    series_months = len(scored) / days_per_month
    return {"threshold": round(float(threshold), 3), "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3),
            "false_alarms_per_series_month": round(fp / series_months, 3),
            "tp": tp, "fp": fp, "fn": fn}
