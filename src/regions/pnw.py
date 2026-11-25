"""Pacific Northwest (original fire-weather-windows region)."""
SOURCE = "USFS fire weather planning guidance (see README); values as in src/config.py"
THRESHOLDS = {"rh_min": 25.0, "rh_max": 55.0, "wind_min": 5.0, "wind_max": 15.0, "temp_max": 90.0}
STATIONS = None  # all stations in DATA_CSV
DATA_CSV = "data/processed/raws/raws_combined_20250410_20260410.csv"
