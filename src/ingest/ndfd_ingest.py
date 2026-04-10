"""
NDFD Forecast Ingestion — NOAA National Digital Forecast Database
Downloads GRIB2 files via NOAA's NDFD REST service and parses key
fire-weather variables: RH, wind speed, wind direction, temperature.

No API key required. Data is public.

Usage:
    python ndfd_ingest.py                         # download + parse latest forecast
    python ndfd_ingest.py --vars rh wspd wdir tmp # select specific variables
    python ndfd_ingest.py --plot                  # also generate diagnostic plots

NDFD REST endpoint docs:
    https://graphical.weather.gov/xml/rest.php
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "ndfd"
PROC_DIR = ROOT / "data" / "processed" / "ndfd"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── NDFD Configuration ─────────────────────────────────────────────────────
NDFD_REST_BASE = "https://graphical.weather.gov/xml/sample_products/browser_interface/ndfdXMLclient.php"
NDFD_OPENDAP_BASE = "https://tgftp.nws.noaa.gov/SL.us008001/ST.opnl/DF.gr2/DC.ndfd/AR.pacnwest"

# PNW bounding box (lat/lon)
PNW_BBOX = {
    "lat_min": 41.5,
    "lat_max": 49.5,
    "lon_min": -125.0,
    "lon_max": -115.0,
}

# NDFD variable element names
NDFD_VARS = {
    "rh": "rh",            # relative humidity
    "wspd": "wspd",        # wind speed (sustained)
    "wdir": "wdir",        # wind direction
    "tmp": "tmp",          # temperature
    "maxt": "maxt",        # max temp (daily)
    "mint": "mint",        # min temp (daily)
    "minrh": "minrh",      # min RH (daily)
}


def download_ndfd_rest(
    lat: float,
    lon: float,
    variables: list[str] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Download NDFD point forecast via REST interface for a single lat/lon.
    Returns path to saved XML file.
    
    This is the most reliable approach for point extraction.
    For gridded GRIB2 download, see download_ndfd_grib2().
    """
    if variables is None:
        variables = ["rh", "wspd", "wdir", "tmp"]

    params = {
        "lat": lat,
        "lon": lon,
        "product": "time-series",
        "Unit": "e",   # English units (°F, mph)
        "begin": datetime.utcnow().strftime("%Y-%m-%dT%H:%M"),
        "end": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
    }
    for var in variables:
        params[NDFD_VARS.get(var, var)] = NDFD_VARS.get(var, var)

    print(f"Requesting NDFD point forecast: ({lat:.2f}, {lon:.2f})")
    r = requests.get(NDFD_REST_BASE, params=params, timeout=60)
    r.raise_for_status()

    if output_path is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        output_path = RAW_DIR / f"ndfd_point_{lat:.2f}_{lon:.2f}_{ts}.xml"

    output_path.write_bytes(r.content)
    print(f"  Saved → {output_path.name} ({len(r.content)/1024:.1f} KB)")
    return output_path


