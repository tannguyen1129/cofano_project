# Fuel Demand Forecasting — Prototype Handover

Station-product-day demand forecasting for weekly fuel replenishment planning, built to
feed the **ROVER** optimiser. This repository is the **validated research prototype**
described in the final assignment report: a single, self-contained notebook that runs the
entire workflow end to end — data loading → EDA → leakage-safe feature engineering →
chronological backtest → feature ablation → paired-bootstrap significance test →
quantile-demand layer → capacity-bounded inventory stress test.

> **Scope note (consistent with report §8.1).** The **notebook is the validated artifact** — it
> is where the results in the report were produced and audited end to end. Alongside it, this repo
> ships three small helper scripts (`pipeline.py`, `train_model.py`, `predict.py`) that reuse the
> notebook's *exact* Version 5 feature engineering so the delivered model is directly runnable.
> These are lightweight serving utilities, **not** the full productionised pipeline: scheduled
> retraining, monitoring, and drift detection remain the recommended next phase (see below).

---

## What's in this repo

```
cofano-fuel-forecast/
├── README.md                 # this file
├── requirements.txt          # Python dependencies
├── full_pipeline.ipynb       # validated workflow: EDA → backtest → ablation → quantiles → simulation
├── pipeline.py               # shared Version 5 feature engineering (imported by the scripts)
├── train_model.py            # fit the model bundle on all history  → model/model_bundle.pkl
├── predict.py                # run the model                        → outputs/forecast.csv (next 7 days)
├── model/
│   └── model_bundle.pkl      # trained models: point ensemble + P50/P90/P95 quantiles + encodings
├── data/
│   ├── demand_history.csv     # enriched demand dataset (model input #1)
│   └── station_metadata.csv   # station geography/metadata (model input #2)
└── webapp/                   # demo dashboard (Django + Next.js) — see section below
```

The notebook and `predict.py` write to an `outputs/` folder (metrics, forecasts, charts), which is
git-ignored and **regenerated** on each run. The trained **`model/model_bundle.pkl` is committed** so
the project runs out of the box; you can also rebuild it from scratch with `train_model.py`.

---

## Quick start

**Option A — Local (Jupyter):**
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter notebook full_pipeline.ipynb
# Run all cells (Kernel ▸ Restart & Run All). ~a few minutes on a laptop.
```
The notebook auto-discovers the two CSVs in `./data/` (and in the working directory).

**Option B — Google Colab:**
1. Upload `full_pipeline.ipynb` to Colab.
2. Upload `demand_history.csv` and `station_metadata.csv` (to `/content` or a `data/` folder).
3. Runtime ▸ Run all.

**Option C — Run the model directly (no notebook):**
```bash
pip install -r requirements.txt

# Forecast the next 7 days using the committed model:
python predict.py                       # -> outputs/forecast.csv
python predict.py --start 2026-05-23 --horizon 7

