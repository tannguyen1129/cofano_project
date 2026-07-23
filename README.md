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
└── data/
    ├── demand_history.csv     # enriched demand dataset (model input #1)
    └── station_metadata.csv   # station geography/metadata (model input #2)
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
