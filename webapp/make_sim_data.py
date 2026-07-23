"""
Generate the backtest slice the dashboard's inventory panel replays.

Trains the Version 5 models on history before CUTOFF and scores the window after it, so the
dashboard shows genuine out-of-sample predictions (actual vs naive lag-7 vs P50 vs P95) rather
than in-sample fits. This is the demo equivalent of the notebook's chronological folds,
collapsed into a single window.

    python webapp/make_sim_data.py      -> webapp/data/sim_predictions.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from pipeline import (TARGET, BEST_FEATURES, QUANTILES, SEED, ENSEMBLE_CFGS,  # noqa: E402
                      QUANTILE_PARAMS, build_features)

CUTOFF = pd.Timestamp("2025-10-01")     # matches the first notebook fold's test_start
VAL_DAYS = 28
OUT = REPO_ROOT / "webapp" / "data" / "sim_predictions.csv"


def main():
    raw = pd.read_csv(REPO_ROOT / "data" / "demand_history.csv", low_memory=False)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    df, cat_maps = build_features(raw, fit=True)
    elig = df.loc[df["target_known"] & df["month_eligible"]]

    val_start = CUTOFF - pd.Timedelta(days=VAL_DAYS)
    tr = elig[elig.date < val_start]
    va = elig[(elig.date >= val_start) & (elig.date < CUTOFF)]
    te = elig[(elig.date >= CUTOFF) & elig["lag_7"].notna()].copy()   # paired with the naive rule
    print(f"train {len(tr):,} | val {len(va):,} | test {len(te):,} "
          f"({te.date.min().date()} -> {te.date.max().date()})")

    Xtr, ytr, Xva, yva = tr[BEST_FEATURES], tr[TARGET], va[BEST_FEATURES], va[TARGET]
    Xte = te[BEST_FEATURES]

    point = []
    for cfg in ENSEMBLE_CFGS:
        m = xgb.XGBRegressor(**{**cfg, "random_state": SEED})
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        point.append(np.clip(m.predict(Xte), 0, None))
    te["pred_point"] = np.mean(point, axis=0)

    qcols = []
    for q in QUANTILES:
        m = xgb.XGBRegressor(**QUANTILE_PARAMS, quantile_alpha=q, random_state=SEED)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        qcols.append(np.clip(m.predict(Xte), 0, None))
        print(f"  quantile P{int(q*100)} done")
    qmat = np.maximum.accumulate(np.column_stack(qcols), axis=1)      # non-crossing
    for j, q in enumerate(QUANTILES):
        te[f"pred_p{int(q*100)}"] = qmat[:, j]

    out = te[["date", "station_code", "product"]].copy()
    out["actual"] = te[TARGET].values
    out["naive"] = te["lag_7"].values
    out["pred_point"] = te["pred_point"].round(1)
    for q in QUANTILES:
        c = f"pred_p{int(q*100)}"
        out[c] = te[c].round(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values(["station_code", "product", "date"]).to_csv(OUT, index=False)

    def wape(y, p):
        y, p = np.asarray(y, float), np.asarray(p, float)
        return np.abs(y - p).sum() / np.abs(y).sum() * 100
    print(f"\nSaved {len(out):,} rows -> {OUT}")
    print(f"  WAPE naive={wape(out.actual, out.naive):.2f}%  model={wape(out.actual, out.pred_point):.2f}%")
    print(f"  P95 coverage={np.mean(out.actual <= out.pred_p95)*100:.1f}%")


if __name__ == "__main__":
    main()
