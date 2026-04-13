"""
forecast_windows.py
-------------------
Applies USFS burn window threshold logic to NDFD forecast data and
compares forecast conditions against the historical climatological baseline.

Inputs:
    - forecast DataFrame from ndfd_ingest.py (station_id, valid_time,
      rh_forecast, wind_mph_forecast, temp_f_forecast)
    - climatology_monthly.csv and climatology_weekly.csv from Week 2

Outputs:
    - Hourly and daily flagged forecast DataFrames
    - Per-station anomaly scores vs. climatological baseline
    - Clean summary table ready for dashboard consumption

Usage:
    from src.analysis.forecast_windows import (
        apply_thresholds_to_forecast,
        daily_forecast_windows,
        compare_to_climatology,
        forecast_summary_table,
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths & logging
# ---------------------------------------------------------------------------

PROCESSED_DIR = Path("data/processed/raws")
FORECAST_CACHE_DIR = Path("data/processed/ndfd")
FORECAST_CACHE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold constants — sourced from src/config.py conventions
# Mirror burn_windows.py so thresholds stay in one place; import from
# config.py when that module exists.
# ---------------------------------------------------------------------------

RH_MIN = 25.0       # % — below this, fuels too dry / fire behavior extreme
RH_MAX = 55.0       # % — above this, fire won't carry
WIND_MIN = 5.0      # mph — below this, smoke dispersal inadequate
WIND_MAX = 15.0     # mph — above this, spotting / control risk
TEMP_MAX = 90.0     # °F — above this, fine fuel moisture critically low

# Quality tier thresholds (hours in a day with all variables in-window)
MARGINAL_HRS = 1    # 1–2 hrs
PARTIAL_HRS = 3     # 3–5 hrs
FULL_HRS = 6        # 6+ hrs — operationally meaningful

# Anomaly classification bins (forecast viable hrs minus climatological mean)
ABOVE_NORMAL_THRESH = 1.5   # hrs above mean → above_normal
BELOW_NORMAL_THRESH = -1.5  # hrs below mean → below_normal


# ---------------------------------------------------------------------------
# 1. Threshold application
# ---------------------------------------------------------------------------

def apply_thresholds_to_forecast(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply USFS burn window thresholds to each row of the forecast DataFrame.

    Expected input columns (from ndfd_ingest.py):
        station_id, valid_time, rh_forecast, wind_mph_forecast, temp_f_forecast

    Returns the input DataFrame with added boolean flag columns:
        rh_ok, wind_ok, temp_ok, burn_window, vars_present
    """
    df = forecast_df.copy()

    _validate_forecast_columns(df)

    df["rh_ok"] = (df["rh_forecast"] >= RH_MIN) & (df["rh_forecast"] <= RH_MAX)
    df["wind_ok"] = (
        (df["wind_mph_forecast"] >= WIND_MIN)
        & (df["wind_mph_forecast"] <= WIND_MAX)
    )
    df["temp_ok"] = df["temp_f_forecast"] <= TEMP_MAX

    # Count how many variables have non-null data for this timestep
    df["vars_present"] = (
        df["rh_forecast"].notna().astype(int)
        + df["wind_mph_forecast"].notna().astype(int)
        + df["temp_f_forecast"].notna().astype(int)
    )

    # Only flag burn_window=True when all three variables are present and pass
    all_present = df["vars_present"] == 3
    df["burn_window"] = all_present & df["rh_ok"] & df["wind_ok"] & df["temp_ok"]

    # Sub-threshold diagnostics — useful for understanding why a window failed
    df["rh_too_dry"] = df["rh_forecast"] < RH_MIN
    df["rh_too_wet"] = df["rh_forecast"] > RH_MAX
    df["wind_too_calm"] = df["wind_mph_forecast"] < WIND_MIN
    df["wind_too_strong"] = df["wind_mph_forecast"] > WIND_MAX
    df["temp_too_hot"] = df["temp_f_forecast"] > TEMP_MAX

    n_flagged = df["burn_window"].sum()
    n_total = len(df)
    log.info(
        "Threshold pass rate: %d / %d timesteps (%.1f%%)",
        n_flagged, n_total, 100 * n_flagged / max(n_total, 1),
    )

    return df


# ---------------------------------------------------------------------------
# 2. Daily aggregation
# ---------------------------------------------------------------------------