def download_ndfd_grib2(
    variable: str = "rh",
    forecast_hour: int = 0,
) -> Optional[Path]:
    """
    Download a GRIB2 file from NOAA's tgftp server for the PNW region.
    Variable options: 'ds.rhm.bin' (RH), 'ds.wspd.bin' (wind speed),
                      'ds.wdir.bin' (wind dir), 'ds.temp.bin' (temp)
    
    Returns local path if successful, None if download fails.
    """
    file_map = {
        "rh": "ds.rhm.bin",
        "wspd": "ds.wspd.bin",
        "wdir": "ds.wdir.bin",
        "tmp": "ds.temp.bin",
        "maxt": "ds.maxt.bin",
        "mint": "ds.mint.bin",
    }
    remote_file = file_map.get(variable)
    if not remote_file:
        raise ValueError(f"Unknown variable '{variable}'. Options: {list(file_map)}")

    url = f"{NDFD_OPENDAP_BASE}/VP.001-003/{remote_file}"
    print(f"Downloading GRIB2: {url}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    local_path = RAW_DIR / f"ndfd_{variable}_{ts}.grb2"

    r = requests.get(url, timeout=120, stream=True)
    if r.status_code != 200:
        print(f"  WARNING: Got HTTP {r.status_code}. GRIB2 download skipped.")
        print(f"  Falling back to REST point queries for station locations.")
        return None

    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = local_path.stat().st_size / (1024 * 1024)
    print(f"  Saved → {local_path.name} ({size_mb:.1f} MB)")
    return local_path


def parse_grib2(grib_path: Path, bbox: dict = None) -> dict:
    """
    Parse a GRIB2 file using cfgrib/xarray.
    Returns dict with xarray datasets keyed by variable shortName.
    
    Requires: cfgrib, eccodes, xarray (see requirements.txt)
    """
    try:
        import cfgrib
        import xarray as xr
    except ImportError:
        print("  cfgrib/xarray not installed. Run: pip install cfgrib xarray")
        return {}

    bbox = bbox or PNW_BBOX
    print(f"Parsing GRIB2: {grib_path.name}")

    datasets = {}
    try:
        ds_list = cfgrib.open_datasets(str(grib_path))
        for ds in ds_list:
            # Subset to PNW bounding box
            if "latitude" in ds.coords and "longitude" in ds.coords:
                lat_mask = (ds.latitude >= bbox["lat_min"]) & (ds.latitude <= bbox["lat_max"])
                lon_mask = (ds.longitude >= bbox["lon_min"]) & (ds.longitude <= bbox["lon_max"])
                ds_subset = ds.where(lat_mask & lon_mask, drop=True)
            else:
                ds_subset = ds

            for var in ds_subset.data_vars:
                datasets[var] = ds_subset[var]
                print(f"  Loaded variable: {var} | shape: {ds_subset[var].shape}")

    except Exception as e:
        print(f"  GRIB2 parse error: {e}")
        print("  Make sure eccodes is installed: conda install -c conda-forge eccodes")

    return datasets


def parse_ndfd_xml(xml_path: Path) -> pd.DataFrame:
    """
    Parse NDFD XML (from REST endpoint) into a clean DataFrame.
    Handles multi-variable time series.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {"dwml": "https://graphical.weather.gov/xml/DWMLgen/schema/DWML.xsd"}

    # Build time layout map: layout-key → list of datetimes
    time_layouts = {}
    for tl in root.findall(".//time-layout"):
        key_el = tl.find("layout-key")
        if key_el is None:
            continue
        key = key_el.text
        times = [
            pd.to_datetime(sv.text)
            for sv in tl.findall("start-valid-time")
        ]
        time_layouts[key] = times

    # Extract each parameter
    records = {}
    for param in root.findall(".//parameters"):
        for child in param:
            tag = child.tag.lower()
            time_key = child.get("time-layout", "")
            if time_key not in time_layouts:
                continue
            times = time_layouts[time_key]
            values = [
                float(v.text) if v.text and v.text not in ("", "nil") else None
                for v in child.findall("value")
            ]
            if len(values) == len(times):
                records[tag] = dict(zip(times, values))

    # Align all variables on a common time index
    all_times = sorted(set(t for v in records.values() for t in v))
    if not all_times:
        return pd.DataFrame()

    df = pd.DataFrame(index=all_times)
    for var_name, time_val_map in records.items():
        df[var_name] = df.index.map(time_val_map)

    df.index.name = "datetime"
    df = df.reset_index()

    # Standardize column names
    rename = {
        "temperature": "temp_f",
        "humidity": "rh_pct",
        "wind-speed": "wind_speed_mph",
        "direction": "wind_dir_deg",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    return df


def extract_point_from_grid(
    datasets: dict,
    lat: float,
    lon: float,
    var_map: dict = None,
) -> pd.DataFrame:
    """
    Extract forecast time series for a specific lat/lon from parsed GRIB2 datasets.
    Uses nearest-neighbor grid point lookup.
    """
    try:
        import xarray as xr
        import numpy as np
    except ImportError:
        return pd.DataFrame()

    var_map = var_map or {
        "r": "rh_pct",
        "2r": "rh_pct",
        "si10": "wind_speed_mph",
        "wdir10": "wind_dir_deg",
        "2t": "temp_f",
    }

    records = {}
    for grib_name, df_col in var_map.items():
        if grib_name not in datasets:
            continue
        da = datasets[grib_name]

        # Find nearest grid point
        dist = np.sqrt((da.latitude - lat) ** 2 + (da.longitude - lon) ** 2)
        idx = np.unravel_index(dist.values.argmin(), dist.shape)

        # Extract time series
        if "valid_time" in da.coords:
            times = da.valid_time.values
        elif "time" in da.coords:
            times = da.time.values
        else:
            continue

        vals = da.isel({k: idx[i] for i, k in enumerate(da.dims[-2:])}).values
        records[df_col] = dict(zip(pd.to_datetime(times), vals))

    if not records:
        return pd.DataFrame()

    all_times = sorted(set(t for v in records.values() for t in v))
    df = pd.DataFrame(index=all_times)
    for col, time_val in records.items():
        df[col] = df.index.map(time_val)

    df.index.name = "datetime"
    return df.reset_index()


def fetch_station_forecasts(
    stations: pd.DataFrame,
    variables: list[str] = None,
    delay: float = 1.0,
) -> pd.DataFrame:
    """
    Pull NDFD point forecasts for a list of stations (from raws_ingest metadata).
    Returns combined forecast DataFrame aligned to station IDs.
    """
    variables = variables or ["rh", "wspd", "wdir", "tmp"]
    all_frames = []

    for _, row in stations.iterrows():
        sid = row["station_id"]
        lat = row["lat"]
        lon = row["lon"]

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        xml_cache = RAW_DIR / f"ndfd_{sid}_{ts[:8]}.xml"

        if not xml_cache.exists():
            try:
                xml_cache = download_ndfd_rest(lat, lon, variables, xml_cache)
                time.sleep(delay)
            except Exception as e:
                print(f"  [{sid}] Forecast download failed: {e}")
                continue

        try:
            df = parse_ndfd_xml(xml_cache)
            if not df.empty:
                df["station_id"] = sid
                df["station_name"] = row.get("name", sid)
                df["lat"] = lat
                df["lon"] = lon
                all_frames.append(df)
        except Exception as e:
            print(f"  [{sid}] XML parse failed: {e}")

    if not all_frames:
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)
    out_path = PROC_DIR / f"ndfd_forecasts_{datetime.utcnow():%Y%m%d}.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nSaved forecast data → {out_path}")
    return combined


def plot_grib2_field(datasets: dict, variable: str = "r", title: str = None):
    """
    Quick diagnostic plot of a GRIB2 field over the PNW.
    Requires matplotlib.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
    except ImportError:
        print("matplotlib not installed.")
        return

    if variable not in datasets:
        print(f"Variable '{variable}' not in datasets. Available: {list(datasets)}")
        return

    da = datasets[variable]

    # If multi-timestep, plot first valid time
    if "valid_time" in da.dims:
        da = da.isel(valid_time=0)
    elif "step" in da.dims:
        da = da.isel(step=0)

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = cm.RdYlGn if "r" in variable.lower() else cm.viridis

    mesh = ax.pcolormesh(
        da.longitude, da.latitude, da.values,
        cmap=cmap, shading="auto"
    )
    plt.colorbar(mesh, ax=ax, label=da.attrs.get("GRIB_name", variable))
    ax.set_title(title or f"NDFD {variable} — PNW Forecast")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    out_path = PROC_DIR / f"ndfd_{variable}_diagnostic.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Diagnostic plot saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and parse NDFD forecasts")
    parser.add_argument("--vars", nargs="+", default=["rh", "wspd", "wdir", "tmp"],
                        help="Variables to fetch")
    parser.add_argument("--grib2", action="store_true",
                        help="Attempt GRIB2 download (requires cfgrib/eccodes)")
    parser.add_argument("--plot", action="store_true",
                        help="Generate diagnostic plot of first GRIB2 field")
    parser.add_argument("--lat", type=float, default=47.5,
                        help="Test point latitude")
    parser.add_argument("--lon", type=float, default=-120.5,
                        help="Test point longitude")
    args = parser.parse_args()

    if args.grib2:
        # Try GRIB2 download for first variable
        grib_path = download_ndfd_grib2(variable=args.vars[0])
        if grib_path:
            datasets = parse_grib2(grib_path)
            if args.plot and datasets:
                plot_grib2_field(datasets, variable=list(datasets)[0])
            # Extract point for test location
            df = extract_point_from_grid(datasets, args.lat, args.lon)
            if not df.empty:
                print(df.head(10))
    else:
        # REST point query for test location
        xml_path = download_ndfd_rest(args.lat, args.lon, args.vars)
        df = parse_ndfd_xml(xml_path)
        if not df.empty:
            print(df.head(10))
            print(f"\nColumns: {list(df.columns)}")
            print(f"Forecast hours: {len(df)}")
