import datetime
import functools
from pathlib import Path

import numpy as np
import pandas as pd
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Station, ProductMap, Forecast, BenchmarkMetric, PenaltyResult, Kpi
from .serializers import (StationSerializer, ProductMapSerializer, ForecastSerializer,
                          BenchmarkSerializer, PenaltySerializer, KpiSerializer)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data"
WEBAPP_DATA = REPO_ROOT / "webapp" / "data"
# Rolling live history (real + synthetic tail to today) if present, else the raw real data.
_LIVE = WEBAPP_DATA / "demand_history_live.csv"
HISTORY_CSV = _LIVE if _LIVE.exists() else DATA / "demand_history.csv"
REAL_CUTOFF = "2026-05-22"      # last real (non-synthetic) data date, for the honest footnote
FUEL_ORDER = ["Euro95", "Diesel", "Super98", "AdBlue", "LPG"]

# Version 5 simulation constants (see report §6.2): deliveries are hard-capped at a tank
# capacity proxy, and the penalty separates feasible carryover from undeliverable volume.
CAPACITY_MULTIPLIER = 1.3
STOCKOUT_WEIGHT, CARRY_WEIGHT, REPLAN_WEIGHT = 10, 1, 5


@functools.lru_cache(maxsize=1)
def _history():
    raw = pd.read_csv(HISTORY_CSV, low_memory=False)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    return raw


@functools.lru_cache(maxsize=1)
def _heatmap():
    raw = _history()
    piv = raw.pivot_table(index="station_code", columns="product", values="daily_demand", aggfunc="mean")
    piv = piv.reindex(columns=["P1", "P3", "P2", "P4", "P5"])
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    return {"stations": list(piv.index),
            "products": ["P1·Euro95", "P3·Diesel", "P2·Super98", "P4·AdBlue", "P5·LPG"],
            "values": [[None if pd.isna(v) else round(float(v)) for v in r] for r in piv.values]}


@functools.lru_cache(maxsize=1)
def _sim_preds():
    """Backtest slice produced by make_sim_data.py: actual + naive + P50/P95 per station-product-day."""
    sp = pd.read_csv(WEBAPP_DATA / "sim_predictions.csv")
    sp["date"] = pd.to_datetime(sp["date"])
    return sp


def _capacity(station, product, before):
    """Tank capacity proxy = CAPACITY_MULTIPLIER x heaviest complete 7-day volume before the window."""
    raw = _history()
    g = raw[(raw.station_code == station) & (raw["product"] == product) & (raw.date < before)]
    if g.empty:
        return None
    weekly = g.sort_values("date")["daily_demand"].rolling(7, min_periods=7).sum().max()
    if not weekly or not np.isfinite(weekly) or weekly <= 0:
        return None
    return float(weekly) * CAPACITY_MULTIPLIER


def _sim(station=None, product=None):
    """Weekly order-up-to simulation with a hard capacity cap (Version 5 methodology)."""
    sp = _sim_preds()
    if not station or not product:
        station, product = sp.groupby(["station_code", "product"])["actual"].sum().idxmax()
    g = sp[(sp.station_code == station) & (sp["product"] == product)].sort_values("date")
    if g.empty:
        station, product = sp.groupby(["station_code", "product"])["actual"].sum().idxmax()
        g = sp[(sp.station_code == station) & (sp["product"] == product)].sort_values("date")

    cap = _capacity(station, product, g["date"].min()) or max(float(g["actual"].sum()), 1.0)
    g = g.assign(week=g["date"].dt.isocalendar().week.astype(int) + g["date"].dt.year * 100)

    def run(col):
        """Return (stock curve, stockout days, undeliverable litres) for one forecast column."""
        stock = cap / 2.0
        curve, stockout, undeliv = [], 0, 0.0
        for _, w in g.groupby("week", sort=False):
            desired = max(0.0, float(w[col].clip(lower=0).sum()) - stock)
            delivered = min(desired, max(0.0, cap - stock))
            undeliv += desired - delivered
            stock += delivered
            for demand in w["actual"].clip(lower=0):
                if demand > stock:
                    stockout += 1
                    stock = 0.0
                else:
                    stock -= demand
                curve.append(round(stock))
        return curve, stockout, round(undeliv)

    cols = {"naive": "naive", "p50": "pred_p50", "p95": "pred_p95"}
    res = {k: run(c) for k, c in cols.items()}
    return {"dates": [d.strftime("%Y-%m-%d") for d in g["date"]],
            "actual": [round(float(v)) for v in g["actual"].values],
            "naive": res["naive"][0], "p50": res["p50"][0], "p95": res["p95"][0],
            "capacity": round(cap), "station": station, "product": product,
            "stockout": {k: res[k][1] for k in res},
            "undeliverable": {k: res[k][2] for k in res}}


@api_view(["GET"])
def stations(r): return Response(StationSerializer(Station.objects.all(), many=True).data)

@api_view(["GET"])
def products(r): return Response(ProductMapSerializer(ProductMap.objects.all(), many=True).data)

