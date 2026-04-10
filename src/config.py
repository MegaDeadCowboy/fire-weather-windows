"""
Project-wide configuration for fire-weather-windows.
Thresholds sourced from USFS fire weather planning guides.
"""

# ── Burn Window Thresholds ─────────────────────────────────────────────────
# Standard PNW prescribed fire operating window (USFS Red Book guidance)
# All values in English units to match NDFD and Synoptic defaults

BURN_THRESHOLDS = {
    # Relative humidity (%)
    "rh_min": 25,          # Below this: fire behavior too erratic
    "rh_max": 55,          # Above this: fire may not carry / hold heat
    
    # Wind speed (mph, 20-ft wind)
    "wind_min": 5,          # Below this: smoke dispersion concerns
    "wind_max": 15,         # Above this: spotting / control risk
    
    # Temperature (°F)
    "temp_max": 90,         # Above this: fine fuel moisture too low
    
    # Optional tighter window for sensitive areas
    "rh_min_sensitive": 30,
    "rh_max_sensitive": 50,
    "wind_max_sensitive": 12,
}

# ── Data Quality ───────────────────────────────────────────────────────────
# Minimum hourly observations per day to count as a valid data day
MIN_OBS_PER_DAY = 6

# Maximum gap (hours) to interpolate across in QC
MAX_GAP_HOURS = 3

# ── Climatology ────────────────────────────────────────────────────────────
# Minimum years of data to compute reliable climatology
MIN_YEARS_FOR_CLIMO = 2

# Season definitions (month ranges, inclusive)
SEASONS = {
    "spring": (3, 5),
    "summer": (6, 8),
    "fall": (9, 11),
    "winter": (12, 2),
}

# ── API / Network ──────────────────────────────────────────────────────────
SYNOPTIC_BASE_URL = "https://api.synopticdata.com/v2"
NDFD_REST_URL = "https://graphical.weather.gov/xml/sample_products/browser_interface/ndfdXMLclient.php"
NDFD_GRIB2_BASE = "https://tgftp.nws.noaa.gov/SL.us008001/ST.opnl/DF.gr2/DC.ndfd/AR.pacnwest"

# Polite rate limiting for free API tiers
SYNOPTIC_DELAY_SEC = 0.3
NDFD_DELAY_SEC = 1.0

# ── Spatial ────────────────────────────────────────────────────────────────
PNW_BBOX = {
    "lat_min": 41.5,
    "lat_max": 49.5,
    "lon_min": -125.0,
    "lon_max": -115.0,
}

# ── Paths ─────────────────────────────────────────────────────────────────
# These are resolved at runtime relative to project root
DATA_DIR = "data"
RAW_DIR = "data/raw"
PROC_DIR = "data/processed"
NOTEBOOK_DIR = "notebooks"
