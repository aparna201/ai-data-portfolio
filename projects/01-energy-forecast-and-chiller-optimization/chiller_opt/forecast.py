"""Day-ahead cooling-load forecasting: features, candidate models, tuning, selection.

The question the model answers: "tomorrow, at this hour, how much cooling will we need?"
So every feature must be known a day ahead. That is why the load lags start at 24 hours
and why the weather input is a forecast, not the measured temperature.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "load_kw"
FEATURES = ["hour_sin", "hour_cos", "is_weekend", "temp_forecast_c",
            "lag_24", "lag_48", "lag_168", "mean_24_lagged"]
BASELINES = {"same_hour_yesterday": "lag_24", "same_hour_last_week": "lag_168"}


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build model inputs. Nothing here uses load from the last 24 hours."""
    out = df.copy()
    out["hour_sin"] = np.sin(2 * np.pi * out["timestamp"].dt.hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["timestamp"].dt.hour / 24)
    out["is_weekend"] = (out["timestamp"].dt.dayofweek >= 5).astype(int)
    out["lag_24"] = out[TARGET].shift(24)
    out["lag_48"] = out[TARGET].shift(48)
    out["lag_168"] = out[TARGET].shift(168)
    out["mean_24_lagged"] = out[TARGET].rolling(24).mean().shift(24)
    return out.dropna().reset_index(drop=True)


def split_by_time(df: pd.DataFrame, train: float = 0.70, val: float = 0.15):
    """Chronological split. Shuffling would leak the future into training."""
    n = len(df)
    i, j = int(n * train), int(n * (train + val))
    return df.iloc[:i], df.iloc[i:j], df.iloc[j:]


def metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return {
        "mae_kw": float(mean_absolute_error(y_true, y_pred)),
        "rmse_kw": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mape_pct": float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100),
    }


def candidate_models(quick: bool = False) -> dict:
    """name -> (estimator, parameter grid). `quick` shrinks the grids for tests."""
    if quick:
        return {
            "ridge": (make_pipeline(StandardScaler(), Ridge()), {"ridge__alpha": [1.0]}),
            "gradient_boosting": (HistGradientBoostingRegressor(random_state=0),
                                  {"max_iter": [100], "learning_rate": [0.1]}),
        }
    return {
        "ridge": (make_pipeline(StandardScaler(), Ridge()),
                  {"ridge__alpha": [0.01, 0.1, 1, 10, 100]}),
        "random_forest": (RandomForestRegressor(random_state=0, n_jobs=1),
                          {"n_estimators": [100, 200], "max_depth": [6, 12, None],
                           "min_samples_leaf": [1, 5]}),
        "gradient_boosting": (HistGradientBoostingRegressor(random_state=0),
                              {"max_iter": [200, 400], "learning_rate": [0.05, 0.1],
                               "max_depth": [3, 6]}),
    }


def tune_and_select(train: pd.DataFrame, val: pd.DataFrame, quick: bool = False):
    """Tune each model with time-ordered cross-validation on the training data, then pick
    the winner on the separate validation block. Returns (results table, winner, fitted)."""
    rows, fitted = [], {}
    for name, (estimator, grid) in candidate_models(quick).items():
        search = GridSearchCV(estimator, grid, cv=TimeSeriesSplit(n_splits=4),
                              scoring="neg_mean_absolute_error", n_jobs=1)
        search.fit(train[FEATURES], train[TARGET])
        scores = metrics(val[TARGET], search.predict(val[FEATURES]))
        rows.append({"model": name, "kind": "ml", "cv_mae_kw": -search.best_score_,
                     "val_mae_kw": scores["mae_kw"], "val_rmse_kw": scores["rmse_kw"],
                     "val_mape_pct": scores["mape_pct"], "best_params": search.best_params_})
        fitted[name] = search.best_estimator_
    for name, column in BASELINES.items():
        scores = metrics(val[TARGET], val[column])
        rows.append({"model": name, "kind": "baseline", "cv_mae_kw": np.nan,
                     "val_mae_kw": scores["mae_kw"], "val_rmse_kw": scores["rmse_kw"],
                     "val_mape_pct": scores["mape_pct"], "best_params": {}})
    table = pd.DataFrame(rows).sort_values("val_mae_kw").reset_index(drop=True)
    winner = table[table["kind"] == "ml"].iloc[0]["model"]
    return table, winner, fitted
