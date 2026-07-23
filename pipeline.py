"""
Shared feature-engineering pipeline (Version 5).

This module contains the EXACT configuration and feature engineering used by
`full_pipeline.ipynb`, factored out so that `train_model.py` and `predict.py`
build features identically to the validated notebook. Nothing here changes the
methodology — it is a copy of the notebook's `build_daily_panel` / `build_features`
with the categorical encoder parameterised so it can either *fit* (training) or
*apply* a saved mapping (prediction).
"""
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- configuration
TARGET = "daily_demand"
PRODUCT_FUEL = {"P1": "Euro95", "P2": "Super98", "P3": "Diesel", "P4": "AdBlue", "P5": "LPG"}
MAIN_PRODUCTS = ["P1", "P3"]

LAGS = [7, 14, 21, 28, 56, 364, 371]
G_TS = ["lag_7", "lag_14", "lag_21", "lag_28", "lag_56", "lag_364", "lag_371",
        "roll4_mean", "roll4_std", "roll8_mean", "roll8_std", "asof_last", "yoy_mean", "trend_7_28", "ratio_7_28",
        "lag_7_missing", "lag_14_missing", "lag_21_missing", "lag_28_missing", "lag_56_missing",
        "lag_364_missing", "lag_371_missing", "roll4_valid_count", "roll8_valid_count"]
G_CAL = ["day_of_week", "is_weekend", "month", "quarter", "week_of_year", "day_of_year",
         "month_sin", "month_cos", "week_sin", "week_cos", "is_month_end"]
G_STAT = ["station_encoded", "product_encoded", "country_encoded", "area_type_encoded", "nearest_place_type_encoded",
          "traffic_source_encoded", "station_product_encoded", "lat", "lon", "building_density_km2", "roads_1km",
          "major_roads_3km", "is_belgium"]
G_SCHOOL = ["is_school_holiday", "school_holiday_type_code", "days_into_holiday", "days_to_holiday"]
BEST_FEATURES = G_TS + G_CAL + G_STAT + G_SCHOOL

SEED = 0
QUANTILES = [0.50, 0.90, 0.95]

# XGBoost point ensemble: Tweedie + absolute-error objectives, averaged.
ENSEMBLE_CFGS = [
    dict(n_estimators=300, learning_rate=0.05, max_depth=7, subsample=0.9, colsample_bytree=0.9,
         objective="reg:tweedie", tweedie_variance_power=1.4, tree_method="hist", n_jobs=-1,
         eval_metric="mae", early_stopping_rounds=30),
    dict(n_estimators=300, learning_rate=0.03, max_depth=7, subsample=0.9, colsample_bytree=0.9,
         objective="reg:absoluteerror", tree_method="hist", n_jobs=-1,
         eval_metric="mae", early_stopping_rounds=30),
]
QUANTILE_PARAMS = dict(n_estimators=300, learning_rate=0.04, max_depth=5, subsample=0.9, colsample_bytree=0.9,
                       objective="reg:quantileerror", tree_method="hist", n_jobs=-1,
                       eval_metric="mae", early_stopping_rounds=30)

# categorical columns -> (source expression name) handled explicitly in build_features
ENCODED_COLS = ["station_encoded", "product_encoded", "country_encoded", "area_type_encoded",
                "nearest_place_type_encoded", "traffic_source_encoded", "station_product_encoded"]


def _encode(series, name, cat_maps, fit):
    """Factorise when fitting (and record the mapping); apply the saved mapping otherwise.

    Unseen categories at prediction time map to -1, mirroring pandas' factorize NaN code so the
    model sees an out-of-vocabulary marker rather than a wrong, reused code.
    """
    s = series.astype(str).fillna("missing")
    if fit:
        codes, uniques = pd.factorize(s)
        cat_maps[name] = {str(u): int(i) for i, u in enumerate(uniques)}
        return codes
    mapping = cat_maps.get(name, {})
    return s.map(mapping).fillna(-1).astype(int).to_numpy()


