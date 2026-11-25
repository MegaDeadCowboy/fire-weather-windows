"""
RAWS ingest from USFS FEMS (Fire Environment Mapping System). Free, no key.
Replaces Synoptic for the Northeast region (Synoptic history now needs a paid/.edu tier).

Docs: FEMS Climatology API External User Guide (2025-09);
      FEMS TechNote 2025-09-16 "Get Data Manipulation (URL)".

Usage (from repo root):
    python -m src.ingest.fems_ingest stations                 # NE RAWS list -> data/raw/fems/ne_stations.csv
    python -m src.ingest.fems_ingest sample --station 102712  # 7-day test pull, prints columns
    python -m src.ingest.fems_ingest pull --stations 1,2,3 --start 2025-01-01 --end 2025-12-31

Output of `pull`: data/processed/raws/northeast_hourly.csv with the same columns
burn_windows.load_processed() expects (station_id, datetime, temp_f, rh, wind_mph, wind_dir)
plus precip_in. Values with FEMS QC flag 2 ("suspicious") are set to NaN and counted.
"""

import argparse
import io
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "fems"
PROC_DIR = ROOT / "data" / "processed" / "raws"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_URL = "https://fems.fs2c.usda.gov/api/climatology/graphql"
WEATHER_URL = "https://fems.fs2c.usda.gov/api/ext-climatology/download-weather"
NE_STATES = ["CT", "DE", "MD", "ME", "MA", "NH", "NJ", "NY", "PA", "RI", "VT", "WV"]
CHUNK_DAYS = 90  # max range per request isn't documented; keep chunks modest

COLMAP = {  # FEMS CSV header -> fire-weather-windows schema
    "Temperature(F)": "temp_f",
    "RelativeHumidity(%)": "rh",
    "WindSpeed(mph)": "wind_mph",
    "WindAzimuth(degrees)": "wind_dir",
    "Precipitation(in)": "precip_in",
}
FLAGMAP = {"temp_f": "Tflag", "rh": "RHflag", "wind_mph": "WSflag",
           "wind_dir": "WAflag", "precip_in": "PCPflag"}

STATION_QUERY = """
query StationMetaData($stateId: String) {
  stationMetaData(stateId: $stateId, networkName: "RAWS", per_page: 1000) {
    _metadata { page per_page total_count page_count }
    data { station_id station_name state latitude longitude station_status station_type }
  }
}"""


def stations():
    frames = []
    for st in NE_STATES:
        cache = RAW_DIR / f"stations_{st}.json"
        if not cache.exists():
            r = requests.post(GRAPHQL_URL, json={"query": STATION_QUERY,
                              "variables": {"stateId": st}}, timeout=60)
            r.raise_for_status()
            body = r.json()
            if body.get("errors"):
                raise SystemExit(f"{st}: GraphQL errors: {body['errors'][:2]}")
            res = body["data"]["stationMetaData"]
            pages = res["data"]
            total = res["_metadata"]["total_count"]
            if len(pages) != total:
                raise SystemExit(f"{st}: got {len(pages)} of {total} stations; raise per_page")
            cache.write_text(json.dumps(pages))
        frames.append(pd.DataFrame(json.loads(cache.read_text())))
    df = pd.concat(frames, ignore_index=True)
    out = RAW_DIR / "ne_stations.csv"
    df.to_csv(out, index=False)
    print(f"NE RAWS stations: {len(df)} -> {out}")
    print(df.groupby("state").size().reindex(NE_STATES, fill_value=0).to_string())
    if "station_status" in df:
        print(df["station_status"].value_counts(dropna=False).to_string())


PROBE_QUERY = """
query P($stateId: String, $networkName: String) {
  stationMetaData(stateId: $stateId, networkName: $networkName, per_page: 3) {
    _metadata { total_count }
    data { station_id station_name state latitude longitude station_status station_type }
  }
}"""


def probe():
    """Try filter combinations; print total_count and a sample record for each."""
    for label, v in [("no filter", {}), ("stateId=ME", {"stateId": "ME"}),
                     ("stateId=ME, network=RAWS", {"stateId": "ME", "networkName": "RAWS"}),
                     ("stateId=Maine", {"stateId": "Maine"}), ("stateId=23", {"stateId": "23"})]:
        r = requests.post(GRAPHQL_URL, json={"query": PROBE_QUERY, "variables": v}, timeout=60)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not body or body.get("errors"):
            print(f"{label}: HTTP {r.status_code} {str(body.get('errors') or r.text)[:300]}")
            continue
        res = body["data"]["stationMetaData"]
        print(f"{label}: total_count={res['_metadata']['total_count']} sample={res['data'][:1]}")


def _get_chunk(station, start, end):
    cache = RAW_DIR / f"wx_{station}_{start}_{end}.csv"
    if not cache.exists():
        params = {"stationIds": station, "startDate": f"{start}T00:00:00Z",
                  "endDate": f"{end}T23:59:59Z", "dataset": "observation",
                  "dataFormat": "csv", "dataIncrement": "hourly"}
        r = requests.get(WEATHER_URL, params=params, timeout=120)
        r.raise_for_status()
        cache.write_text(r.text)
    return pd.read_csv(io.StringIO(cache.read_text()))


def sample(station):
    end = date.today() - timedelta(days=30)
    df = _get_chunk(station, end - timedelta(days=7), end)
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    print(df.head(5).to_string())


def pull(station_ids, start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    frames, qa = [], []
    for sid in station_ids:
        cur = s
        while cur <= e:
            stop = min(cur + timedelta(days=CHUNK_DAYS - 1), e)
            df = _get_chunk(sid, cur, stop)
            df["station_id"] = sid
            frames.append(df)
            cur = stop + timedelta(days=1)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw.get("ObservationType", "O").astype(str).str.upper().str.startswith("O")]
    out = raw.rename(columns=COLMAP)
    out["datetime"] = pd.to_datetime(out["DateTime"], utc=True, errors="coerce")
    for col, flag in FLAGMAP.items():
        if flag in out:
            bad = out[flag] == 2
            qa.append((col, int(bad.sum())))
            out.loc[bad, col] = pd.NA
    keep = ["station_id", "datetime", "temp_f", "rh", "wind_mph", "wind_dir", "precip_in"]
    out = out[keep].drop_duplicates(["station_id", "datetime"]).sort_values(["station_id", "datetime"])
    path = PROC_DIR / "northeast_hourly.csv"
    out.to_csv(path, index=False)
    qa_df = pd.DataFrame(qa, columns=["variable", "set_nan_qc_flag2"])
    qa_df.to_csv(PROC_DIR / "northeast_qc_drops.csv", index=False)
    print(f"rows: {len(out)} -> {path}")
    print(out.groupby("station_id")["datetime"].agg(["min", "max", "size"]).to_string())
    print(qa_df.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stations")
    sub.add_parser("probe")
    sp = sub.add_parser("sample"); sp.add_argument("--station", required=True)
    pp = sub.add_parser("pull")
    pp.add_argument("--stations", required=True)
    pp.add_argument("--start", required=True); pp.add_argument("--end", required=True)
    a = ap.parse_args()
    if a.cmd == "probe":
        probe()
    elif a.cmd == "stations":
        stations()
    elif a.cmd == "sample":
        sample(a.station)
    else:
        pull(a.stations.split(","), a.start, a.end)
