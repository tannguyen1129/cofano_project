"""Seed the demo dashboard database.

Stations/products come from the anonymised repo data; the forecast table is produced by running
the Version 5 model bundle; the benchmark, penalty and KPI figures are the headline results
reported in the final assignment report (five-fold, capacity-capped simulation).
"""
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from forecast.models import Station, ProductMap, Forecast, BenchmarkMetric, PenaltyResult, Kpi

REPO_ROOT = Path(__file__).resolve().parents[5]
DATA = REPO_ROOT / "data"
_LIVE = REPO_ROOT / "webapp" / "data" / "demand_history_live.csv"
HISTORY_CSV = _LIVE if _LIVE.exists() else DATA / "demand_history.csv"

PRODUCT_FUEL = {"P1": "Euro95", "P2": "Super98", "P3": "Diesel", "P4": "AdBlue", "P5": "LPG"}
MAIN = {"P1", "P3"}

# --- headline results from the final report (Version 5, five chronological folds) -------------
NAIVE_WAPE, MODEL_WAPE, MODEL_WAPE_MAIN = 25.478, 20.153, 19.29
BENCH = [("Naive (last week)", NAIVE_WAPE, None, None),
         ("Selected model (Core + school)", MODEL_WAPE, MODEL_WAPE_MAIN, None)]

# report Table 13 — capacity-capped (1.3x complete 7-calendar-day peak proxy)
#   policy, stockout-day events, shortfall L, feasible carryover L, undeliverable L, penalty, vs naive %
PENALTY = [
    ("Naive (last week)",                     1401,   801620, 2632991,     10945, 10703920,   0.0),
    ("P50 quantile (central)",                1455,  1094776, 2311978,         0, 13259733, -23.9),
    ("P95 quantile (safety-oriented)",          29,   139224, 7092252,    132028,  9144637,  14.6),
]
VS_NAIVE = round((NAIVE_WAPE - MODEL_WAPE) / NAIVE_WAPE * 100, 1)          # 20.9 %
STOCKOUT_CUT = round((1401 - 29) / 1401 * 100, 1)                          # 97.9 %
KPIS = [
    ("wape_main", MODEL_WAPE_MAIN,
     "Sai số trên nhiên liệu chính (Euro95+Diesel, ~93% sản lượng)",
     "Error on main fuels (Euro95+Diesel, ~93% of volume)"),
    ("vs_naive", VS_NAIVE,
     "Giảm sai số so với cách “lặp lại tuần trước”",
     "Error cut vs the “repeat last week” baseline"),
    ("penalty_cut", 14.6,
     "Giảm chi phí tồn kho (proxy có giới hạn sức chứa) khi dùng P95",
     "Weighted-proxy inventory cost cut with P95 (capacity-capped)"),
    ("stockout_cut", STOCKOUT_CUT,
     "Giảm số sự kiện trạm cạn hàng (1.401 → 29)",
     "Fewer station-product stockout-day events (1,401 → 29)"),
]


class Command(BaseCommand):
    help = "Load stations, product mapping, model forecasts, benchmark, penalty and KPI rows."

    @transaction.atomic
    def handle(self, *args, **o):
        for M in (Forecast, Station, ProductMap, BenchmarkMetric, PenaltyResult, Kpi):
            M.objects.all().delete()

        geo = pd.read_csv(DATA / "station_metadata.csv")
        raw = pd.read_csv(HISTORY_CSV, low_memory=False)
        demand = raw.groupby("station_code")["daily_demand"].sum().to_dict()

        smap = {}
        for _, r in geo.iterrows():
            smap[r.station_code] = Station.objects.create(
                code=r.station_code, name=str(r.station_code),
                brand=str(r.get("brand", "") or ""), country=str(r.get("country_code", "") or ""),
                lat=float(r.lat), lon=float(r.lon), total_demand=float(demand.get(r.station_code, 0)))

        share = raw.groupby("product")["daily_demand"].sum()
        share = (share / share.sum() * 100).round(2)
        for code, fuel in PRODUCT_FUEL.items():
            ProductMap.objects.create(code=code, fuel=fuel,
                                      volume_share=float(share.get(code, 0)), is_main=code in MAIN)

        # Forecasts straight from the Version 5 bundle (weekly planning horizon).
        from forecast.ml_service import predict
        recs = predict()
        Forecast.objects.bulk_create([
            Forecast(date=r["date"], station=smap[r["station_code"]], product=r["product"],
                     fuel=r["fuel"], weeks_ahead=r["weeks_ahead"],
                     p50=r["forecast"], p90=r["p90"], p95=r["p95"])
            for r in recs if r["station_code"] in smap], batch_size=1000)

        for name, w, wm, wn in BENCH:
            BenchmarkMetric.objects.create(model_name=name, wape=w, wape_main=wm, wape_minor=wn)
        for policy, sd, sh, carry, und, pen, vs in PENALTY:
            PenaltyResult.objects.create(policy=policy, stockout_days=sd, shortfall=sh,
                                         carryover=carry, undeliverable=und,
                                         replan_events=0, penalty=pen, vs_naive=vs)
        for k, v, vi, en in KPIS:
            Kpi.objects.create(key=k, value=v, label_vi=vi, label_en=en)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Station.objects.count()} stations, {Forecast.objects.count()} forecast rows, "
            f"{ProductMap.objects.count()} products, {PenaltyResult.objects.count()} penalty rows."))
