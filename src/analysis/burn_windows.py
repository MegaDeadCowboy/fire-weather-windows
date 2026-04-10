"""
burn_windows.py
---------------
Applies USFS burn window threshold logic to processed RAWS observations.

Thresholds (configurable in config.py or passed at runtime):
    RH:    25 – 55 %
    Wind:  5  – 15 mph
    Temp:  < 90 °F

Outputs
-------
hourly_flags(df)   → DataFrame with per-hour boolean flags + composite burn_window column
daily_windows(df)  → Daily aggregates: burn_window_hours, pct_day_viable, window_quality

Usage
-----
    from src.analysis.burn_windows import load_and_flag, daily_windows

    hourly = load_and_flag()          # uses default processed CSV path
    daily  = daily_windows(hourly)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Default paths & thresholds — override via function args or config.py
# ---------------------------------------------------------------------------

PROCESSED_CSV = Path("data/processed/raws/raws_combined_20250410_20260410.csv")

DEFAULT_THRESHOLDS = {
    "rh_min":   25.0,   # %
    "rh_max":   55.0,   # %
    "wind_min":  5.0,   # mph
    "wind_max": 15.0,   # mph
    "temp_max": 90.0,   # °F
}

# Try to pull from config.py if it exists
try:
    from src.config import THRESHOLDS  # type: ignore
    DEFAULT_THRESHOLDS.update(THRESHOLDS)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_processed(path: Path | str = PROCESSED_CSV) -> pd.DataFrame:
    """
    Load the combined processed RAWS CSV produced by raws_ingest.py.

    Expects columns (names are normalised below):
        station_id | datetime | air_temp | relative_humidity | wind_speed | wind_direction

    Returns a DataFrame with a tz-naive UTC datetime index.
    """
    df = pd.read_csv(path, low_memory=False)

    # ---- normalise column names to lowercase with underscores ----
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    # ---- print actual columns so mismatches are easy to diagnose ----
    print(f"  Columns found: {list(df.columns)}")

    # ---- canonical column aliases — covers Synoptic, RAWS, and common variants ----
    rename_map = {
        # temperature
        "air_temp":          "temp_f",
        "temperature":       "temp_f",
        "temp":              "temp_f",
        "air_temperature":   "temp_f",
        # relative humidity
        "relative_humidity": "rh",
        "humidity":          "rh",
        "rh_pct":            "rh",       # this repo's processed CSV
        "rel_humidity":      "rh",
        # wind speed
        "wind_speed":        "wind_mph",
        "windspeed":         "wind_mph",
        "wind_spd":          "wind_mph",
        "wind_speed_mph":    "wind_mph",  # this repo's processed CSV
        # wind direction
        "wind_direction":    "wind_dir",
        "winddirection":     "wind_dir",
        "wind_dir_deg":      "wind_dir",  # this repo's processed CSV
        # datetime
        "date_time":         "datetime",
        "timestamp":         "datetime",
        "time":              "datetime",
        "obs_time":          "datetime",
        "valid_time":        "datetime",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # ---- last-resort fuzzy match for any remaining unmapped columns ----
    # catches e.g. 'air_temp_value_1', 'wind_speed_set_1' from Synoptic derived names
    col_map = {}
    for col in df.columns:
        if col in ("temp_f", "rh", "wind_mph", "wind_dir", "datetime", "station_id"):
            continue  # already canonical
        if "temp" in col and "temp_f" not in df.columns:
            col_map[col] = "temp_f"
        elif ("humidity" in col or col.startswith("rh")) and "rh" not in df.columns:
            col_map[col] = "rh"
        elif "wind" in col and "speed" in col and "wind_mph" not in df.columns:
            col_map[col] = "wind_mph"
        elif "wind" in col and "dir" in col and "wind_dir" not in df.columns:
            col_map[col] = "wind_dir"
    if col_map:
        print(f"  Fuzzy-matched columns: {col_map}")
        df.rename(columns=col_map, inplace=True)

    print(f"  Columns after rename: {list(df.columns)}")

    # ---- required column check — fail loudly with diagnosis ----
    required = {"station_id", "datetime", "temp_f", "rh", "wind_mph"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"\n\nMissing required columns after renaming: {missing}\n"
            f"Columns present in CSV: {list(df.columns)}\n\n"
            f"Fix: add entries to rename_map in load_processed() to map your CSV's column "
            f"names to the canonical names: temp_f, rh, wind_mph, datetime, station_id.\n"
            f"Run: head -1 data/processed/raws/raws_combined_*.csv  to see exact names."
        )

    # ---- parse datetime ----
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df["datetime"] = df["datetime"].dt.tz_convert(None)   # drop tz for simplicity
    df = df.dropna(subset=["datetime"])
    df = df.sort_values(["station_id", "datetime"]).reset_index(drop=True)

    # ---- coerce numeric ----
    for col in ["temp_f", "rh", "wind_mph", "wind_dir"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    print(
        f"Loaded {len(df):,} records | "
        f"{df['station_id'].nunique()} stations | "
        f"{df['datetime'].min().date()} → {df['datetime'].max().date()}"
    )
    return df


# ---------------------------------------------------------------------------
# Threshold flagging
# ---------------------------------------------------------------------------

def hourly_flags(
    df: pd.DataFrame,
    thresholds: dict | None = None,
) -> pd.DataFrame:
    """
    Add boolean threshold columns and a composite burn_window flag to an hourly DataFrame.

    New columns added
    -----------------
    rh_ok         : RH within [rh_min, rh_max]
    wind_ok       : wind speed within [wind_min, wind_max]
    temp_ok       : temp below temp_max
    vars_present  : count of non-null threshold variables for this hour
    burn_window   : True when rh_ok AND wind_ok AND temp_ok (all three vars present)
    """
    t = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        t.update(thresholds)

    out = df.copy()

    # individual flags — NaN → False (conservatively not a burn window)
    out["rh_ok"]   = out["rh"].between(t["rh_min"],   t["rh_max"],   inclusive="both")
    out["wind_ok"] = out["wind_mph"].between(t["wind_min"], t["wind_max"], inclusive="both")
    out["temp_ok"] = out["temp_f"] < t["temp_max"]

    # fill NaN flags as False
    for col in ["rh_ok", "wind_ok", "temp_ok"]:
        out[col] = out[col].fillna(False)

    # track data completeness
    out["vars_present"] = (
        out["rh"].notna().astype(int)
        + out["wind_mph"].notna().astype(int)
        + out["temp_f"].notna().astype(int)
    )

    # composite — only flag when all three variables actually have data
    out["burn_window"] = out["rh_ok"] & out["wind_ok"] & out["temp_ok"] & (out["vars_present"] == 3)

    return out


# ---------------------------------------------------------------------------
# Daily aggregation
# ---------------------------------------------------------------------------

def daily_windows(
    df: pd.DataFrame,
    min_hours_for_quality: int = 20,
) -> pd.DataFrame:
    """
    Aggregate hourly flags to daily burn window scores.

    Parameters
    ----------
    df : hourly DataFrame with burn_window column (output of hourly_flags)
    min_hours_for_quality : minimum hours of data per day to assign a quality label

    Returns
    -------
    DataFrame with columns:
        station_id, date, burn_window_hours, pct_day_viable,
        rh_ok_hours, wind_ok_hours, temp_ok_hours,
        data_hours, window_quality, any_window
    """
    if "burn_window" not in df.columns:
        df = hourly_flags(df)

    df = df.copy()
    df["date"] = df["datetime"].dt.date

    agg = (
        df.groupby(["station_id", "date"])
        .agg(
            burn_window_hours=("burn_window",   "sum"),
            rh_ok_hours=      ("rh_ok",         "sum"),
            wind_ok_hours=    ("wind_ok",        "sum"),
            temp_ok_hours=    ("temp_ok",        "sum"),
            data_hours=       ("vars_present",   lambda x: (x == 3).sum()),
        )
        .reset_index()
    )

    agg["date"] = pd.to_datetime(agg["date"])

    # percent of data-present hours that meet all thresholds
    agg["pct_day_viable"] = np.where(
        agg["data_hours"] > 0,
        agg["burn_window_hours"] / agg["data_hours"] * 100,
        np.nan,
    )

    # any_window: at least 1 viable hour that day
    agg["any_window"] = agg["burn_window_hours"] > 0

    # window quality label
    def _quality(row):
        if row["data_hours"] < min_hours_for_quality:
            return "insufficient_data"
        h = row["burn_window_hours"]
        if h == 0:
            return "no_window"
        elif h < 3:
            return "marginal"      # 1–2 hrs
        elif h < 6:
            return "partial"       # 3–5 hrs
        else:
            return "full"          # 6+ hrs — operationally useful window

    agg["window_quality"] = agg.apply(_quality, axis=1)

    # calendar helpers
    agg["month"]       = agg["date"].dt.month
    agg["week_of_year"]= agg["date"].dt.isocalendar().week.astype(int)
    agg["doy"]         = agg["date"].dt.dayofyear
    agg["season"]      = agg["month"].map(_month_to_season)

    return agg.sort_values(["station_id", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Multi-day window clusters
# ---------------------------------------------------------------------------

def find_window_clusters(
    daily: pd.DataFrame,
    min_consecutive: int = 2,
    quality_threshold: str = "partial",
) -> pd.DataFrame:
    """
    Identify consecutive-day burn window clusters — operationally important
    because multi-day windows allow smoke dispersal and re-entry.

    Parameters
    ----------
    daily              : output of daily_windows()
    min_consecutive    : minimum consecutive days to count as a cluster
    quality_threshold  : minimum window_quality level ('marginal'|'partial'|'full')

    Returns
    -------
    DataFrame with cluster_id, station_id, start_date, end_date, length_days, peak_quality
    """
    quality_rank = {"no_window": 0, "marginal": 1, "partial": 2, "full": 3, "insufficient_data": -1}
    min_rank = quality_rank.get(quality_threshold, 1)

    clusters = []

    for station, grp in daily.groupby("station_id"):
        grp = grp.sort_values("date").copy()
        grp["viable"] = grp["window_quality"].map(quality_rank).fillna(-1) >= min_rank

        # label consecutive viable runs
        grp["run_id"] = (grp["viable"] != grp["viable"].shift()).cumsum()
        runs = grp[grp["viable"]].groupby("run_id")

        for run_id, run in runs:
            if len(run) >= min_consecutive:
                clusters.append({
                    "station_id":   station,
                    "start_date":   run["date"].iloc[0],
                    "end_date":     run["date"].iloc[-1],
                    "length_days":  len(run),
                    "peak_hours":   run["burn_window_hours"].max(),
                    "mean_hours":   round(run["burn_window_hours"].mean(), 1),
                    "peak_quality": run["window_quality"].map(quality_rank).idxmax()
                                    if not run.empty else "unknown",
                    "month":        run["date"].iloc[0].month,
                    "season":       run["season"].iloc[0],
                })

    if not clusters:
        return pd.DataFrame()

    df_clusters = pd.DataFrame(clusters).reset_index(drop=True)
    df_clusters.index.name = "cluster_id"
    return df_clusters.reset_index()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_to_season(month: int) -> str:
    return {
        12: "winter", 1: "winter", 2: "winter",
        3:  "spring", 4: "spring", 5: "spring",
        6:  "summer", 7: "summer", 8: "summer",
        9:  "fall",  10: "fall",  11: "fall",
    }.get(month, "unknown")


def summarise_flags(hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Per-station summary of how often each variable is the limiting factor.

    Wind is split into two failure modes because they have different operational meanings:
      - wind_too_calm  (<  wind_min): poor smoke dispersal, fire may not carry
      - wind_too_strong(>  wind_max): loss-of-control risk

    Also computes limiting_factor: which single variable most constrains burn windows.
    """
    if "burn_window" not in hourly.columns:
        hourly = hourly_flags(hourly)

    t = DEFAULT_THRESHOLDS
    h = hourly.copy()
    complete = h["vars_present"].eq(3)

    total     = h.groupby("station_id").size().rename("total_hours")
    viable    = h.groupby("station_id")["burn_window"].sum().rename("burn_window_hours")
    rh_fail   = (~h["rh_ok"]   & complete).groupby(h["station_id"]).sum().rename("rh_fail_hours")
    wind_fail = (~h["wind_ok"] & complete).groupby(h["station_id"]).sum().rename("wind_fail_hours")
    temp_fail = (~h["temp_ok"] & complete).groupby(h["station_id"]).sum().rename("temp_fail_hours")

    # wind split: too calm vs too strong
    wind_calm   = (h["wind_mph"].lt(t["wind_min"])  & complete).groupby(h["station_id"]).sum().rename("wind_too_calm_hours")
    wind_strong = (h["wind_mph"].gt(t["wind_max"])  & complete).groupby(h["station_id"]).sum().rename("wind_too_strong_hours")

    # rh split: too dry vs too humid
    rh_dry  = (h["rh"].lt(t["rh_min"]) & complete).groupby(h["station_id"]).sum().rename("rh_too_dry_hours")
    rh_wet  = (h["rh"].gt(t["rh_max"]) & complete).groupby(h["station_id"]).sum().rename("rh_too_wet_hours")

    summary = pd.concat(
        [total, viable, rh_fail, rh_dry, rh_wet, wind_fail, wind_calm, wind_strong, temp_fail],
        axis=1
    ).reset_index()

    summary["pct_viable"] = (summary["burn_window_hours"] / summary["total_hours"] * 100).round(1)

    # dominant limiting factor per station
    def _limiting(row):
        candidates = {"rh": row["rh_fail_hours"], "wind": row["wind_fail_hours"], "temp": row["temp_fail_hours"]}
        top = max(candidates, key=candidates.get)
        if top == "wind":
            calm_pct   = row["wind_too_calm_hours"]   / max(row["wind_fail_hours"], 1)
            strong_pct = row["wind_too_strong_hours"] / max(row["wind_fail_hours"], 1)
            return "wind_too_strong" if strong_pct >= calm_pct else "wind_too_calm"
        if top == "rh":
            dry_pct = row["rh_too_dry_hours"] / max(row["rh_fail_hours"], 1)
            return "rh_too_dry" if dry_pct >= 0.5 else "rh_too_wet"
        return "temp"

    summary["limiting_factor"] = summary.apply(_limiting, axis=1)
    return summary


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Flag burn windows in processed RAWS data")
    parser.add_argument("--csv",    default=str(PROCESSED_CSV), help="Path to processed CSV")
    parser.add_argument("--output", default="data/processed/raws/daily_windows.csv")
    parser.add_argument("--clusters", action="store_true", help="Also output cluster CSV")
    args = parser.parse_args()

    raw   = load_processed(args.csv)
    flags = hourly_flags(raw)
    daily = daily_windows(flags)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out_path, index=False)
    print(f"Daily windows saved → {out_path}  ({len(daily):,} rows)")

    if args.clusters:
        clusters = find_window_clusters(daily)
        c_path = out_path.parent / "window_clusters.csv"
        clusters.to_csv(c_path, index=False)
        print(f"Clusters saved → {c_path}  ({len(clusters)} clusters found)")

    print("\n--- Variable failure summary ---")
    print(summarise_flags(flags).to_string(index=False))

# ---------------------------------------------------------------------------
# Install note: if jupyter is missing, run:
#   pip install jupyterlab
#   jupyter lab notebooks/02_burn_window_climatology.ipynb
# ---------------------------------------------------------------------------