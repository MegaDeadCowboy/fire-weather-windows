"""
climatology.py
--------------
Computes burn window climatology from daily window data produced by burn_windows.py.

Answers the Week 2 key questions:
  - Which stations have the most viable burn hours per year?
  - What months are peak window months across the PNW?
  - How much station-to-station variation exists within the same week?
  - Are there consistent multi-day window clusters?

All functions accept the output of daily_windows() and return clean DataFrames
ready for visualisation (matplotlib, plotly, or Streamlit).

Usage
-----
    from src.analysis.burn_windows import load_processed, hourly_flags, daily_windows
    from src.analysis.climatology import (
        monthly_climatology, weekly_climatology,
        seasonal_summary, station_annual_summary,
        peak_season_by_station,
    )

    hourly = load_processed()
    flags  = hourly_flags(hourly)
    daily  = daily_windows(flags)

    monthly = monthly_climatology(daily)
    weekly  = weekly_climatology(daily)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

SEASON_ORDER = ["spring", "summer", "fall", "winter"]


# ---------------------------------------------------------------------------
# Monthly climatology
# ---------------------------------------------------------------------------

def monthly_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Burn window frequency by station × month.

    Returns
    -------
    DataFrame:
        station_id, month, month_name,
        viable_days        — days with any_window == True
        total_days         — days with sufficient data
        pct_viable_days    — viable_days / total_days × 100
        mean_window_hours  — mean burn_window_hours on viable days
        median_window_hours
        full_window_days   — days rated 'full' quality (6+ hrs)
        pct_full_days      — full / total × 100
    """
    d = daily[daily["window_quality"] != "insufficient_data"].copy()

    agg = (
        d.groupby(["station_id", "month"])
        .agg(
            viable_days=      ("any_window",        "sum"),
            total_days=       ("any_window",        "count"),
            mean_window_hours=("burn_window_hours",  lambda x: x[x > 0].mean() if (x > 0).any() else 0),
            median_window_hours=("burn_window_hours", lambda x: x[x > 0].median() if (x > 0).any() else 0),
            full_window_days= ("window_quality",    lambda x: (x == "full").sum()),
        )
        .reset_index()
    )

    agg["pct_viable_days"] = (agg["viable_days"] / agg["total_days"] * 100).round(1)
    agg["pct_full_days"]   = (agg["full_window_days"] / agg["total_days"] * 100).round(1)
    agg["month_name"]      = agg["month"].map(MONTH_NAMES)
    agg["mean_window_hours"]   = agg["mean_window_hours"].round(1)
    agg["median_window_hours"] = agg["median_window_hours"].round(1)

    return agg.sort_values(["station_id", "month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Weekly climatology
# ---------------------------------------------------------------------------

def weekly_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Burn window frequency by station × week of year (ISO week 1–52).

    Returns
    -------
    DataFrame:
        station_id, week_of_year, month (majority month in that week),
        viable_days, total_days, pct_viable_days, mean_window_hours
    """
    d = daily[daily["window_quality"] != "insufficient_data"].copy()

    agg = (
        d.groupby(["station_id", "week_of_year"])
        .agg(
            viable_days=      ("any_window",        "sum"),
            total_days=       ("any_window",        "count"),
            mean_window_hours=("burn_window_hours",  lambda x: x[x > 0].mean() if (x > 0).any() else 0),
            month=            ("month",              lambda x: x.mode().iloc[0]),  # most common month
        )
        .reset_index()
    )

    agg["pct_viable_days"]    = (agg["viable_days"] / agg["total_days"] * 100).round(1)
    agg["mean_window_hours"]  = agg["mean_window_hours"].round(1)

    return agg.sort_values(["station_id", "week_of_year"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Seasonal summary
# ---------------------------------------------------------------------------

def seasonal_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Burn window frequency by station × season.

    Returns
    -------
    DataFrame:
        station_id, season, viable_days, total_days, pct_viable_days,
        mean_window_hours, full_window_days, pct_full_days
    """
    d = daily[daily["window_quality"] != "insufficient_data"].copy()

    agg = (
        d.groupby(["station_id", "season"])
        .agg(
            viable_days=      ("any_window",        "sum"),
            total_days=       ("any_window",        "count"),
            mean_window_hours=("burn_window_hours",  lambda x: x[x > 0].mean() if (x > 0).any() else 0),
            full_window_days= ("window_quality",    lambda x: (x == "full").sum()),
        )
        .reset_index()
    )

    agg["pct_viable_days"] = (agg["viable_days"] / agg["total_days"] * 100).round(1)
    agg["pct_full_days"]   = (agg["full_window_days"] / agg["total_days"] * 100).round(1)
    agg["mean_window_hours"] = agg["mean_window_hours"].round(1)

    # ordered season column for sorting/plotting
    agg["season_order"] = agg["season"].map({s: i for i, s in enumerate(SEASON_ORDER)})
    agg = agg.sort_values(["station_id", "season_order"]).drop(columns="season_order")

    return agg.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Station annual summary
# ---------------------------------------------------------------------------

def station_annual_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Per-station annual summary — useful for ranking stations by burn opportunity.

    Returns
    -------
    DataFrame (one row per station):
        station_id, total_days, viable_days, pct_viable_days,
        full_window_days, pct_full_days,
        mean_window_hours (on viable days),
        annual_window_hours (total viable hours across year),
        peak_month, peak_season
    """
    d = daily[daily["window_quality"] != "insufficient_data"].copy()

    agg = (
        d.groupby("station_id")
        .agg(
            total_days=           ("any_window",        "count"),
            viable_days=          ("any_window",        "sum"),
            full_window_days=     ("window_quality",    lambda x: (x == "full").sum()),
            annual_window_hours=  ("burn_window_hours", "sum"),
            mean_window_hours=    ("burn_window_hours", lambda x: x[x > 0].mean() if (x > 0).any() else 0),
        )
        .reset_index()
    )

    agg["pct_viable_days"] = (agg["viable_days"] / agg["total_days"] * 100).round(1)
    agg["pct_full_days"]   = (agg["full_window_days"] / agg["total_days"] * 100).round(1)
    agg["mean_window_hours"]   = agg["mean_window_hours"].round(1)

    # peak month per station
    monthly = monthly_climatology(daily)
    peak_months = (
        monthly.loc[monthly.groupby("station_id")["viable_days"].idxmax()]
        [["station_id", "month_name"]]
        .rename(columns={"month_name": "peak_month"})
    )

    # peak season per station — derived from peak month number to avoid idxmax cross-station collision
    def _m2s(m):
        return {12:"winter",1:"winter",2:"winter",
                3:"spring",4:"spring",5:"spring",
                6:"summer",7:"summer",8:"summer",
                9:"fall",10:"fall",11:"fall"}.get(m, "unknown")

    peak_month_nums = (
        monthly.loc[monthly.groupby("station_id")["viable_days"].idxmax(), ["station_id", "month"]]
        .copy()
    )
    peak_seasons = peak_month_nums.assign(
        peak_season=peak_month_nums["month"].map(_m2s)
    )[["station_id", "peak_season"]]

    agg = agg.merge(peak_months, on="station_id", how="left")
    agg = agg.merge(peak_seasons, on="station_id", how="left")

    return agg.sort_values("viable_days", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Peak season per station
# ---------------------------------------------------------------------------

def peak_season_by_station(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Identify the 4-week rolling peak burn period for each station
    (highest mean viable-day percentage in any 4-week window).

    Returns
    -------
    DataFrame:
        station_id, peak_start_week, peak_end_week,
        peak_month_range, mean_viable_pct_in_window
    """
    weekly = weekly_climatology(daily)
    results = []

    for station, grp in weekly.groupby("station_id"):
        grp = grp.sort_values("week_of_year").reset_index(drop=True)
        weeks  = grp["week_of_year"].values
        viable = grp["pct_viable_days"].values

        best_mean = -1
        best_start = best_end = None

        # sliding 4-week window
        for i in range(len(grp) - 3):
            window_mean = viable[i:i+4].mean()
            if window_mean > best_mean:
                best_mean  = window_mean
                best_start = int(weeks[i])
                best_end   = int(weeks[i+3])

        # map back to month range
        start_month = grp.loc[grp["week_of_year"] == best_start, "month"].values
        end_month   = grp.loc[grp["week_of_year"] == best_end,   "month"].values
        if len(start_month) and len(end_month):
            month_range = f"{MONTH_NAMES[start_month[0]]}–{MONTH_NAMES[end_month[0]]}"
        else:
            month_range = "unknown"

        results.append({
            "station_id":               station,
            "peak_start_week":          best_start,
            "peak_end_week":            best_end,
            "peak_month_range":         month_range,
            "mean_viable_pct_in_window": round(best_mean, 1),
        })

    return pd.DataFrame(results).sort_values("mean_viable_pct_in_window", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Cross-station weekly variation
# ---------------------------------------------------------------------------

def cross_station_weekly_variation(daily: pd.DataFrame) -> pd.DataFrame:
    """
    For each week of year, compute mean and std of pct_viable_days across all stations.
    High std = weeks where stations diverge significantly (elevation, aspect, etc.)

    Returns
    -------
    DataFrame:
        week_of_year, month_name, mean_viable_pct, std_viable_pct,
        min_station, max_station, range_pct
    """
    weekly = weekly_climatology(daily)

    agg = (
        weekly.groupby("week_of_year")
        .agg(
            mean_viable_pct=("pct_viable_days", "mean"),
            std_viable_pct= ("pct_viable_days", "std"),
            min_viable_pct= ("pct_viable_days", "min"),
            max_viable_pct= ("pct_viable_days", "max"),
            month=          ("month",           lambda x: x.mode().iloc[0]),
        )
        .reset_index()
    )

    agg["range_pct"]    = (agg["max_viable_pct"] - agg["min_viable_pct"]).round(1)
    agg["mean_viable_pct"] = agg["mean_viable_pct"].round(1)
    agg["std_viable_pct"]  = agg["std_viable_pct"].round(1)
    agg["month_name"]   = agg["month"].map(MONTH_NAMES)

    return agg.sort_values("week_of_year").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Heatmap pivot helpers
# ---------------------------------------------------------------------------

def station_month_heatmap(daily: pd.DataFrame, metric: str = "pct_viable_days") -> pd.DataFrame:
    """
    Return a pivot table suitable for seaborn.heatmap or plotly imshow.

    Parameters
    ----------
    metric : column from monthly_climatology() to pivot
             e.g. 'pct_viable_days', 'mean_window_hours', 'pct_full_days'

    Returns
    -------
    DataFrame with station_id as index, month_name as columns
    """
    monthly = monthly_climatology(daily)
    pivot = monthly.pivot(index="station_id", columns="month_name", values=metric)
    # reorder columns Jan→Dec
    ordered_months = [MONTH_NAMES[m] for m in range(1, 13) if MONTH_NAMES[m] in pivot.columns]
    return pivot[ordered_months]


def station_week_heatmap(daily: pd.DataFrame, metric: str = "pct_viable_days") -> pd.DataFrame:
    """
    Pivot table: station_id × week_of_year, filled with `metric`.
    """
    weekly = weekly_climatology(daily)
    return weekly.pivot(index="station_id", columns="week_of_year", values=metric)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from src.analysis.burn_windows import load_processed, hourly_flags, daily_windows

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/raws/raws_combined_20250410_20260410.csv"

    print("Loading data...")
    hourly = load_processed(csv_path)
    flags  = hourly_flags(hourly)
    daily  = daily_windows(flags)

    out_dir = Path("data/processed/raws")
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "climatology_monthly.csv":   monthly_climatology(daily),
        "climatology_weekly.csv":    weekly_climatology(daily),
        "climatology_seasonal.csv":  seasonal_summary(daily),
        "station_annual_summary.csv": station_annual_summary(daily),
        "peak_season_by_station.csv": peak_season_by_station(daily),
    }

    for fname, df in tables.items():
        path = out_dir / fname
        df.to_csv(path, index=False)
        print(f"Saved → {path}  ({len(df)} rows)")

    print("\n--- Station Annual Summary ---")
    print(station_annual_summary(daily).to_string(index=False))