def build_daily_panel(raw):
    """Build a calendar-day panel without silently equating data outages with zero demand.

    Policy: an observed row keeps its actual target; a missing product row is a confirmed zero only
    when another product was observed at the same station on that date; if the whole station-day is
    absent, the target remains unknown. Pairs are expanded only between their first and last observed
    dates, avoiding invented history before a product launch or after discontinuation.
    """
    base = raw.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    if TARGET not in base.columns and "volume_in_liter" in base.columns:
        base[TARGET] = base["volume_in_liter"]
    base = base.dropna(subset=["date", "station_code", "product"]).copy()
    duplicate_keys = base.duplicated(["station_code", "product", "date"], keep=False)
    if duplicate_keys.any():
        raise ValueError(f"Expected one row per station-product-day; found {int(duplicate_keys.sum())} duplicate rows.")

    spans = base.groupby(["station_code", "product"])["date"].agg(["min", "max"]).reset_index()
    panel_parts = [pd.DataFrame({"station_code": r["station_code"], "product": r["product"],
                                 "date": pd.date_range(r["min"], r["max"], freq="D")})
                   for _, r in spans.iterrows()]
    panel = pd.concat(panel_parts, ignore_index=True)
    panel = panel.merge(base, on=["station_code", "product", "date"], how="left", indicator="_source")
    panel["source_observed"] = panel["_source"].eq("both")
    panel = panel.drop(columns="_source")

    station_day = base[["station_code", "date"]].drop_duplicates().assign(station_day_observed=True)
    panel = panel.merge(station_day, on=["station_code", "date"], how="left")
    panel["station_day_observed"] = panel["station_day_observed"].fillna(False).astype(bool)
    panel["target_status"] = np.select(
        [panel["source_observed"], panel["station_day_observed"]],
        ["observed", "confirmed_zero"], default="unknown_station_day")
    panel.loc[panel["target_status"].eq("confirmed_zero"), TARGET] = 0.0
    panel["target_known"] = (~panel["target_status"].eq("unknown_station_day")) & panel[TARGET].notna()

    audit_cols = {"station_code", "product", "date", TARGET, "source_observed",
                  "station_day_observed", "target_status", "target_known"}
    metadata_cols = [c for c in base.columns if c not in audit_cols]
    station_day_meta = base.groupby(["station_code", "date"], as_index=False)[metadata_cols].first()
    panel = panel.merge(station_day_meta, on=["station_code", "date"], how="left", suffixes=("", "_station_day"))
    for col in metadata_cols:
        peer = f"{col}_station_day"
        if peer in panel.columns:
            panel[col] = panel[col].combine_first(panel[peer])
            panel = panel.drop(columns=peer)
        panel[col] = panel.groupby(["station_code", "product"])[col].transform(lambda s: s.ffill().bfill())

    panel["year_month"] = panel["date"].dt.to_period("M").astype(str)
    observed_days = (station_day.assign(year_month=station_day["date"].dt.to_period("M").astype(str))
                     .groupby(["station_code", "year_month"])["date"].nunique()
                     .rename("station_month_observed_days").reset_index())
    panel = panel.merge(observed_days, on=["station_code", "year_month"], how="left")
    panel["station_month_observed_days"] = panel["station_month_observed_days"].fillna(0).astype(int)
    panel["month_eligible"] = panel["station_month_observed_days"].ge(28)
    return panel.sort_values(["station_code", "product", "date"]).reset_index(drop=True)


def build_features(raw, cat_maps=None, fit=True):
    """Return (panel_with_features, cat_maps). Set fit=False and pass cat_maps to score new rows."""
    if cat_maps is None:
        cat_maps = {}
    df = build_daily_panel(raw)
    df = df.sort_values(["station_code", "product", "date"]).reset_index(drop=True)
    keys = ["station_code", "product"]

    # Calendar features
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["month"] = df["date"].dt.month
    df["quarter"] = df["date"].dt.quarter
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_year"] = df["date"].dt.dayofyear
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["week_sin"] = np.sin(2 * np.pi * df["week_of_year"] / 52)
    df["week_cos"] = np.cos(2 * np.pi * df["week_of_year"] / 52)
    df["is_month_end"] = df["date"].dt.is_month_end.astype(int)

    for col, default in [("is_school_holiday", 0), ("school_holiday_type_code", 0),
                         ("days_into_holiday", -1), ("days_to_holiday", -1)]:
        if col not in df.columns:
            df[col] = default

    # Time-series features: shifted by at least 7 days for weekly planning.
    grouped = df.groupby(keys)[TARGET]
    for lag in LAGS:
        df[f"lag_{lag}"] = grouped.shift(lag)
        df[f"lag_{lag}_missing"] = df[f"lag_{lag}"].isna().astype(int)
    df["asof_last"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).ffill())
    df["roll4_mean"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(28, min_periods=1).mean())
    df["roll4_std"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(28, min_periods=2).std())
    df["roll8_mean"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(56, min_periods=1).mean())
    df["roll8_std"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(56, min_periods=2).std())
    df["roll4_valid_count"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(28, min_periods=1).count())
    df["roll8_valid_count"] = df.groupby(keys)[TARGET].transform(lambda s: s.shift(7).rolling(56, min_periods=1).count())
    df["yoy_mean"] = df[["lag_364", "lag_371"]].mean(axis=1)
    df["trend_7_28"] = df["lag_7"] - df["lag_28"]
    df["ratio_7_28"] = df["lag_7"] / df["lag_28"].replace(0, np.nan)

    # Station / geography features (categorical encodings use the shared cat_maps).
    df["station_encoded"] = _encode(df["station_code"], "station_encoded", cat_maps, fit)
    df["product_encoded"] = _encode(df["product"], "product_encoded", cat_maps, fit)
    df["country_encoded"] = _encode(df.get("country_code", pd.Series("missing", index=df.index)), "country_encoded", cat_maps, fit)
    df["area_type_encoded"] = _encode(df.get("area_type", pd.Series("missing", index=df.index)), "area_type_encoded", cat_maps, fit)
    df["nearest_place_type_encoded"] = _encode(df.get("nearest_place_type", pd.Series("missing", index=df.index)), "nearest_place_type_encoded", cat_maps, fit)
    df["traffic_source_encoded"] = _encode(df.get("traffic_source", pd.Series("missing", index=df.index)), "traffic_source_encoded", cat_maps, fit)
    df["station_product_encoded"] = _encode(df["station_code"].astype(str) + "_" + df["product"].astype(str), "station_product_encoded", cat_maps, fit)
    df["is_belgium"] = (df.get("country_code", "") == "BE").astype(int) if "country_code" in df.columns else 0
    for col in ["lat", "lon", "building_density_km2", "roads_1km", "major_roads_3km"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in BEST_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, cat_maps
