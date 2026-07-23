# Fuel Demand Forecasting — Prototype Handover

Station-product-day demand forecasting for weekly fuel replenishment planning, built to
feed the **ROVER** optimiser. This repository is the **validated research prototype**
described in the final assignment report: a single, self-contained notebook that runs the
entire workflow end to end — data loading → EDA → leakage-safe feature engineering →
chronological backtest → feature ablation → paired-bootstrap significance test →
quantile-demand layer → capacity-bounded inventory stress test.

> **Scope note (matches report §8.1).** What exists today is the notebook below. A modular
> production pipeline (separate `features.py` / `train.py` / `evaluate.py` / `predict.py` /
> `simulate.py` on a recurring schedule, with monitoring and drift detection) is a
> *recommendation for the next phase*, **not** something built here. This repo deliberately
> ships only what the report validated, so code and report stay consistent.

---

## What's in this repo

```
cofano-fuel-forecast/
├── README.md                 # this file
├── requirements.txt          # Python dependencies
├── full_pipeline.ipynb       # THE product: full workflow, run top-to-bottom
└── data/
    ├── demand_history.csv     # enriched demand dataset (model input #1)
    └── station_metadata.csv   # station geography/metadata (model input #2)
```

Running the notebook creates an `outputs/` folder (metrics tables, forecast CSVs, charts).
`outputs/` and any model artifact are intentionally git-ignored — they are **regenerated**
by running the notebook, not stored.

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

---

## The model, and how to get it

The notebook **trains the models itself** as part of the backtest and quantile stages — it
is an end-to-end pipeline you re-run and audit in one sitting, not a frozen binary. There is
therefore **no pre-built `model_bundle.pkl` committed** (an earlier bundle existed but was
produced by superseded code and trained on non-anonymised data, so it is not shipped here).

- **Point forecast:** an XGBoost ensemble (Tweedie + absolute-error objectives, bagged),
  clipped at zero.
- **Safety stock:** quantile models (`reg:quantileerror`) producing **P50 / P90 / P95**.

If you want a standalone serialised model for serving, add a short export cell at the end of
the notebook (fit on all available history, `joblib.dump(...)`) — we can provide this on
request.

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