@api_view(["GET"])
def benchmark(r): return Response(BenchmarkSerializer(BenchmarkMetric.objects.all(), many=True).data)

@api_view(["GET"])
def penalty(r): return Response(PenaltySerializer(PenaltyResult.objects.all(), many=True).data)

@api_view(["GET"])
def kpis(r): return Response(KpiSerializer(Kpi.objects.all(), many=True).data)

@api_view(["GET"])
def sim(r): return Response(_sim(r.GET.get("station"), r.GET.get("product")))


PRODUCT_FUEL = {"P1": "Euro95", "P2": "Super98", "P3": "Diesel", "P4": "AdBlue", "P5": "LPG"}
HISTORY_DAYS = 84      # weeks of actuals shown before the forecast window


@api_view(["GET"])
def forecast(r):
    """Actual history (last ~12 weeks) + the model's forecast for the planning week.

    Each row carries `actual` (real/observed litres, null for future) and `p50/p90/p95`
    (forecast, null for history) so the chart can draw one continuous timeline.
    """
    st, pr = r.GET.get("station"), r.GET.get("product")

    fq = Forecast.objects.select_related("station").all()
    if st:
        fq = fq.filter(station__code=st)
    if pr:
        fq = fq.filter(product=pr)
    fq = fq.order_by("station__code", "product", "date")
    out = [dict(date=str(f.date), station=f.station.code, product=f.product, fuel=f.fuel,
                actual=None, p50=f.p50, p90=f.p90, p95=f.p95) for f in fq]

    fc_start = Forecast.objects.order_by("date").values_list("date", flat=True).first()
    if fc_start is not None:
        fc_start = pd.Timestamp(fc_start)
        hist = _history()
        h = hist[(hist["date"] >= fc_start - pd.Timedelta(days=HISTORY_DAYS)) & (hist["date"] < fc_start)]
        if st:
            h = h[h["station_code"] == st]
        if pr:
            h = h[h["product"] == pr]
        h = h[["date", "station_code", "product", "daily_demand"]].dropna(subset=["daily_demand"])
        for row in h.itertuples(index=False):
            out.append(dict(date=row.date.strftime("%Y-%m-%d"), station=row.station_code,
                            product=row.product, fuel=PRODUCT_FUEL.get(row.product, row.product),
                            actual=round(float(row.daily_demand), 1), p50=None, p90=None, p95=None))
    return Response(out)


@api_view(["GET"])
def dashboard(r):
    """Whole dashboard payload in one call."""
    fc = pd.DataFrame(Forecast.objects.values("date", "fuel", "p50", "p95"))
    fc["date"] = fc["date"].astype(str)
    dates = sorted(fc["date"].unique())
    fuel_daily = {f: [round(float(fc[(fc.date == d) & (fc.fuel == f)].p50.sum())) for d in dates] for f in FUEL_ORDER}
    tot_p50 = [round(float(fc[fc.date == d].p50.sum())) for d in dates]
    tot_p95 = [round(float(fc[fc.date == d].p95.sum())) for d in dates]
    fuel_tot = [{"fuel": f, "liters": int(fc[fc.fuel == f].p50.sum())} for f in FUEL_ORDER]
    geo = [{"s": s.code, "lon": s.lon, "lat": s.lat, "d": s.total_demand, "brand": s.brand}
           for s in Station.objects.all()]
    brands = [{"brand": b, "n": Station.objects.filter(brand=b).count()}
              for b in sorted(Station.objects.values_list("brand", flat=True).distinct()) if b]
    last_dt = _history()["date"].max().date()
    last_actual = last_dt.strftime("%Y-%m-%d")
    now = datetime.date.today()
    data_age = (now - last_dt).days
    return Response({
        "meta": {"today": dates[0], "last_actual": last_actual, "start": dates[0], "end": dates[-1],
                 "server_now": now.strftime("%Y-%m-%d"),
                 "data_as_of": last_actual,
                 "data_age_days": data_age,
                 "data_fresh": data_age <= 7,
                 "real_cutoff": REAL_CUTOFF,
                 "n_stations": Station.objects.count(),
                 "n_series": Forecast.objects.values("station", "product").distinct().count(),
                 "brands": brands},
        "kpis": KpiSerializer(Kpi.objects.all(), many=True).data,
        "benchmark": BenchmarkSerializer(BenchmarkMetric.objects.all(), many=True).data,
        "product_map": ProductMapSerializer(ProductMap.objects.all().order_by("-volume_share"), many=True).data,
        "penalty": PenaltySerializer(PenaltyResult.objects.all(), many=True).data,
        "dates": dates, "fuel_daily": fuel_daily, "tot_p50": tot_p50, "tot_p95": tot_p95,
        "fuel_totals": fuel_tot, "geo": geo, "station_product": _heatmap(), "sim": _sim(),
    })


@api_view(["GET"])
def predict_live(r):
    """Run the Version 5 model bundle directly (proof the deployed model works)."""
    from .ml_service import predict
    recs = predict(r.GET.get("start") or None, r.GET.get("end") or None)
    return Response({"count": len(recs), "forecast": recs})
