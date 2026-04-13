# Fire Weather Windows
### Prescribed Burn Decision Support Tool · Pacific Northwest

---

Prescribed fire is one of the most effective tools for reducing wildfire risk in the Pacific Northwest — but executing a burn requires a narrow convergence of weather conditions. Relative humidity must be high enough to prevent the fire from escaping, wind speeds must be sufficient to disperse smoke while staying below the threshold where flames become unpredictable, and temperature ceilings cap the most dangerous conditions. In practice, identifying these windows accurately and in advance is a persistent operational bottleneck for fire managers.

This tool automates that identification. It pulls a year of hourly observations from 15 RAWS (Remote Automated Weather Stations) across Washington and Oregon, applies USFS standard burn window thresholds, characterizes each station's climatological window patterns, and integrates NOAA NDFD 7-day forecasts to flag upcoming candidate windows relative to historical baselines.

The result is a Streamlit dashboard that gives a prescribed fire coordinator a single view: which stations currently have viable windows, how today's forecast compares to historical norms, and which months to target for burn planning at each location.

---

## What the tool does

**Historical climatology** — one year of hourly RAWS observations (April 2025–April 2026) processed against USFS thresholds. Each hour flagged as pass/fail with directional sub-categories: `wind_too_calm`, `wind_too_strong`, `rh_too_wet`, `rh_too_dry`. Aggregated to daily window quality tiers (full / partial / marginal / no window) and monthly climatology tables. Outputs viable-day frequency by station and month.

**Forecast integration** — NOAA NDFD 7-day forecast pulled via REST XML for all 15 station locations. Same threshold logic applied to forecast data. Upcoming windows compared against same-month climatological baselines and classified as above-normal, near-normal, or below-normal.

**Interactive dashboard** — four-panel Streamlit app: station map (colored by current forecast window quality), 7-day forecast panel with network-wide heatmap, historical burn window calendar for any selected station, and cross-station climatology explorer with constraint regime breakdown.

---

## Key findings

Two constraint regimes emerge from the data:

**RH-constrained stations** (ANEW1, DRYW1, GRFW1, HIBW1, KOSW1, LBFO3, PEFW1) — RH runs wet enough that humidity is the primary limiting factor. These stations see 11–27% viable days annually. When windows open, wind dispersal requirements are typically met.

**Wind-constrained stations** (CGFO3, CMFW1, EVFO3, MILW1, TPEO3, TT246, VPFW1, WSRO3) — persistently below the 5 mph smoke dispersal floor. Calm-air conditions dominate year-round. Any window meeting the wind threshold is operationally significant.

**Temperature almost never constrains windows in this dataset.** The `< 90°F` ceiling is climatologically irrelevant for PNW prescribed fire — maximum temperature exceedance was 376 hours/year at WSRO3. The binding constraints in the PNW are fuel moisture (proxied here by RH) and smoke dispersal (wind speed floor), not temperature. This has implications for how coordinators should prioritize monitoring and for how threshold criteria might be refined for PNW-specific conditions.

LBFO3 (Lava Butte, OR) shows the most even seasonal distribution — viable windows in every month including winter, making it the highest-priority station for year-round burn planning. EVFO3 (Evans Creek, OR) produces approximately 5 viable days per year under standard thresholds and is operationally non-viable without threshold modification.

---

## Burn window thresholds

Standard USFS criteria applied throughout:

| Variable | Min | Max |
|---|---|---|
| Relative Humidity | 25% | 55% |
| Wind Speed | 5 mph | 15 mph |
| Temperature | — | 90°F |

Window quality tiers based on hours per day meeting all criteria:

| Tier | Hours | Interpretation |
|---|---|---|
| Full | ≥ 6 hrs | Strong candidate for burn execution |
| Partial | 3–5 hrs | Possible with early start |
| Marginal | 1–2 hrs | Monitor; unlikely to support full operation |
| No Window | 0 hrs | Conditions not met |

**Note on temperature in forecasts** — NOAA NDFD does not serve temperature forecasts for the PNW gridpoint products used here. A fill value of 50°F is applied (passes the `< 90°F` threshold). This is consistent with PNW climatology and documented as a design decision, not a data gap. The operative thresholds for forecasting in this region are RH and wind.

---

## Stations

15 verified RAWS stations across Washington and Oregon:

| ID | Name | State | Lat | Lon | Regime |
|---|---|---|---|---|---|
| TT246 | Entiat | WA | 47.733 | -120.243 | Wind-constrained |
| DRYW1 | Dry Creek | WA | 47.727 | -120.540 | RH-constrained |
| CMFW1 | Camp 4 | WA | 48.025 | -120.241 | Wind-constrained |
| VPFW1 | Viewpoint | WA | 47.855 | -120.890 | Wind-constrained |
| ANEW1 | Aeneas | WA | 48.743 | -119.622 | RH-constrained |
| GRFW1 | Grayback | WA | 45.992 | -121.083 | RH-constrained |
| PEFW1 | Peoh Point | WA | 47.152 | -120.947 | RH-constrained |
| MILW1 | Mill Creek | WA | 46.263 | -120.862 | Wind-constrained |
| HIBW1 | Highbridge | WA | 46.081 | -120.544 | RH-constrained |
| KOSW1 | Kosmos | WA | 46.524 | -122.190 | RH-constrained |
| LBFO3 | Lava Butte | OR | 43.925 | -121.343 | RH-constrained |
| WSRO3 | Warm Springs | OR | 44.780 | -121.250 | Wind-constrained |
| CGFO3 | Colgate | OR | 44.317 | -121.607 | Wind-constrained |
| TPEO3 | Tepee Draw | OR | 43.835 | -121.083 | Wind-constrained |
| EVFO3 | Evans Creek | OR | 42.598 | -123.105 | Wind-constrained |

Station IDs are verified against Synoptic Data API metadata — assumed IDs (e.g., ENTW1) were found not to exist and corrected via bbox metadata query.

---

## Data sources

**RAWS observations** — Synoptic Data API (`mesonet.utah.edu`), free tier. Hourly pulls for temperature, RH, wind speed, wind direction. 30-day chunked requests to stay within API limits. 129,794 rows across 15 stations, April 2025–April 2026.

**NDFD forecasts** — NOAA National Digital Forecast Database, REST XML endpoint (`graphical.weather.gov`). No API key required. Variables: RH, wind speed, wind direction. 7-day rolling forecast at station point locations.

**Thresholds** — USFS fire weather planning guides. Standard window criteria applied uniformly across all stations.

---

## Architecture

```
fire-weather-windows/
├── data/
│   ├── raw/
│   │   ├── raws/           # Cached JSON per station (Synoptic API)
│   │   └── ndfd/           # Cached XML per station per day (NOAA NDFD)
│   └── processed/
│       ├── raws/           # Combined CSV, climatology outputs, figures
│       └── ndfd/           # forecast_parsed.csv, forecast_summary.csv, figures
├── src/
│   ├── config.py           # Thresholds, station lists, paths
│   ├── ingest/
│   │   ├── raws_ingest.py  # Synoptic API pull + cache
│   │   └── ndfd_ingest.py  # NDFD REST XML pull + cache
│   └── analysis/
│       ├── burn_windows.py      # Core threshold logic, daily aggregation
│       ├── climatology.py       # Monthly/weekly/seasonal summaries
│       └── forecast_windows.py  # Forecast thresholds + climatology comparison
├── notebooks/
│   ├── 01_raws_exploration.ipynb
│   ├── 02_burn_window_climatology.ipynb
│   └── 03_ndfd_forecast_integration.ipynb
├── app.py                  # Streamlit dashboard
├── requirements.txt
└── README.md
```

Three loosely separated layers: ingestion (pull and cache raw data), analysis (threshold logic and climatology, same logic applied to both historical and forecast data), and dashboard (Streamlit consuming pre-computed outputs).

---

## Setup and usage

```bash
# Clone and set up environment
git clone https://github.com/MegaDeadCowboy/fire-weather-windows.git
cd fire-weather-windows
conda create -n firenv python=3.11
conda activate firenv
pip install -r requirements.txt

# Configure API token
cp .env.example .env
# Add your Synoptic Data API token to .env as SYNOPTIC_TOKEN=...

# Pull RAWS data
python src/ingest/raws_ingest.py --all-stations

# Pull NDFD forecast
python src/ingest/ndfd_ingest.py --all-stations

# Run analysis
python src/analysis/burn_windows.py
python src/analysis/climatology.py
python src/analysis/forecast_windows.py

# Launch dashboard
streamlit run app.py
```

The ingestion scripts cache raw data locally. Re-runs skip re-download unless `--force-refresh` is passed. Analysis scripts read from `data/processed/` and write outputs back to the same directory.

---

## Requirements

```
requests
pandas
numpy
xarray
cfgrib
eccodes
geopandas
scipy
scikit-learn
matplotlib
plotly
streamlit
streamlit-folium
folium
python-dotenv
```

Full pinned versions in `requirements.txt`.

---

## Technical notes

A few non-obvious implementation details that matter for reproducibility:

Timezone handling requires explicit UTC parsing: `pd.to_datetime(..., utc=True).dt.tz_convert(None)`. The Synoptic API returns timestamps in UTC without timezone markers; naive parsing produces incorrect local-time alignment.

The `pct_viable_days` column in climatology outputs is stored as a whole-number percent (e.g., `93.5` not `0.935`). The `compare_to_climatology()` function divides by 100 before multiplying by `mean_window_hours` to convert from hours-per-viable-day to hours-per-calendar-day for correct anomaly math.

Peak season derivation uses the peak month integer directly, not `idxmax()` on a seasonal summary DataFrame. The `idxmax()` approach produces incorrect results when viable-day counts are similar across stations — it picks the global maximum row rather than the per-station maximum.

---

*Built as part of a USDA Forest Service fellowship project. RAWS data via Synoptic Data API. Forecasts via NOAA NDFD. Thresholds per USFS fire weather planning standards.*
