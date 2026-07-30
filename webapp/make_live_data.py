"""
Build a "live" demand history for the demo dashboard.

The real anonymised dataset ends 2026-05-22. To keep the dashboard's planning week current, this
appends a synthetic tail from the day after the last real date up to today, using a seasonal-naive
estimate: each synthetic day copies the matching day ~one year earlier (same station-product), which
carries realistic weekday/seasonal/holiday structure. Synthetic rows are flagged `is_synthetic=1`.

The canonical data/demand_history.csv is NOT modified — this only writes webapp/data/demand_history_live.csv.

    python webapp/make_live_data.py
"""
import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL = REPO_ROOT / "data" / "demand_history.csv"
OUT = REPO_ROOT / "webapp" / "data" / "demand_history_live.csv"


def main():
    real = pd.read_csv(REAL, low_memory=False)
    real["date"] = pd.to_datetime(real["date"], errors="coerce")
    if "is_synthetic" not in real.columns:
        real["is_synthetic"] = 0

    last_real = real["date"].max().normalize()
    target_end = pd.Timestamp(datetime.date.today())
    if target_end <= last_real:
        real.to_csv(OUT, index=False)
        print(f"Nothing to extend (today {target_end.date()} <= data {last_real.date()}).")
        return

    lookup = {(r.station_code, r.product, r.date): i for i, r in
              zip(real.index, real[["station_code", "product", "date"]].itertuples(index=False))}
    future_dates = pd.date_range(last_real + pd.Timedelta(days=1), target_end, freq="D")
    OFFSETS = [364, 371, 357, 365, 358, 350]      # ~1 year back, snap to same weekday-ish

    new_rows = []
    for (station, product), _ in real.groupby(["station_code", "product"]):
        for d in future_dates:
            src = None
            for off in OFFSETS:
                key = (station, product, d - pd.Timedelta(days=off))
                if key in lookup:
                    src = real.loc[lookup[key]].copy()
                    break
            if src is None:
                continue
            src["date"] = d
            src["station_code"] = station
            src["product"] = product
            src["year"] = d.year
            src["month"] = d.month
            src["day_of_week"] = d.dayofweek
            src["is_weekend"] = int(d.dayofweek >= 5)
            src["is_synthetic"] = 1
            new_rows.append(src)

    synth = pd.DataFrame(new_rows)
    live = pd.concat([real, synth], ignore_index=True).sort_values(
        ["station_code", "product", "date"]).reset_index(drop=True)
    live["date"] = live["date"].dt.strftime("%Y-%m-%d")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    live.to_csv(OUT, index=False)
    print(f"Real rows: {len(real):,} | synthetic appended: {len(synth):,} "
          f"({future_dates[0].date()} -> {future_dates[-1].date()})")
    print(f"Live dataset -> {OUT}  (total {len(live):,} rows, ends {target_end.date()})")


if __name__ == "__main__":
    main()