def daily_forecast_windows(forecast_flagged: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate hourly flagged forecast data to daily burn window scores.

    Input: output of apply_thresholds_to_forecast()

    Returns one row per (station_id, forecast_date) with:
        burn_window_hours   — count of hours in window that day
        pct_day_viable      — fraction of day with valid window
        any_window          — bool, at least 1 viable hour
        window_quality      — tier label: no_window / marginal / partial / full
        data_hours          — hours with complete variable coverage
        limiting_factor     — primary reason window fails (if it does)
    """
    df = forecast_flagged.copy()
    df["forecast_date"] = pd.to_datetime(df["valid_time"]).dt.date

    daily = (
        df.groupby(["station_id", "forecast_date"])
        .apply(_aggregate_day, include_groups=False)
        .reset_index()
    )

    return daily


def _aggregate_day(group: pd.DataFrame) -> pd.Series:
    """Per-day aggregation helper."""
    burn_hrs = group["burn_window"].sum()
    data_hrs = (group["vars_present"] == 3).sum()
    pct_viable = burn_hrs / max(data_hrs, 1)

    # Quality tier
    if burn_hrs == 0:
        quality = "no_window"
    elif burn_hrs < PARTIAL_HRS:
        quality = "marginal"
    elif burn_hrs < FULL_HRS:
        quality = "partial"
    else:
        quality = "full"

    # Limiting factor when no window exists
    limiting = _limiting_factor(group) if burn_hrs == 0 else "n/a"

    return pd.Series({
        "burn_window_hours": int(burn_hrs),
        "pct_day_viable": round(float(pct_viable), 3),
        "any_window": bool(burn_hrs > 0),
        "window_quality": quality,
        "data_hours": int(data_hrs),
        "limiting_factor": limiting,
        # Pass-rate per variable — useful for marginal days
        "rh_pass_pct": round(group["rh_ok"].mean(), 3),
        "wind_pass_pct": round(group["wind_ok"].mean(), 3),
        "temp_pass_pct": round(group["temp_ok"].mean(), 3),
    })


def _limiting_factor(group: pd.DataFrame) -> str:
    """
    Identify the primary variable preventing a burn window.
    Mirrors logic in burn_windows.py summarise_flags().
    """
    fail_counts = {
        "rh_too_wet": group.get("rh_too_wet", pd.Series(dtype=bool)).sum(),
        "rh_too_dry": group.get("rh_too_dry", pd.Series(dtype=bool)).sum(),
        "wind_too_calm": group.get("wind_too_calm", pd.Series(dtype=bool)).sum(),
        "wind_too_strong": group.get("wind_too_strong", pd.Series(dtype=bool)).sum(),
        "temp_too_hot": group.get("temp_too_hot", pd.Series(dtype=bool)).sum(),
    }
    if not any(fail_counts.values()):
        return "unknown"
    return max(fail_counts, key=fail_counts.get)


# ---------------------------------------------------------------------------
# 3. Climatological comparison
# ---------------------------------------------------------------------------

def compare_to_climatology(
    forecast_daily: pd.DataFrame,
    climatology_monthly: pd.DataFrame,
    station_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    For each forecast day, look up the climatological baseline for that
    station × month and compute an anomaly score.

    Parameters
    ----------
    forecast_daily : output of daily_forecast_windows()
    climatology_monthly : loaded from data/processed/raws/climatology_monthly.csv
        Expected columns: station_id, month, viable_day_pct, full_window_day_pct,
        mean_viable_hours (or similar — see _normalise_climo_columns())
    station_id : if provided, filter to a single station

    Returns forecast_daily with added columns:
        climo_mean_viable_hrs   — historical mean viable hours for this month
        climo_viable_day_pct    — historical viable day frequency for this month
        anomaly_hrs             — forecast_viable_hrs minus climo_mean
        anomaly_label           — above_normal / near_normal / below_normal
        climo_data_available    — bool, False when no climo match found
    """
    df = forecast_daily.copy()
    climo = _normalise_climo_columns(climatology_monthly.copy())

    if station_id:
        df = df[df["station_id"] == station_id].copy()

    df["forecast_date"] = pd.to_datetime(df["forecast_date"])
    df["month"] = df["forecast_date"].dt.month

    df = df.merge(
        climo[["station_id", "month", "climo_mean_viable_hrs", "climo_viable_day_pct"]],
        on=["station_id", "month"],
        how="left",
    )

    df["climo_data_available"] = df["climo_mean_viable_hrs"].notna()

    df["anomaly_hrs"] = df["burn_window_hours"] - df["climo_mean_viable_hrs"]

    df["anomaly_label"] = df["anomaly_hrs"].apply(_classify_anomaly)

    log.info(
        "Climatological comparison complete. %d / %d rows have climo baseline.",
        df["climo_data_available"].sum(), len(df),
    )

    return df


def _normalise_climo_columns(climo: pd.DataFrame) -> pd.DataFrame:
    """
    Map climatology_monthly.csv columns to the names expected downstream.

    Confirmed CSV schema (from data/processed/raws/climatology_monthly.csv):
        station_id, month, viable_days, total_days, mean_window_hours,
        median_window_hours, full_window_days, pct_viable_days,
        pct_full_days, month_name

    Target columns for comparison logic:
        climo_mean_viable_hrs  — mean viable hours per day this month
        climo_viable_day_pct   — fraction of days with any viable window

    Also handles legacy or alternate column names in case the CSV was
    regenerated with different Week 2 code.
    """
    log.info("Climatology columns found: %s", climo.columns.tolist())

    # --- Mean viable hours per day ---
    # mean_window_hours from Week 2 is hours per viable day, not per calendar day.
    # Convert to per-calendar-day by multiplying by viable day fraction.
    # This makes it directly comparable to burn_window_hours (0–24 scale).
    if "mean_window_hours" in climo.columns and "pct_viable_days" in climo.columns:
        pct = climo["pct_viable_days"]
        # pct_viable_days is whole-number percent (e.g. 93.5 = 93.5%) — normalise
        if pct.dropna().median() > 1.0:
            pct = pct / 100.0
        climo["climo_mean_viable_hrs"] = climo["mean_window_hours"] * pct
        log.info(
            "climo_mean_viable_hrs derived from mean_window_hours × pct_viable_days/100"
        )
    else:
        # Fallback rename map for alternate column names
        fallback_hrs = {
            "mean_viable_hours":      "climo_mean_viable_hrs",
            "viable_hours_mean":      "climo_mean_viable_hrs",
            "avg_viable_hrs":         "climo_mean_viable_hrs",
            "burn_window_hours_mean": "climo_mean_viable_hrs",
            "mean_burn_window_hours": "climo_mean_viable_hrs",
        }
        for src, dst in fallback_hrs.items():
            if src in climo.columns:
                climo = climo.rename(columns={src: dst})
                log.info("climo_mean_viable_hrs mapped from '%s'", src)
                break

    # --- Viable day fraction ---
    if "pct_viable_days" in climo.columns:
        pct = climo["pct_viable_days"].copy()
        if pct.dropna().median() > 1.0:
            pct = pct / 100.0
        climo["climo_viable_day_pct"] = pct
    else:
        fallback_pct = {
            "viable_day_pct":  "climo_viable_day_pct",
            "any_window_pct":  "climo_viable_day_pct",
            "pct_days_viable": "climo_viable_day_pct",
            "viable_days_pct": "climo_viable_day_pct",
        }
        for src, dst in fallback_pct.items():
            if src in climo.columns:
                climo = climo.rename(columns={src: dst})
                if climo["climo_viable_day_pct"].dropna().median() > 1.0:
                    climo["climo_viable_day_pct"] = climo["climo_viable_day_pct"] / 100.0
                break

    # --- Full window fraction (bonus context for dashboard) ---
    if "pct_full_days" in climo.columns:
        pct_full = climo["pct_full_days"].copy()
        if pct_full.dropna().median() > 1.0:
            pct_full = pct_full / 100.0
        climo["climo_full_day_pct"] = pct_full

    # --- Final guard ---
    if "climo_mean_viable_hrs" not in climo.columns:
        log.error(
            "Could not derive climo_mean_viable_hrs from columns: %s. "
            "Anomaly scores will be NaN.",
            climo.columns.tolist(),
        )
        climo["climo_mean_viable_hrs"] = np.nan

    if "climo_viable_day_pct" not in climo.columns:
        climo["climo_viable_day_pct"] = np.nan

    # Sanity check: values must be 0–24 hr/day scale
    max_val = climo["climo_mean_viable_hrs"].max()
    if max_val > 24:
        log.warning(
            "climo_mean_viable_hrs max=%.1f still exceeds 24 after transforms — "
            "check climatology_monthly.csv units.", max_val
        )

    return climo


def _classify_anomaly(anomaly_hrs: float) -> str:
    """Classify anomaly score into three bins."""
    if pd.isna(anomaly_hrs):
        return "unknown"
    if anomaly_hrs >= ABOVE_NORMAL_THRESH:
        return "above_normal"
    if anomaly_hrs <= BELOW_NORMAL_THRESH:
        return "below_normal"
    return "near_normal"


# ---------------------------------------------------------------------------
# 4. Summary table for dashboard
# ---------------------------------------------------------------------------

def forecast_summary_table(
    forecast_daily: pd.DataFrame,
    climatology_monthly: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produce the clean output table consumed by the Streamlit dashboard.

    One row per (station_id, forecast_date).

    Columns:
        station_id, forecast_date, burn_window_hours, window_quality,
        any_window, limiting_factor, rh_pass_pct, wind_pass_pct,
        climo_mean_viable_hrs, climo_viable_day_pct,
        anomaly_hrs, anomaly_label, week_of_year, month, season
    """
    compared = compare_to_climatology(forecast_daily, climatology_monthly)

    compared["forecast_date"] = pd.to_datetime(compared["forecast_date"])
    compared["week_of_year"] = compared["forecast_date"].dt.isocalendar().week.astype(int)
    compared["season"] = compared["month"].apply(_month_to_season)

    # Column ordering for dashboard readability
    col_order = [
        "station_id",
        "forecast_date",
        "week_of_year",
        "month",
        "season",
        "burn_window_hours",
        "window_quality",
        "any_window",
        "pct_day_viable",
        "limiting_factor",
        "rh_pass_pct",
        "wind_pass_pct",
        "temp_pass_pct",
        "climo_mean_viable_hrs",
        "climo_viable_day_pct",
        "anomaly_hrs",
        "anomaly_label",
        "climo_data_available",
        "data_hours",
    ]
    available_cols = [c for c in col_order if c in compared.columns]
    summary = compared[available_cols].sort_values(["station_id", "forecast_date"])

    out_path = FORECAST_CACHE_DIR / "forecast_summary.csv"
    summary.to_csv(out_path, index=False)
    log.info("Forecast summary written to %s (%d rows)", out_path, len(summary))

    return summary


# ---------------------------------------------------------------------------
# 5. Convenience loaders
# ---------------------------------------------------------------------------

def load_climatology_monthly(
    path: Optional[Path] = None,
) -> pd.DataFrame:
    """Load climatology_monthly.csv from standard location."""
    p = path or PROCESSED_DIR / "climatology_monthly.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"climatology_monthly.csv not found at {p}. "
            "Run src/analysis/climatology.py first (Week 2 deliverable)."
        )
    climo = pd.read_csv(p)
    log.info("Loaded climatology_monthly: %d rows from %s", len(climo), p)
    return climo


def load_forecast_summary(path: Optional[Path] = None) -> pd.DataFrame:
    """Load cached forecast_summary.csv if it exists."""
    p = path or FORECAST_CACHE_DIR / "forecast_summary.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"forecast_summary.csv not found at {p}. "
            "Run forecast_summary_table() to generate it."
        )
    df = pd.read_csv(p, parse_dates=["forecast_date"])
    log.info("Loaded forecast summary: %d rows from %s", len(df), p)
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_to_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def _validate_forecast_columns(df: pd.DataFrame) -> None:
    required = {"station_id", "valid_time", "rh_forecast", "wind_mph_forecast", "temp_f_forecast"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Forecast DataFrame is missing required columns: {missing}\n"
            f"Found: {list(df.columns)}\n"
            "Check ndfd_ingest.py output — wind must already be converted from knots to mph."
        )


# ---------------------------------------------------------------------------
# CLI entry point — useful for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply burn window logic to cached NDFD forecast data."
    )
    parser.add_argument(
        "--forecast",
        type=Path,
        default=FORECAST_CACHE_DIR / "forecast_parsed.csv",
        help="Path to parsed forecast CSV from ndfd_ingest.py",
    )
    parser.add_argument(
        "--climo",
        type=Path,
        default=PROCESSED_DIR / "climatology_monthly.csv",
        help="Path to climatology_monthly.csv from Week 2",
    )
    parser.add_argument(
        "--station",
        type=str,
        default=None,
        help="Optional: filter output to a single station_id",
    )
    args = parser.parse_args()

    forecast_raw = pd.read_csv(args.forecast, parse_dates=["valid_time"])
    climo = load_climatology_monthly(args.climo)

    flagged = apply_thresholds_to_forecast(forecast_raw)
    daily = daily_forecast_windows(flagged)
    summary = forecast_summary_table(daily, climo)

    if args.station:
        summary = summary[summary["station_id"] == args.station]

    print(summary.to_string(index=False))