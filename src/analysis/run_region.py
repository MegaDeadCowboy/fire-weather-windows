"""Run burn-window analysis for one region config.

    python -m src.analysis.run_region --region northeast

Writes results/<region>/:
  hours_in_window_by_month.csv   station x month, hours inside the window
  constraint_failures.csv        per station: hours failing each constraint (of complete hours)
  binding_constraint_region.csv  region totals: share of complete hours failing each constraint,
                                 and share where it is the ONLY failing constraint
"""
import argparse
from pathlib import Path

import pandas as pd

from src.analysis.burn_windows import hourly_flags, load_processed, summarise_flags
from src.regions import load

ap = argparse.ArgumentParser()
ap.add_argument("--region", required=True)
a = ap.parse_args()
cfg = load(a.region)
out_dir = Path("results") / a.region
out_dir.mkdir(parents=True, exist_ok=True)

df = load_processed(cfg.DATA_CSV)
df["station_id"] = df["station_id"].astype(str)
if cfg.STATIONS:
    df = df[df["station_id"].isin(cfg.STATIONS)]
h = hourly_flags(df, cfg.THRESHOLDS)
complete = h["vars_present"].eq(3)

h["month"] = h["datetime"].dt.month
months = h[complete].pivot_table(index="station_id", columns="month", values="burn_window",
                                 aggfunc="sum", fill_value=0)
months.to_csv(out_dir / "hours_in_window_by_month.csv")

summ = summarise_flags(h, cfg.THRESHOLDS)
summ.to_csv(out_dir / "constraint_failures.csv", index=False)

c = h[complete]
fails = pd.DataFrame({"rh": ~c["rh_ok"], "wind": ~c["wind_ok"],
                      "temp": ~c["temp_ok"], "rain": ~c["rain_ok"]})
n_fail = fails.sum(axis=1)
region = pd.DataFrame({
    "pct_complete_hours_failing": (fails.mean() * 100).round(1),
    "pct_complete_hours_sole_failure": (fails[n_fail == 1].sum() / len(c) * 100).round(1),
})
region.loc["ALL_window_open", "pct_complete_hours_failing"] = round(c["burn_window"].mean() * 100, 1)
region.to_csv(out_dir / "binding_constraint_region.csv")

print(f"region={a.region} stations={h['station_id'].nunique()} complete_hours={len(c)} | source: {cfg.SOURCE}")
print(region.to_string())
print(summ[["station_id", "pct_viable", "limiting_factor"]].to_string(index=False))
print(f"-> {out_dir}")
