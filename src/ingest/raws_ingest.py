"""
RAWS Station Ingestion — Synoptic Data (Mesonet) API
Pulls temperature, RH, wind speed, wind direction for PNW stations.
Free tier, no API key required for public data.

Usage:
    python raws_ingest.py                          # pull all default PNW stations
    python raws_ingest.py --states WA OR           # filter by state
    python raws_ingest.py --stations KSEA KPDX     # specific station IDs
    python raws_ingest.py --years 3                # how many years back
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "raws"
PROC_DIR = ROOT / "data" / "processed" / "raws"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── Synoptic API base ──────────────────────────────────────────────────────
BASE_URL = "https://api.synopticdata.com/v2"

# ── PNW RAWS stations (USFS / BLM fire-weather network) ───────────────────
# Selected for geographic spread across WA and OR.
# Expand this list as needed; keep 10–15 for Week 1 scope.
DEFAULT_STATIONS = {
    # Washington — Cascades east slope, NE WA, Olympics
    "TT246":  {"name": "Entiat",         "state": "WA", "lat": 47.733, "lon": -120.243},
    "DRYW1":  {"name": "Dry Creek",      "state": "WA", "lat": 47.727, "lon": -120.540},
    "CMFW1":  {"name": "Camp 4",         "state": "WA", "lat": 48.025, "lon": -120.241},
    "VPFW1":  {"name": "Viewpoint",      "state": "WA", "lat": 47.855, "lon": -120.890},
    "ANEW1":  {"name": "Aeneas",         "state": "WA", "lat": 48.743, "lon": -119.622},
    "GRFW1":  {"name": "Grayback",       "state": "WA", "lat": 45.992, "lon": -121.083},
    "PEFW1":  {"name": "Peoh Point",     "state": "WA", "lat": 47.152, "lon": -120.947},
    "MILW1":  {"name": "Mill Creek",     "state": "WA", "lat": 46.263, "lon": -120.862},
    "HIBW1":  {"name": "Highbridge",     "state": "WA", "lat": 46.081, "lon": -120.544},
    "KOSW1":  {"name": "Kosmos",         "state": "WA", "lat": 46.524, "lon": -122.190},
    # Oregon — Cascades, SW OR, high desert
    "LBFO3":  {"name": "Lava Butte",     "state": "OR", "lat": 43.925, "lon": -121.343},
    "WSRO3":  {"name": "Warm Springs",   "state": "OR", "lat": 44.780, "lon": -121.250},
    "CGFO3":  {"name": "Colgate",        "state": "OR", "lat": 44.317, "lon": -121.607},
    "TPEO3":  {"name": "Tepee Draw",     "state": "OR", "lat": 43.835, "lon": -121.083},
    "EVFO3":  {"name": "Evans Creek",    "state": "OR", "lat": 42.598, "lon": -123.105},
}

# Variables to request from Synoptic
VARIABLES = ["air_temp", "relative_humidity", "wind_speed", "wind_direction"]


def get_station_metadata(token: str, states: list[str] = None) -> pd.DataFrame:
    """
    Fetch station metadata. If states provided, filter to those.
    Falls back to DEFAULT_STATIONS if API returns nothing useful.
    """
    params = {
        "token": token,
        "network": "2",        # RAWS network ID
        "status": "active",
        "vars": ",".join(VARIABLES),
        "output": "json",
    }
    if states:
        params["state"] = ",".join(states)

    url = f"{BASE_URL}/stations/metadata"
    print(f"Fetching station metadata (states={states or 'all PNW'})...")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if data.get("SUMMARY", {}).get("NUMBER_OF_OBJECTS", 0) == 0:
        print("  No stations returned from API; using DEFAULT_STATIONS list.")
        records = [
            {"station_id": sid, **meta}
            for sid, meta in DEFAULT_STATIONS.items()
            if (not states or meta["state"] in states)
        ]
        return pd.DataFrame(records)

    records = []
    for stn in data.get("STATION", []):
        records.append({
            "station_id": stn["STID"],
            "name": stn.get("NAME", ""),
            "state": stn.get("STATE", ""),
            "lat": float(stn.get("LATITUDE", 0)),
            "lon": float(stn.get("LONGITUDE", 0)),
            "elevation_ft": stn.get("ELEVATION", None),
        })

    df = pd.DataFrame(records)
    print(f"  Found {len(df)} stations.")
    return df


def fetch_timeseries(
    token: str,
    station_id: str,
    start_dt: datetime,
    end_dt: datetime,
    chunk_days: int = 30,
) -> pd.DataFrame:
    """
    Pull hourly observations for one station over a date range.
    Chunks requests to stay within API limits. Caches raw JSON responses.
    """
    cache_file = RAW_DIR / f"{station_id}_{start_dt:%Y%m%d}_{end_dt:%Y%m%d}.json"

    if cache_file.exists():
        print(f"  [{station_id}] Loading from cache: {cache_file.name}")
        with open(cache_file) as f:
            all_obs = json.load(f)
    else:
        all_obs = []
        cursor = start_dt
        while cursor < end_dt:
            chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)
            params = {
                "token": token,
                "stid": station_id,
                "start": cursor.strftime("%Y%m%d%H%M"),
                "end": chunk_end.strftime("%Y%m%d%H%M"),
                "vars": ",".join(VARIABLES),
                "units": "english",   # °F, mph
                "obtimezone": "local",
                "output": "json",
            }
            url = f"{BASE_URL}/stations/timeseries"
            print(f"  [{station_id}] {cursor:%Y-%m-%d} → {chunk_end:%Y-%m-%d}")
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            stations = data.get("STATION", [])
            if stations:
                all_obs.append(stations[0])
            time.sleep(0.3)   # polite rate limiting
            cursor = chunk_end

        with open(cache_file, "w") as f:
            json.dump(all_obs, f)

    return _parse_observations(all_obs, station_id)


def _parse_observations(raw_list: list, station_id: str) -> pd.DataFrame:
    """Parse Synoptic timeseries JSON into a clean DataFrame."""
    rows = []
    for stn_chunk in raw_list:
        obs = stn_chunk.get("OBSERVATIONS", {})
        times = obs.get("date_time", [])
        temp = obs.get("air_temp_set_1", [None] * len(times))
        rh = obs.get("relative_humidity_set_1", [None] * len(times))
        wspd = obs.get("wind_speed_set_1", [None] * len(times))
        wdir = obs.get("wind_direction_set_1", [None] * len(times))

        for i, ts in enumerate(times):
            rows.append({
                "station_id": station_id,
                "datetime": pd.to_datetime(ts),
                "temp_f": temp[i],
                "rh_pct": rh[i],
                "wind_speed_mph": wspd[i],
                "wind_dir_deg": wdir[i],
            })

    if not rows:
        return pd.DataFrame(columns=["station_id", "datetime", "temp_f",
                                     "rh_pct", "wind_speed_mph", "wind_dir_deg"])

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(None)  # normalize to naive UTC
    df = df.sort_values("datetime").reset_index(drop=True)

    # Basic QC: clip physically implausible values
    df.loc[df["temp_f"] < -60, "temp_f"] = None
    df.loc[df["temp_f"] > 130, "temp_f"] = None
    df.loc[df["rh_pct"] < 0, "rh_pct"] = None
    df.loc[df["rh_pct"] > 100, "rh_pct"] = None
    df.loc[df["wind_speed_mph"] < 0, "wind_speed_mph"] = None

    return df


def run_ingest(
    token: str,
    states: list[str] = None,
    station_ids: list[str] = None,
    years_back: int = 3,
) -> pd.DataFrame:
    """
    Main entry point. Pulls observations for all target stations
    and saves a combined processed CSV.
    """
    from datetime import timezone
    end_dt = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, capped to now
    start_dt = end_dt - timedelta(days=365 * years_back)

    # Resolve station list
    if station_ids:
        stations_df = pd.DataFrame([
            {"station_id": sid, **DEFAULT_STATIONS.get(sid, {"name": sid, "state": "UNK", "lat": 0, "lon": 0})}
            for sid in station_ids
        ])
    else:
        stations_df = get_station_metadata(token, states)
        # Limit to our curated list for Week 1 if API returns a huge list
        if len(stations_df) > 20:
            known = list(DEFAULT_STATIONS.keys())
            if states:
                known = [k for k, v in DEFAULT_STATIONS.items() if v["state"] in states]
            stations_df = stations_df[stations_df["station_id"].isin(known)]
            print(f"  Capped to {len(stations_df)} curated stations.")

    print(f"\nPulling {len(stations_df)} stations | {start_dt:%Y-%m-%d} → {end_dt:%Y-%m-%d}\n")

    all_frames = []
    for _, row in stations_df.iterrows():
        sid = row["station_id"]
        try:
            df = fetch_timeseries(token, sid, start_dt, end_dt)
            if not df.empty:
                df["station_name"] = row.get("name", sid)
                df["state"] = row.get("state", "")
                df["lat"] = row.get("lat", None)
                df["lon"] = row.get("lon", None)
                all_frames.append(df)
        except Exception as e:
            print(f"  [{sid}] ERROR: {e}")

    if not all_frames:
        print("No data retrieved.")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)

    out_path = PROC_DIR / f"raws_combined_{start_dt:%Y%m%d}_{end_dt:%Y%m%d}.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nSaved {len(combined):,} records → {out_path}")

    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest RAWS data via Synoptic API")
    parser.add_argument("--token", default="demotoken",
                        help="Synoptic API token (free at synopticdata.com)")
    parser.add_argument("--states", nargs="+", default=["WA", "OR"],
                        help="States to pull (e.g. WA OR)")
    parser.add_argument("--stations", nargs="+", default=None,
                        help="Specific station IDs (overrides --states)")
    parser.add_argument("--years", type=int, default=3,
                        help="Years of historical data to pull")
    args = parser.parse_args()

    df = run_ingest(
        token=args.token,
        states=args.states,
        station_ids=args.stations,
        years_back=args.years,
    )
    if not df.empty:
        print(df.head())
        print(f"\nStations: {df['station_id'].nunique()}")
        print(f"Date range: {df['datetime'].min()} → {df['datetime'].max()}")