# Fire Weather Windows
### Decision Support for Prescribed Burn Planning in the Pacific Northwest

---

Prescribed fire is one of the most effective tools available for reducing catastrophic wildfire risk and restoring fire-adapted ecosystems across the PNW — but its application is tightly constrained. Burn managers must identify narrow meteorological windows where conditions allow a fire to carry, consume fuels effectively, and remain controllable: low enough wind to prevent spotting, high enough relative humidity to slow spread, cool enough temperatures to keep fine fuel moisture at workable levels. Miss that window and the burn doesn't happen. Catch it at the wrong moment and you may lose it.

In practice, identifying these windows is often done manually — reading RAWS station feeds, checking spot forecasts, applying thresholds from experience and the Red Book. This project builds a prototype decision-support tool that automates the window identification logic, surfaces climatological patterns (when do viable windows typically occur at each station?), and integrates NOAA NDFD forecast data to flag upcoming candidate windows before they arrive.

The framing mirrors USFS pre-burn weather review workflow. The thresholds are drawn from publicly documented USFS fire weather planning guidance. The goal is a tool that a prescribed fire coordinator could use to answer: *"When have we historically had burnable days here, and do the next 7 days look like one of them?"*

---

## What This Tool Does

- **Ingests** 2–3 years of hourly RAWS observations for 10–15 PNW stations via the Synoptic Data API (free tier, no API key required for public data)
- **Ingests** NOAA NDFD 7-day forecasts via the NDFD REST service or GRIB2 files (no API key required)
- **Applies** standard USFS burn window thresholds:
  - Relative humidity: 25–55%
  - Wind speed: 5–15 mph
  - Temperature: below 90°F
- **Computes climatology**: burn window frequency by station, month, season
- **Flags upcoming windows**: forecast conditions evaluated against thresholds, compared to climatological baseline
- **Displays** in a Streamlit dashboard: station map, burn window calendar, forecast panel

---

## Project Structure

```
fire-weather-windows/
├── data/
│   ├── raw/
│   │   ├── raws/           # Raw JSON from Synoptic API (cached per-station)
│   │   └── ndfd/           # GRIB2 and XML files from NOAA NDFD
│   └── processed/
│       ├── raws/           # Combined CSVs, QC'd observations
│       └── ndfd/           # Parsed forecast DataFrames
├── src/
│   ├── config.py           # Thresholds, paths, API config
│   ├── ingest/
│   │   ├── raws_ingest.py  # Synoptic API pull, caching, QC
│   │   └── ndfd_ingest.py  # NDFD REST + GRIB2 download and parse
│   ├── analysis/
│   │   ├── burn_windows.py # Threshold logic, window flagging
│   │   └── climatology.py  # Historical frequency, seasonal patterns
│   └── dashboard/
│       └── components.py   # Reusable Streamlit/Plotly components
├── notebooks/
│   ├── 01_raws_exploration.ipynb
│   ├── 02_burn_window_climatology.ipynb
│   └── 03_ndfd_forecast_integration.ipynb
├── app.py                  # Streamlit dashboard entry point
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
# Recommended: conda for eccodes (GRIB2 library)
conda create -n fire-wx python=3.11
conda activate fire-wx
conda install -c conda-forge eccodes cfgrib
pip install -r requirements.txt
```

Or pip-only (GRIB2 may require manual eccodes install on some platforms):
```bash
pip install -r requirements.txt
```

### 2. Pull RAWS historical data

```bash
# Free Synoptic token: register at https://synopticdata.com (free tier)
python src/ingest/raws_ingest.py --token YOUR_TOKEN --states WA OR --years 3
```

Without a token, use `--token demotoken` for limited public access.

### 3. Download NDFD forecast

```bash
# REST point queries (no dependencies beyond requests + xml)
python src/ingest/ndfd_ingest.py --lat 47.5 --lon -120.5

# GRIB2 gridded download (requires cfgrib/eccodes)
python src/ingest/ndfd_ingest.py --grib2 --plot
```

### 4. Run the dashboard

```bash
streamlit run app.py
```

---

## Burn Window Thresholds

| Variable | Min | Max | Source |
|---|---|---|---|
| Relative Humidity | 25% | 55% | USFS Red Book / fire weather planning guides |
| Wind Speed (20-ft) | 5 mph | 15 mph | USFS standard; smoke dispersal + control |
| Temperature | — | 90°F | Fine fuel moisture proxy |

Tighter thresholds are configurable in `src/config.py` for sensitive areas or high-consequence burns.

---

## Data Sources

| Source | Format | Cost | Auth |
|---|---|---|---|
| [Synoptic Data (Mesonet)](https://synopticdata.com) | JSON REST | Free tier available | Token (free registration) |
| [NOAA NDFD](https://www.weather.gov/mdl/ndfd_home) | XML REST / GRIB2 | Free | None |
| USFS RAWS Network | Via Synoptic | Free | Token |

---

## Development Milestones

- **Week 1** ✅ Repo structure, RAWS ingestion, NDFD GRIB2 parser
- **Week 2** — Burn window climatology, seasonal frequency analysis
- **Week 3** — Forecast integration, climatological comparison
- **Week 4** — Streamlit dashboard, spatial interpolation (stretch), final polish

---

## License

MIT. Data from NOAA and USFS are public domain. Synoptic data subject to their terms of service.
