"""Live forecasting service — runs the Version 5 model bundle.

Loads `model/model_bundle.pkl` from the repository root and reuses the repo's
`pipeline.py` feature engineering, so the dashboard serves exactly the same model
and features as `predict.py` and the validated notebook.
"""
import functools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

REPO_ROOT = Path(__file__).resolve().parents[3]        # .../cofano-fuel-forecast
sys.path.insert(0, str(REPO_ROOT))
from pipeline import TARGET, PRODUCT_FUEL, build_features  # noqa: E402

MODEL_PATH = REPO_ROOT / "model" / "model_bundle.pkl"
# Prefer the rolling "live" history (real data + synthetic seasonal tail to today) so the
# dashboard's planning week stays current; fall back to the raw real data.
_LIVE = REPO_ROOT / "webapp" / "data" / "demand_history_live.csv"
DATA_PATH = _LIVE if _LIVE.exists() else REPO_ROOT / "data" / "demand_history.csv"
GEO_PATH = REPO_ROOT / "data" / "station_metadata.csv"
HORIZON_DAYS = 7                                        # weekly planning horizon


@functools.lru_cache(maxsize=1)
def bundle():
    return joblib.load(MODEL_PATH)


@functools.lru_cache(maxsize=1)
def history():
    h = pd.read_csv(DATA_PATH, low_memory=False)
    h["date"] = pd.to_datetime(h["date"], errors="coerce")
    return h


@functools.lru_cache(maxsize=1)
def stations():
    return pd.read_csv(GEO_PATH)


def _forecast_frame(start, days):
    """Extend every station-product series by `days` days and score it with the v5 bundle."""
    b = bundle()
    raw = history().copy()

    pairs = raw[["station_code", "product"]].drop_duplicates()
    dates = pd.date_range(start, periods=days, freq="D")
    future = (pairs.assign(_k=1).merge(pd.DataFrame({"date": dates, "_k": 1}), on="_k").drop(columns="_k"))
    future[TARGET] = np.nan
    future = future.merge(raw[["station_code", "product", "date"]], on=["station_code", "product", "date"],
                          how="left", indicator=True)
    future = future[future["_merge"] == "left_only"].drop(columns="_merge")
    for c in raw.columns:
        if c not in future.columns:
            future[c] = np.nan

    feat, _ = build_features(pd.concat([raw, future[raw.columns]], ignore_index=True),
                            cat_maps=b["cat_maps"], fit=False)
    fut = feat[(feat["date"] >= start) & (feat["date"] < start + pd.Timedelta(days=days))].copy()
    if fut.empty:
        return fut

    X = fut[b["features"]]
    fut["point"] = np.mean([np.clip(m.predict(X), 0, None) for m in b["point"]], axis=0)
    qnames = sorted(b["quantile"], key=lambda n: int(n[1:]))          # P50, P90, P95
    q = np.maximum.accumulate(
        np.column_stack([np.clip(b["quantile"][n].predict(X), 0, None) for n in qnames]), axis=1)
    for j, n in enumerate(qnames):
        fut[n.lower()] = q[:, j]
    return fut


def predict(start=None, end=None):
    """Return a list of forecast records. Defaults to the 7 days after the history ends."""
    raw = history()
    last = raw["date"].max()
    start = (last + pd.Timedelta(days=1)) if start is None else pd.Timestamp(start)
    days = max(1, (pd.Timestamp(end) - start).days + 1) if end else HORIZON_DAYS

    fut = _forecast_frame(start, days)
    if len(fut) == 0:
        return []
    fut["weeks_ahead"] = ((fut["date"] - start).dt.days // 7) + 1
    return [dict(date=r.date.strftime("%Y-%m-%d"), station_code=r.station_code, product=r.product,
                 fuel=PRODUCT_FUEL.get(r.product, r.product), weeks_ahead=int(r.weeks_ahead),
                 forecast=round(float(r.point), 1), p50=round(float(r.p50), 1),
                 p90=round(float(r.p90), 1), p95=round(float(r.p95), 1))
            for r in fut.itertuples()]
