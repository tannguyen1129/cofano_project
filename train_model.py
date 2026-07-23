"""
Train the production model bundle (Version 5) on ALL available history.

This fits the exact models validated in the notebook backtest — a two-objective
XGBoost point ensemble plus P50/P90/P95 quantile models — on every eligible
known-target row, and serialises them (with the categorical mappings) to
`model/model_bundle.pkl` so `predict.py` can score new dates.

Usage:
    python train_model.py                        # uses data/demand_history.csv
    python train_model.py --data path/to.csv --out model/model_bundle.pkl
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import xgboost as xgb

from pipeline import (TARGET, BEST_FEATURES, QUANTILES, SEED, ENSEMBLE_CFGS,
                      QUANTILE_PARAMS, PRODUCT_FUEL, build_features)

VAL_DAYS = 28  # final validation tail used only for early stopping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/demand_history.csv")
    ap.add_argument("--out", default="model/model_bundle.pkl")
    args = ap.parse_args()

    raw = pd.read_csv(args.data, low_memory=False)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    print(f"Loaded {len(raw):,} rows | {raw.date.min().date()} -> {raw.date.max().date()}")

    df, cat_maps = build_features(raw, fit=True)
    elig = df.loc[df["target_known"] & df["month_eligible"]].reset_index(drop=True)
    print(f"Eligible known-target rows for training: {len(elig):,}")

    # Time-ordered split: last VAL_DAYS as the early-stopping validation set.
    cutoff = elig["date"].max() - pd.Timedelta(days=VAL_DAYS)
    tr = elig[elig["date"] < cutoff]
    va = elig[elig["date"] >= cutoff]
    if len(va) == 0 or len(tr) == 0:              # tiny-history fallback
        tr, va = elig, elig.tail(max(1, len(elig) // 10))
    print(f"Train rows: {len(tr):,} | validation (early-stop) rows: {len(va):,}")

    Xtr, ytr = tr[BEST_FEATURES], tr[TARGET]
    Xva, yva = va[BEST_FEATURES], va[TARGET]

    # --- point ensemble (Tweedie + absolute-error) ---
    point_models = []
    for i, cfg in enumerate(ENSEMBLE_CFGS, start=1):
        m = xgb.XGBRegressor(**{**cfg, "random_state": SEED})
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        point_models.append(m)
        print(f"  point model {i}/{len(ENSEMBLE_CFGS)} ({cfg['objective']}) trained "
              f"(best_iteration={getattr(m, 'best_iteration', 'n/a')})")

    # --- quantile models (safety stock) ---
    quantile_models = {}
    for q in QUANTILES:
        m = xgb.XGBRegressor(**QUANTILE_PARAMS, quantile_alpha=q, random_state=SEED)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        quantile_models[f"P{int(q * 100)}"] = m
        print(f"  quantile model P{int(q * 100)} trained")

    bundle = dict(
        point=point_models,
        quantile=quantile_models,
        cat_maps=cat_maps,
        features=BEST_FEATURES,
        target=TARGET,
        product_fuel=PRODUCT_FUEL,
        meta=dict(
            version="v5",
            objectives=[c["objective"] for c in ENSEMBLE_CFGS],
            quantiles=[f"P{int(q * 100)}" for q in QUANTILES],
            seed=SEED,
            n_train_rows=int(len(tr)),
            n_val_rows=int(len(va)),
            history_start=str(raw["date"].min().date()),
            history_end=str(raw["date"].max().date()),
        ),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    print(f"\nSaved model bundle -> {out} ({out.stat().st_size/1024:.0f} KB)")
    print("Keys:", list(bundle.keys()))


if __name__ == "__main__":
    main()