# Rebuild the model from the data (optional, ~1-2 min):
python train_model.py                   # -> model/model_bundle.pkl
```

---

## The model

`model/model_bundle.pkl` is produced by `train_model.py`, which fits the **exact** models the
notebook validated on **all** eligible history (last 28 days held out only for early stopping):

- **Point forecast (`forecast`):** an XGBoost ensemble — Tweedie (variance power 1.4) +
  absolute-error objectives, averaged and clipped at zero.
- **Safety stock (`p50` / `p90` / `p95`):** quantile models (`reg:quantileerror`). At prediction
  time the three levels are rearranged to be non-crossing (P50 ≤ P90 ≤ P95).

The bundle is a dict: `point` (list of models), `quantile` (`P50/P90/P95`), `cat_maps`
(categorical encodings so prediction matches training), `features`, and `meta`. `predict.py`
loads it, extends each series with the requested horizon, rebuilds features via `pipeline.py`,
and writes forecasts. Because every feature uses history ≥ 7 days old, a full 7-day-ahead weekly
forecast is leakage-safe.

> Retrain periodically (`train_model.py`) as new sales data arrives. The model is **global** (one
> model across all station-product series), so new stations can be forecast without a per-station model.

---

## Data inputs (schema & anonymisation)

Both CSVs are **anonymised**: brand names and street addresses are removed, place names
blanked, and coordinates rounded to ~1 km. This keeps the data usable for modelling while
protecting station identities.

`station_metadata.csv` — one row per station:

| Column | Meaning |
|---|---|
| `station_code` | anonymised station id (e.g. `Z1`, `NB2`, `B1`) |
| `brand` | anonymised brand label (`Brand A` / `Brand B`) |
| `lat`, `lon` | rounded coordinates (~1 km) |
| `country_code` | `NL` / `BE` |
| `area_type` | `urban_center` / `suburban` / `rural` |

`demand_history.csv` — daily transaction/demand rows. Key columns used by the model:
`date`, `station_code`, `product` (P1–P5), `daily_demand` (target, litres),
`lat`/`lon`, `area_type`, `nearest_place_type`, `country_code`, calendar fields
(`is_public_holiday`, `is_school_holiday`, `day_of_week`, `month`, …). Weather, traffic and
fuel-price columns are present but were **excluded** from the production feature set (they did
not improve, or worsened, the robust configuration — see the report).

**Fuel mapping:** P1 = Euro95, P2 = Super98, P3 = Diesel, P4 = AdBlue, P5 = LPG.
Euro95 + Diesel are ~**92.7%** of volume and are the main operational benchmark.

> Coordinates are rounded but not fully un-locatable; the data is intended for the data owner
> (Cofano) and authorised recipients, not public release.

---

## What the pipeline produces (headline results)

From the final prototype (5 chronological folds, paired against the `lag_7` naive rule):

- **Accuracy:** selected model (Core + school-holiday features) reaches **WAPE 20.15%** overall
  and **19.29% on the main fuels** (Euro95 + Diesel), versus **25.48%** for the naive baseline.
- **Statistical significance:** the improvement's 95% paired-bootstrap interval is fully
  positive (unlike the weaker earlier phases).
- **Safety stock:** pooled **P95 coverage ≈ 94.7%** (a point/P50 forecast covers only ~half of
  demand days).
- **Inventory stress test (capacity-bounded):** at a 1.3× tank-capacity proxy, supplying the
  **P95** forecast instead of the naive rule cuts simulated station-product **stockout-day
  events from 1,401 → 29** and improves the aggregate weighted-proxy penalty by **14.6%**.

**How to read the stress test.** It is a *stress test of the forecast*, not a scheduling rule.
Deliveries are hard-capped at tank capacity; any volume that would exceed the remaining
headroom is counted as an *undeliverable / replan-trigger* event, not free "overfill". The
takeaway is that the model should hand ROVER **both** a point forecast (P50, for expected
consumption, delivery timing and truck-load sizing) **and** a safety-stock quantile (P95, for
protection against stockouts). ROVER then decides the final delivery quantity using real tank
capacities and routing constraints. The gap P95 − P50 is the tunable safety margin.

---

## Demo dashboard (`webapp/`) — prototype, outside the report's scope

A small web dashboard is included so the forecasts can be inspected visually. **It is a demo
prototype, not part of what the final report validated** — the report's results all come from the
notebook. It is included for convenience and has no authentication.

It does, however, run the **same Version 5 model**: the API loads `model/model_bundle.pkl` and
reuses `pipeline.py`, and the inventory panel uses the capacity-capped simulation (report §6.2),
not the superseded unbounded-overfill version.

```
webapp/
├── backend/            Django + DRF API (serves the built frontend too)
│   ├── serve.py        threaded WSGI launcher (binds 127.0.0.1 by default)
│   └── forecast/       models, views, serializers, ml_service.py (loads the v5 bundle)
├── frontend/           Next.js static export (source in app/, build output in out/)
├── data/               sim_predictions.csv — backtest slice replayed by the inventory panel
├── make_sim_data.py    regenerates that slice from the v5 pipeline
└── .env.example        required environment variables
```

**Run it:**
```bash
pip install -r requirements.txt django djangorestframework django-cors-headers

cp webapp/.env.example webapp/.env      # then edit, or just export the variables
export DJANGO_SECRET_KEY="<a long random string>"
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"

cd webapp/backend
python manage.py migrate
python manage.py seed                   # runs the v5 model to fill the forecast table
python serve.py 8080                    # http://127.0.0.1:8080
```

To rebuild the frontend after editing it: `cd webapp/frontend && npm install && npm run build`.
To refresh the inventory-panel data: `python webapp/make_sim_data.py`.

**Security notes.** `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` come from environment variables —
nothing is hardcoded. `serve.py` binds to `127.0.0.1` unless you set `HOST`.

The dashboard has no application-level login. If you need to reach it from another machine, set
`HOST=0.0.0.0` **together with** `DASHBOARD_USER` / `DASHBOARD_PASSWORD`: `serve.py` then requires
HTTP Basic credentials on every request, including the API. Without those two variables set, a
non-localhost bind is unauthenticated and the server prints a warning. Note that Basic Auth over
plain HTTP sends credentials base64-encoded, not encrypted — terminate TLS at a reverse proxy if
the dashboard is reachable over an untrusted network.

**Numbers shown.** The KPI, benchmark and inventory-penalty figures are the report's five-fold
Version 5 results. The interactive per-tank simulation replays a single combined out-of-sample
window (`make_sim_data.py`), so its per-series numbers illustrate behaviour rather than reproduce
the five-fold aggregates exactly.

---

## Notes for productionisation (next phase)

- Split the notebook sections into scheduled components (feature build / train / evaluate /
  predict / simulate) with monitoring and drift detection.
- Supply **real tank capacities** and routing constraints to replace the capacity proxy.
- Extend the future holiday calendar and retrain periodically as new sales data arrives.
- The model is **global** (one model across all station-product series), so new stations can be
  forecast without a per-station model.

---

*Authors: Vo Ngoc Tram Anh · Son Tan · Nguyen Huy Hoang. Prepared for Cofano.
Full methodology and results: see the final assignment report.*
