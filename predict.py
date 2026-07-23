"""
Generate a weekly demand forecast by running the trained model bundle.

Loads `model/model_bundle.pkl`, extends each active station-product series with the
next `--horizon` days, rebuilds the exact Version 5 features (leakage-safe: every
feature uses history >= 7 days old), and writes point + safety-stock forecasts.

Output columns (outputs/forecast.csv):
    date, station_code, product, fuel,
    forecast  -> point forecast (litres/day, ensemble)
    p50, p90, p95 -> safety-stock quantile levels (litres/day)

Usage:
    python predict.py                              # next 7 days after the data
    python predict.py --start 2026-05-23 --horizon 7
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from pipeline import TARGET, build_features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/demand_history.csv")
    ap.add_argument("--model", default="model/model_bundle.pkl")
    ap.add_argument("--start", default=None, help="First forecast date (YYYY-MM-DD). Default: day after last history date.")
    ap.add_argument("--horizon", type=int, default=7, help="Number of days to forecast (>=1). Weekly planning uses 7.")
    ap.add_argument("--out", default="outputs/forecast.csv")
    args = ap.parse_args()

    bundle = joblib.load(args.model)
    feats = bundle["features"]
    cat_maps = bundle["cat_maps"]
    product_fuel = bundle.get("product_fuel", {})
    print(f"Loaded model {bundle['meta'].get('version','?')} "
          f"(trained on {bundle['meta'].get('history_start')} -> {bundle['meta'].get('history_end')})")

    raw = pd.read_csv(args.data, low_memory=False)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    last_hist = raw["date"].max()

    start = pd.Timestamp(args.start) if args.start else last_hist + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=args.horizon)          # exclusive
    if start <= last_hist:
        print(f"WARNING: --start {start.date()} is within history (last={last_hist.date()}); "
              f"forecast rows overlapping known dates are dropped.")

    # Extend every station-product pair with placeholder future rows (target unknown).
    pairs = raw[["station_code", "product"]].drop_duplicates()
    future_dates = pd.date_range(start, end - pd.Timedelta(days=1), freq="D")
    future = (pairs.assign(key=1)
              .merge(pd.DataFrame({"date": future_dates, "key": 1}), on="key")
              .drop(columns="key"))
    future[TARGET] = np.nan
    # anti-join: never duplicate an existing station-product-day
    existing = raw[["station_code", "product", "date"]]
    future = future.merge(existing, on=["station_code", "product", "date"], how="left", indicator=True)
    future = future[future["_merge"] == "left_only"].drop(columns="_merge")
    for c in raw.columns:                                   # align schema; static meta filled by the panel builder
        if c not in future.columns:
            future[c] = np.nan
    raw_ext = pd.concat([raw, future[raw.columns]], ignore_index=True)

    # Rebuild features with the SAVED encodings, then keep only the forecast horizon.
    df, _ = build_features(raw_ext, cat_maps=cat_maps, fit=False)
    fut = df[(df["date"] >= start) & (df["date"] < end)].copy()
    if fut.empty:
        raise SystemExit("No forecast rows produced — check --start / --horizon against the data range.")

    X = fut[feats]
    point = np.mean([np.clip(m.predict(X), 0, None) for m in bundle["point"]], axis=0)
    out = fut[["date", "station_code", "product"]].copy()
    out["fuel"] = out["product"].map(product_fuel)
    out["forecast"] = np.round(point, 1)

    # Predict each quantile, then enforce non-crossing (P50 <= P90 <= P95) by row-wise
    # rearrangement (cumulative max over increasing quantile levels). Independent quantile
    # regressors can otherwise cross; rearrangement fixes this without hurting coverage.
    qnames = sorted(bundle["quantile"], key=lambda n: int(n[1:]))          # P50, P90, P95
    qpreds = np.column_stack([np.clip(bundle["quantile"][n].predict(X), 0, None) for n in qnames])
    qpreds = np.maximum.accumulate(qpreds, axis=1)
    for j, n in enumerate(qnames):
        out[n.lower()] = np.round(qpreds[:, j], 1)

    out = out.sort_values(["date", "station_code", "product"]).reset_index(drop=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"\nForecast horizon: {start.date()} -> {(end - pd.Timedelta(days=1)).date()} "
          f"| {out['station_code'].nunique()} stations | {len(out):,} rows")
    print(f"Saved -> {out_path}")
    print(out.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
