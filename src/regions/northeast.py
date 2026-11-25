"""Northeast (USDA Northeast Climate Hub states). Linked from MegaDeadCowboy/northeast-fire-weather.

Thresholds: Table 4 medians for the TIMBER fuel group in
Fast, A.J., Ducey, M.J., Weyrick, R.R. "Common Prescribed Burning Prescription Parameters
in Northeastern Fuels." UNH Cooperative Extension, Natural Resource Network (survey of
31 burn plans, 16 agencies/organizations, 7 northeastern states; data collected 2008).
Wind is 20-ft wind, matching the RAWS sensor height. "Days since last rain" min = 1 is
applied as no measurable precip (>= 0.01 in) in the trailing 24 h.
"""
SOURCE = "Fast, Ducey & Weyrick, UNH Cooperative Extension, Table 4 (timber medians)"
THRESHOLDS = {
    "rh_min": 30.0, "rh_max": 67.0,        # %
    "wind_min": 4.5, "wind_max": 20.0,     # mph, 20-ft
    "temp_min": 35.0, "temp_max": 87.5,    # °F
    "rain_free_hours": 24, "rain_trace_in": 0.01,
}
# FEMS station IDs; selection logged in northeast-fire-weather docs/decision_log.md #9
STATIONS = {
    "280051": "Coyle Field, NJ",
    "463501": "Upper Tract, WV",
    "300011": "Albany Pine Bush, NY",
    "360351": "Coffin Rock, PA",
    "172501": "Turner Brook, ME",
    "270301": "White Mtn NF, NH",
}
DATA_CSV = "data/processed/raws/northeast_hourly.csv"
