"""
Fire Weather Windows — Prescribed Fire Decision Support Dashboard
USDA Forest Service Fellowship Project | Pacific Northwest

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fire Weather Windows | PNW",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# THEME / STYLE
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* Root palette */
:root {
    --fire-amber:    #E8A24A;
    --fire-orange:   #D4622A;
    --smoke-gray:    #8A9BA8;
    --forest-green:  #2D5A3D;
    --sky-blue:      #4A90A4;
    --bg-dark:       #0F1A14;
    --bg-card:       #162019;
    --bg-panel:      #1C2B21;
    --text-primary:  #EDF2EE;
    --text-muted:    #7A9180;
    --border:        #2C3E30;
}

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--text-primary);
}

/* App background */
.stApp {
    background: var(--bg-dark);
    background-image:
        radial-gradient(ellipse at 10% 20%, rgba(45,90,61,0.25) 0%, transparent 50%),
        radial-gradient(ellipse at 90% 80%, rgba(212,98,42,0.08) 0%, transparent 50%);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; }

/* Cards / metric containers */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.metric-card .label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}
.metric-card .value {
    font-size: 26px;
    font-weight: 600;
    color: var(--fire-amber);
    line-height: 1;
}
.metric-card .sub {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* Section headers */
.section-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--smoke-gray);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
    margin-top: 8px;
}

/* Dashboard title */
.dash-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    color: var(--fire-amber);
    letter-spacing: -0.01em;
}
.dash-subtitle {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* Quality tier badges */
.tier-full     { background: #2D6A3F; color: #7FD99A; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-family: monospace; }
.tier-partial  { background: #3A4A1A; color: #B8D44A; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-family: monospace; }
.tier-marginal { background: #4A3A10; color: #E8A24A; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-family: monospace; }
.tier-none     { background: #2A1A1A; color: #8A5050; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-family: monospace; }

/* Anomaly badges */
.anom-above  { color: #7FD99A; font-weight: 600; }
.anom-near   { color: #E8A24A; }
.anom-below  { color: #D4622A; font-weight: 600; }

/* Streamlit overrides */
.stSelectbox label, .stMultiSelect label, .stSlider label,
.stCheckbox label, .stRadio label { color: var(--text-muted) !important; font-size: 12px !important; }

div[data-testid="stMetricValue"] { color: var(--fire-amber) !important; }
div[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 11px !important; }

/* Tabs */
button[data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--text-muted) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--fire-amber) !important;
    border-bottom-color: var(--fire-amber) !important;
}

/* Info boxes */
.info-box {
    background: var(--bg-panel);
    border-left: 3px solid var(--fire-amber);
    padding: 10px 14px;
    border-radius: 0 4px 4px 0;
    font-size: 12px;
    color: var(--text-muted);
    margin: 8px 0;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-dark); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
TIER_COLORS = {
    "full":     "#2D6A3F",
    "partial":  "#5A7A1A",
    "marginal": "#8A5A10",
    "no_window":"#3A1A1A",
}
TIER_LABELS = {
    "full":     "Full (6+ hrs)",
    "partial":  "Partial (3–5 hrs)",
    "marginal": "Marginal (1–2 hrs)",
    "no_window":"No Window",
}
TIER_ORDER = ["full", "partial", "marginal", "no_window"]

ANOM_COLORS = {
    "above_normal": "#7FD99A",
    "near_normal":  "#E8A24A",
    "below_normal": "#D4622A",
}

REGIME_MAP = {
    "ANEW1": "RH-constrained", "DRYW1": "RH-constrained",
    "GRFW1": "RH-constrained", "HIBW1": "RH-constrained",
    "KOSW1": "RH-constrained", "LBFO3": "RH-constrained",
    "PEFW1": "RH-constrained",
    "CGFO3": "Wind-constrained", "CMFW1": "Wind-constrained",
    "EVFO3": "Wind-constrained", "MILW1": "Wind-constrained",
    "TPEO3": "Wind-constrained", "TT246": "Wind-constrained",
    "VPFW1": "Wind-constrained", "WSRO3": "Wind-constrained",
}

THRESHOLDS = {"rh_min": 25, "rh_max": 55, "wind_min": 5, "wind_max": 15, "temp_max": 90}

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
DEFAULT_STATIONS = pd.DataFrame([
    {"station_id": "TT246", "station_name": "Entiat",       "state": "WA", "lat": 47.733, "lon": -120.243},
    {"station_id": "DRYW1", "station_name": "Dry Creek",    "state": "WA", "lat": 47.727, "lon": -120.540},
    {"station_id": "CMFW1", "station_name": "Camp 4",       "state": "WA", "lat": 48.025, "lon": -120.241},
    {"station_id": "VPFW1", "station_name": "Viewpoint",    "state": "WA", "lat": 47.855, "lon": -120.890},
    {"station_id": "ANEW1", "station_name": "Aeneas",       "state": "WA", "lat": 48.743, "lon": -119.622},
    {"station_id": "GRFW1", "station_name": "Grayback",     "state": "WA", "lat": 45.992, "lon": -121.083},
    {"station_id": "PEFW1", "station_name": "Peoh Point",   "state": "WA", "lat": 47.152, "lon": -120.947},
    {"station_id": "MILW1", "station_name": "Mill Creek",   "state": "WA", "lat": 46.263, "lon": -120.862},
    {"station_id": "HIBW1", "station_name": "Highbridge",   "state": "WA", "lat": 46.081, "lon": -120.544},
    {"station_id": "KOSW1", "station_name": "Kosmos",       "state": "WA", "lat": 46.524, "lon": -122.190},
    {"station_id": "LBFO3", "station_name": "Lava Butte",   "state": "OR", "lat": 43.925, "lon": -121.343},
    {"station_id": "WSRO3", "station_name": "Warm Springs", "state": "OR", "lat": 44.780, "lon": -121.250},
    {"station_id": "CGFO3", "station_name": "Colgate",      "state": "OR", "lat": 44.317, "lon": -121.607},
    {"station_id": "TPEO3", "station_name": "Tepee Draw",   "state": "OR", "lat": 43.835, "lon": -121.083},
    {"station_id": "EVFO3", "station_name": "Evans Creek",  "state": "OR", "lat": 42.598, "lon": -123.105},
])


@st.cache_data(ttl=3600)
def load_forecast_summary():
    p = Path("data/processed/ndfd/forecast_summary.csv")
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["forecast_date"])
    return df


@st.cache_data(ttl=3600)
def load_daily_windows():
    p = Path("data/processed/raws/daily_windows.csv")
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    return df


@st.cache_data(ttl=3600)
def load_climatology_monthly():
    p = Path("data/processed/raws/climatology_monthly.csv")
    if not p.exists():
        return None
    return pd.read_csv(p)


@st.cache_data(ttl=3600)
def load_station_annual():
    p = Path("data/processed/raws/station_annual_summary.csv")
    if not p.exists():
        return None
    return pd.read_csv(p)


@st.cache_data(ttl=3600)
def load_stations():
    p = Path("data/raw/raws/stations.csv")
    if p.exists():
        try:
            df = pd.read_csv(p)
            required = {"station_id", "station_name", "state", "lat", "lon"}
            if required.issubset(df.columns):
                return df
        except Exception:
            pass
    return DEFAULT_STATIONS.copy()


def load_all():
    return {
        "forecast":   load_forecast_summary(),
        "daily":      load_daily_windows(),
        "climo":      load_climatology_monthly(),
        "annual":     load_station_annual(),
        "stations":   load_stations(),
    }


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────
def tier_color_map(tier):
    return TIER_COLORS.get(tier, "#3A1A1A")


def forecast_color_for_station(forecast_df, station_id):
    """Return best tier in next 3 days for map coloring."""
    if forecast_df is None:
        return "#3A1A1A"
    sub = forecast_df[forecast_df["station_id"] == station_id]
    if sub.empty:
        return "#3A1A1A"
    tiers = sub["window_quality"].tolist()
    for t in TIER_ORDER:
        if t in tiers:
            return TIER_COLORS[t]
    return "#3A1A1A"


def tier_rank(tier):
    return {"full": 0, "partial": 1, "marginal": 2, "no_window": 3}.get(tier, 3)


def best_upcoming_tier(forecast_df, station_id):
    if forecast_df is None:
        return "no_window"
    sub = forecast_df[forecast_df["station_id"] == station_id]
    if sub.empty:
        return "no_window"
    tiers = sub["window_quality"].tolist()
    for t in TIER_ORDER:
        if t in tiers:
            return t
    return "no_window"


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
def render_sidebar(data):
    with st.sidebar:
        st.markdown("""
        <div class="dash-title">🔥 FireWindow</div>
        <div class="dash-subtitle">PNW Prescribed Burn Planner</div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        st.markdown('<div class="section-header">Station Selection</div>', unsafe_allow_html=True)

        stations_df = data["stations"]
        state_filter = st.multiselect(
            "State", options=["WA", "OR"],
            default=["WA", "OR"], key="state_filter"
        )
        regime_filter = st.multiselect(
            "Regime", options=["RH-constrained", "Wind-constrained"],
            default=["RH-constrained", "Wind-constrained"], key="regime_filter"
        )

        filtered_stations = stations_df[stations_df["state"].isin(state_filter)].copy()
        filtered_stations["regime"] = filtered_stations["station_id"].map(REGIME_MAP).fillna("Unknown")
        filtered_stations = filtered_stations[filtered_stations["regime"].isin(regime_filter)]

        station_options = filtered_stations["station_id"].tolist()
        station_labels = {
            r["station_id"]: f"{r['station_id']} — {r['station_name']}"
            for _, r in filtered_stations.iterrows()
        }

        selected_station = st.selectbox(
            "Focus Station",
            options=station_options,
            format_func=lambda x: station_labels.get(x, x),
            key="selected_station",
        )

        st.markdown("---")
        st.markdown('<div class="section-header">USFS Burn Thresholds</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="metric-card"><div class="label">RH Range</div><div class="value" style="font-size:18px">{THRESHOLDS["rh_min"]}–{THRESHOLDS["rh_max"]}%</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><div class="label">Wind Range</div><div class="value" style="font-size:18px">{THRESHOLDS["wind_min"]}–{THRESHOLDS["wind_max"]} mph</div></div>', unsafe_allow_html=True)

        st.markdown(f'<div class="info-box">Temperature ceiling {THRESHOLDS["temp_max"]}°F — rarely binding in PNW climate. NDFD forecast uses 50°F fill (documented design decision).</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div style="font-size:10px; color: #4A6050; font-family: monospace;">RAWS: Synoptic Data API<br>Forecast: NOAA NDFD REST<br>Thresholds: USFS Fire Weather Guide</div>', unsafe_allow_html=True)

    return selected_station, filtered_stations


# ─────────────────────────────────────────────
# TAB 1 — STATION MAP
# ─────────────────────────────────────────────
def render_map_tab(data, filtered_stations):
    st.markdown('<div class="section-header">Network Overview — Upcoming Burn Windows</div>', unsafe_allow_html=True)

    forecast_df = data["forecast"]
    annual_df   = data["annual"]
    stations_df = data["stations"]

    # Build network summary table
    rows = []
    for _, row in filtered_stations.iterrows():
        sid = row["station_id"]
        best_tier = best_upcoming_tier(forecast_df, sid)
        viable_pct = None
        peak_season = None
        if annual_df is not None and sid in annual_df["station_id"].values:
            ann_row = annual_df[annual_df["station_id"] == sid].iloc[0]
            viable_pct  = ann_row.get("pct_viable_days", None)
            peak_season = ann_row.get("peak_season", None)
        rows.append({
            "Station": sid,
            "Name": row["station_name"],
            "State": row["state"],
            "Regime": REGIME_MAP.get(sid, "—"),
            "Best Upcoming": best_tier,
            "Viable Days %": f"{viable_pct:.0f}%" if viable_pct is not None else "—",
            "Peak Season": peak_season if peak_season else "—",
        })

    summary_df = pd.DataFrame(rows)

    col_map, col_table = st.columns([1.2, 1])

    with col_map:
        m = folium.Map(
            location=[46.0, -120.8],
            zoom_start=7,
            tiles="CartoDB dark_matter",
        )

        for _, row in filtered_stations.iterrows():
            sid = row["station_id"]
            color = forecast_color_for_station(forecast_df, sid)
            best  = best_upcoming_tier(forecast_df, sid)
            tier_label = TIER_LABELS.get(best, "—")
            popup_html = f"""
            <div style='font-family:monospace;font-size:12px;background:#162019;
                        color:#EDF2EE;padding:10px;border-radius:4px;min-width:180px'>
              <b style='color:#E8A24A'>{sid}</b><br>
              {row['station_name']}, {row['state']}<br>
              <hr style='border-color:#2C3E30;margin:5px 0'>
              Regime: {REGIME_MAP.get(sid, '—')}<br>
              Best window: <b>{tier_label}</b>
            </div>
            """
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=10,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                weight=2,
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"{sid} — {row['station_name']}",
            ).add_to(m)

        # Legend
        legend_html = """
        <div style='position:fixed;bottom:20px;left:20px;z-index:1000;background:#162019;
                    border:1px solid #2C3E30;border-radius:6px;padding:12px;font-family:monospace;font-size:11px;color:#EDF2EE'>
          <b style='color:#E8A24A'>Upcoming Window Quality</b><br>
          <span style='color:#2D6A3F'>●</span> Full (6+ hrs)<br>
          <span style='color:#5A7A1A'>●</span> Partial (3–5 hrs)<br>
          <span style='color:#8A5A10'>●</span> Marginal (1–2 hrs)<br>
          <span style='color:#6A2A2A'>●</span> No Window
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, width=None, height=460, returned_objects=[])

    with col_table:
        st.markdown('<div class="section-header">Network Summary</div>', unsafe_allow_html=True)

        for _, row in summary_df.iterrows():
            tier = row["Best Upcoming"]
            tier_css = tier.replace("_", "")
            tier_display = TIER_LABELS.get(tier, tier)
            regime_color = "#7FD99A" if row["Regime"] == "RH-constrained" else "#E8A24A"
            st.markdown(f"""
            <div class="metric-card" style="padding:12px 16px; margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <span style="font-family:monospace;font-size:13px;font-weight:600;color:#E8A24A">{row['Station']}</span>
                  <span style="font-size:12px;color:#7A9180;margin-left:8px">{row['Name']}, {row['State']}</span>
                </div>
                <span class="tier-{tier_css.replace('no_window','none')}">{tier_display}</span>
              </div>
              <div style="margin-top:6px;font-size:11px;color:#4A6050">
                <span style="color:{regime_color}">{row['Regime']}</span>
                &nbsp;·&nbsp; {row['Viable Days %']} viable days
                &nbsp;·&nbsp; Peak: {row['Peak Season']}
              </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TAB 2 — FORECAST PANEL
# ─────────────────────────────────────────────
def render_forecast_tab(data, selected_station):
    st.markdown(f'<div class="section-header">7-Day Burn Window Forecast — {selected_station}</div>', unsafe_allow_html=True)

    forecast_df = data["forecast"]
    if forecast_df is None:
        st.warning("⚠ Forecast data not found at `data/processed/ndfd/forecast_summary.csv`. Run `python src/analysis/forecast_windows.py` to generate.")
        return

    station_meta = data["stations"]
    sname = station_meta[station_meta["station_id"] == selected_station]["station_name"].values
    sname = sname[0] if len(sname) > 0 else selected_station

    sub = forecast_df[forecast_df["station_id"] == selected_station].copy()
    if sub.empty:
        st.info(f"No forecast data available for {selected_station}.")
        return

    sub = sub.sort_values("forecast_date")

    # ── Top KPI row
    total_days      = len(sub)
    viable_days     = (sub["window_quality"] != "no_window").sum()
    full_days       = (sub["window_quality"] == "full").sum()
    above_norm_days = (sub.get("anomaly_class", pd.Series()) == "above_normal").sum() if "anomaly_class" in sub.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        (c1, "Forecast Days",    str(total_days),          ""),
        (c2, "Viable Windows",   str(viable_days),         f"of {total_days} days"),
        (c3, "Full Windows",     str(full_days),           "6+ hrs available"),
        (c4, "Above-Normal Days",str(above_norm_days),     "vs. April climatology"),
    ]
    for col, label, val, sub_val in metrics:
        with col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="label">{label}</div>
              <div class="value">{val}</div>
              <div class="sub">{sub_val}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Forecast heatmap bar
    col_chart, col_detail = st.columns([2, 1])

    with col_chart:
        st.markdown('<div class="section-header">Daily Window Quality</div>', unsafe_allow_html=True)

        dates    = sub["forecast_date"].dt.strftime("%b %d").tolist()
        tiers    = sub["window_quality"].tolist()
        hrs_col  = "viable_hours" if "viable_hours" in sub.columns else "window_hours"
        hours    = sub[hrs_col].fillna(0).tolist() if hrs_col in sub.columns else [0] * len(sub)

        colors = [TIER_COLORS.get(t, "#3A1A1A") for t in tiers]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates,
            y=hours,
            marker_color=colors,
            text=[f"{h:.0f}h" if h > 0 else "" for h in hours],
            textposition="inside",
            textfont=dict(family="IBM Plex Mono", size=12, color="#EDF2EE"),
            hovertemplate="<b>%{x}</b><br>Viable hours: %{y:.1f}<extra></extra>",
        ))

        # Anomaly markers
        if "anomaly_class" in sub.columns:
            for i, (d, t, anom) in enumerate(zip(dates, hours, sub["anomaly_class"].tolist())):
                marker = {"above_normal": "▲", "below_normal": "▼", "near_normal": "●"}.get(anom, "")
                color  = ANOM_COLORS.get(anom, "#888")
                if marker:
                    fig.add_annotation(
                        x=d, y=t + 0.3,
                        text=f'<span style="color:{color}">{marker}</span>',
                        showarrow=False,
                        font=dict(size=14, color=color),
                        yshift=8,
                    )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,32,25,0.6)",
            font=dict(family="IBM Plex Sans", color="#EDF2EE"),
            xaxis=dict(tickfont=dict(family="IBM Plex Mono", size=11), gridcolor="#2C3E30", showgrid=False),
            yaxis=dict(
                title="Viable Hours", tickfont=dict(size=11),
                gridcolor="#2C3E30", title_font=dict(size=11),
                range=[0, max(hours) * 1.35 + 1] if max(hours) > 0 else [0, 10],
            ),
            margin=dict(l=40, r=20, t=20, b=30),
            height=300,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_detail:
        st.markdown('<div class="section-header">Day-by-Day Detail</div>', unsafe_allow_html=True)
        for _, row in sub.iterrows():
            tier = row["window_quality"]
            tier_css = {"full": "full", "partial": "partial", "marginal": "marginal", "no_window": "none"}.get(tier, "none")
            anom = row.get("anomaly_class", "") if "anomaly_class" in sub.columns else ""
            anom_sym = {"above_normal": '<span class="anom-above">▲ Above</span>',
                        "below_normal": '<span class="anom-below">▼ Below</span>',
                        "near_normal":  '<span class="anom-near">● Near</span>'}.get(anom, "")
            hrs_val = row.get(hrs_col, 0) if hrs_col in sub.columns else 0
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:6px 0;border-bottom:1px solid #2C3E30;font-size:12px">
              <span style="font-family:monospace;color:#8A9BA8">{row['forecast_date'].strftime('%a %b %d')}</span>
              <span class="tier-{tier_css}">{TIER_LABELS.get(tier,'—')}</span>
              <span style="color:#7A9180">{hrs_val:.0f}h {anom_sym}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Network overview heatmap
    st.markdown("---")
    st.markdown('<div class="section-header">Network Window Forecast — All Stations</div>', unsafe_allow_html=True)

    pivot_data = []
    all_stations_sorted = forecast_df["station_id"].unique().tolist()
    all_dates = sorted(forecast_df["forecast_date"].unique())

    for sid in all_stations_sorted:
        sub2 = forecast_df[forecast_df["station_id"] == sid].sort_values("forecast_date")
        row_data = {"station_id": sid}
        for d in all_dates:
            day_row = sub2[sub2["forecast_date"] == d]
            if not day_row.empty:
                row_data[str(d)[:10]] = day_row.iloc[0]["window_quality"]
            else:
                row_data[str(d)[:10]] = "no_window"
        pivot_data.append(row_data)

    if pivot_data:
        date_cols = [str(d)[:10] for d in all_dates]
        z_numeric = []
        tier_to_num = {"full": 3, "partial": 2, "marginal": 1, "no_window": 0}
        text_matrix = []

        for row_data in pivot_data:
            z_row, t_row = [], []
            for dc in date_cols:
                tier = row_data.get(dc, "no_window")
                z_row.append(tier_to_num.get(tier, 0))
                hrs_here = 0
                if forecast_df is not None:
                    match = forecast_df[
                        (forecast_df["station_id"] == row_data["station_id"]) &
                        (forecast_df["forecast_date"].astype(str).str[:10] == dc)
                    ]
                    if not match.empty and hrs_col in match.columns:
                        hrs_here = match.iloc[0][hrs_col]
                t_row.append(f"{hrs_here:.0f}h" if hrs_here > 0 else "—")
            z_numeric.append(z_row)
            text_matrix.append(t_row)

        station_names_short = [r["station_id"] for r in pivot_data]
        date_labels = [pd.Timestamp(d).strftime("%b %d") for d in date_cols]

        colorscale = [
            [0.00, "#2A1A1A"],
            [0.33, "#4A3A10"],
            [0.66, "#3A4A1A"],
            [1.00, "#1A4A2A"],
        ]

        fig2 = go.Figure(go.Heatmap(
            z=z_numeric,
            x=date_labels,
            y=station_names_short,
            text=text_matrix,
            texttemplate="%{text}",
            colorscale=colorscale,
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}<br>%{text}<extra></extra>",
            textfont=dict(family="IBM Plex Mono", size=10),
            zmin=0, zmax=3,
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,32,25,0.6)",
            font=dict(family="IBM Plex Mono", color="#EDF2EE", size=11),
            xaxis=dict(side="top", tickfont=dict(size=11), gridcolor="#2C3E30"),
            yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
            margin=dict(l=70, r=20, t=40, b=10),
            height=380,
        )
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        st.markdown("""
        <div class="info-box">
          ▲ Above-normal &nbsp;|&nbsp; ● Near-normal &nbsp;|&nbsp; ▼ Below-normal &nbsp; vs. April climatological baseline.
          Temperature threshold (< 90°F) not forecast by NDFD for PNW; 50°F fill used — see README.
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TAB 3 — HISTORICAL CALENDAR
# ─────────────────────────────────────────────
def render_calendar_tab(data, selected_station):
    st.markdown(f'<div class="section-header">Historical Burn Window Record — {selected_station}</div>', unsafe_allow_html=True)

    daily_df = data["daily"]
    climo_df = data["climo"]
    annual_df = data["annual"]

    if daily_df is None:
        st.warning("⚠ Daily window data not found at `data/processed/raws/daily_windows.csv`. Run `src/analysis/burn_windows.py` to generate.")
        return

    station_meta = data["stations"]
    sname = station_meta[station_meta["station_id"] == selected_station]["station_name"].values
    sname = sname[0] if len(sname) > 0 else selected_station

    sub = daily_df[daily_df["station_id"] == selected_station].copy()
    if sub.empty:
        st.info(f"No historical data for {selected_station}.")
        return

    sub = sub.sort_values("date")
    sub["year"]  = sub["date"].dt.year
    sub["month"] = sub["date"].dt.month
    sub["week"]  = sub["date"].dt.isocalendar().week.astype(int)
    sub["doy"]   = sub["date"].dt.dayofyear
    sub["tier_num"] = sub["window_quality"].map({"full": 3, "partial": 2, "marginal": 1, "no_window": 0}).fillna(0)

    hrs_col = "viable_hours" if "viable_hours" in sub.columns else ("window_hours" if "window_hours" in sub.columns else None)

    col1, col2 = st.columns([1.5, 1])

    # ── Monthly climatology bar chart
    with col1:
        if climo_df is not None and selected_station in climo_df["station_id"].values:
            st.markdown('<div class="section-header">Monthly Climatology — Viable Day %</div>', unsafe_allow_html=True)
            cs = climo_df[climo_df["station_id"] == selected_station].copy()
            cs = cs.sort_values("month")
            month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            cs["month_label"] = cs["month"].apply(lambda m: month_names[m-1])

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=cs["month_label"],
                y=cs["pct_viable_days"],
                marker_color=[
                    "#2D6A3F" if v >= 30 else "#5A7A1A" if v >= 15 else "#8A5A10" if v >= 5 else "#3A2A10"
                    for v in cs["pct_viable_days"]
                ],
                hovertemplate="<b>%{x}</b><br>Viable: %{y:.1f}%<extra></extra>",
                text=[f"{v:.0f}%" for v in cs["pct_viable_days"]],
                textposition="outside",
                textfont=dict(family="IBM Plex Mono", size=10, color="#7A9180"),
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(22,32,25,0.6)",
                font=dict(family="IBM Plex Sans", color="#EDF2EE"),
                xaxis=dict(tickfont=dict(family="IBM Plex Mono", size=11), showgrid=False),
                yaxis=dict(
                    title="% Viable Days", tickfont=dict(size=11),
                    gridcolor="#2C3E30", range=[0, max(cs["pct_viable_days"]) * 1.25 + 5],
                ),
                margin=dict(l=40, r=10, t=10, b=30),
                height=280,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        if annual_df is not None and selected_station in annual_df["station_id"].values:
            st.markdown('<div class="section-header">Annual Summary</div>', unsafe_allow_html=True)
            ann = annual_df[annual_df["station_id"] == selected_station].iloc[0]
            fields = [
                ("Viable Days / Year",   f"{ann.get('mean_viable_days', ann.get('viable_days_per_year', '—')):.0f}" if isinstance(ann.get('mean_viable_days', ann.get('viable_days_per_year')), (int, float)) else "—"),
                ("Full Window Days",     f"{ann.get('full_window_days', '—'):.0f}" if isinstance(ann.get('full_window_days'), (int, float)) else "—"),
                ("Peak Season",          str(ann.get("peak_season", "—"))),
                ("Limiting Factor",      str(ann.get("limiting_factor", "—")).replace("_", " ").title()),
                ("Constraint Regime",    REGIME_MAP.get(selected_station, "—")),
            ]
            for label, val in fields:
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:7px 0;
                            border-bottom:1px solid #2C3E30;font-size:12px">
                  <span style="color:#7A9180">{label}</span>
                  <span style="font-family:monospace;color:#E8A24A;font-weight:500">{val}</span>
                </div>
                """, unsafe_allow_html=True)

    # ── Full-window day calendar heatmap (week × day-of-week)
    st.markdown("---")
    st.markdown('<div class="section-header">Full-Window Days — Calendar View</div>', unsafe_allow_html=True)

    sub_full = sub[sub["window_quality"] == "full"].copy()
    if sub_full.empty:
        st.info("No full-window days recorded for this station.")
    else:
        sub_full["dow"]  = sub_full["date"].dt.dayofweek   # 0=Mon
        sub_full["week_of_year"] = sub_full["date"].dt.isocalendar().week.astype(int)
        sub_full["year_week"] = sub_full["date"].dt.strftime("%Y-W%W")

        # Build monthly proportion bar across weeks
        monthly_viable = sub[sub["window_quality"] != "no_window"].groupby("month").size()
        monthly_total  = sub.groupby("month").size()
        monthly_pct    = (monthly_viable / monthly_total * 100).reindex(range(1, 13), fill_value=0)

        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        fig3 = make_subplots(
            rows=1, cols=2,
            subplot_titles=["Any-Window Days by Month (%)", "Full Window Days by Month (count)"],
            horizontal_spacing=0.08,
        )
        fig3.add_trace(go.Bar(
            x=month_names,
            y=monthly_pct.values,
            marker_color=["#2D6A3F" if v >= 30 else "#5A7A1A" if v >= 15 else "#6A4A10" for v in monthly_pct.values],
            name="Any Window %",
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ), row=1, col=1)

        monthly_full = sub_full.groupby("month").size().reindex(range(1, 13), fill_value=0)
        fig3.add_trace(go.Bar(
            x=month_names,
            y=monthly_full.values,
            marker_color=["#1A4A2A" if v > 10 else "#2D6A3F" if v > 3 else "#3A5A2A" for v in monthly_full.values],
            name="Full Windows",
            hovertemplate="%{x}: %{y} days<extra></extra>",
        ), row=1, col=2)

        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,32,25,0.6)",
            font=dict(family="IBM Plex Sans", color="#EDF2EE", size=11),
            showlegend=False,
            margin=dict(l=40, r=20, t=40, b=30),
            height=280,
        )
        for axis in ["xaxis", "xaxis2"]:
            fig3.update_layout(**{axis: dict(tickfont=dict(family="IBM Plex Mono", size=10), showgrid=False)})
        for axis in ["yaxis", "yaxis2"]:
            fig3.update_layout(**{axis: dict(gridcolor="#2C3E30", tickfont=dict(size=10))})

        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    # ── Constraint breakdown
    if climo_df is not None and selected_station in climo_df["station_id"].values:
        st.markdown("---")
        st.markdown('<div class="section-header">Constraint Breakdown — Limiting Factors</div>', unsafe_allow_html=True)
        cs = climo_df[climo_df["station_id"] == selected_station].copy().sort_values("month")

        flag_cols = [c for c in cs.columns if c.startswith("pct_") and c not in ("pct_viable_days", "pct_full_days")]
        if flag_cols:
            fig4 = go.Figure()
            month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            cs["month_label"] = cs["month"].apply(lambda m: month_labels[m-1])
            flag_colors = {
                "pct_wind_too_calm":   "#4A6090",
                "pct_wind_too_strong": "#A05030",
                "pct_rh_too_wet":      "#2060A0",
                "pct_rh_too_dry":      "#A07030",
                "pct_temp_too_hot":    "#C03030",
            }
            flag_labels = {
                "pct_wind_too_calm":   "Wind Too Calm",
                "pct_wind_too_strong": "Wind Too Strong",
                "pct_rh_too_wet":      "RH Too Wet",
                "pct_rh_too_dry":      "RH Too Dry",
                "pct_temp_too_hot":    "Temp Too Hot",
            }
            for fc in flag_cols:
                if fc in cs.columns:
                    fig4.add_trace(go.Bar(
                        name=flag_labels.get(fc, fc),
                        x=cs["month_label"],
                        y=cs[fc],
                        marker_color=flag_colors.get(fc, "#666"),
                        hovertemplate=f"<b>{flag_labels.get(fc, fc)}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
                    ))
            fig4.update_layout(
                barmode="stack",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(22,32,25,0.6)",
                font=dict(family="IBM Plex Sans", color="#EDF2EE", size=11),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                            font=dict(size=10, family="IBM Plex Mono")),
                xaxis=dict(tickfont=dict(family="IBM Plex Mono", size=10), showgrid=False),
                yaxis=dict(title="% Hours", gridcolor="#2C3E30", tickfont=dict(size=10)),
                margin=dict(l=40, r=20, t=50, b=30),
                height=280,
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────
# TAB 4 — CLIMATOLOGY EXPLORER
# ─────────────────────────────────────────────
def render_climo_tab(data, filtered_stations):
    st.markdown('<div class="section-header">Network Climatology — Cross-Station Comparison</div>', unsafe_allow_html=True)

    climo_df  = data["climo"]
    annual_df = data["annual"]

    if climo_df is None:
        st.warning("⚠ Climatology data not found. Run `src/analysis/climatology.py`.")
        return

    station_ids = filtered_stations["station_id"].tolist()
    cs_all = climo_df[climo_df["station_id"].isin(station_ids)].copy()

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    cs_all["month_label"] = cs_all["month"].apply(lambda m: month_names[m-1])

    # Pivot: stations × months → pct_viable_days heatmap
    st.markdown('<div class="section-header">Viable Day % — All Stations × Month</div>', unsafe_allow_html=True)

    pivot = cs_all.pivot_table(index="station_id", columns="month", values="pct_viable_days", aggfunc="mean")
    pivot = pivot.reindex(columns=range(1, 13)).fillna(0)
    pivot.columns = month_names

    # Sort by regime then mean
    pivot["regime"] = pivot.index.map(REGIME_MAP)
    pivot["mean"]   = pivot[month_names].mean(axis=1)
    pivot = pivot.sort_values(["regime", "mean"], ascending=[True, False])
    pivot_plot = pivot[month_names]

    fig = go.Figure(go.Heatmap(
        z=pivot_plot.values,
        x=month_names,
        y=pivot_plot.index.tolist(),
        colorscale=[
            [0.0,  "#1A0A0A"],
            [0.1,  "#3A1A1A"],
            [0.3,  "#5A3A10"],
            [0.5,  "#6A5A20"],
            [0.7,  "#3A6A2A"],
            [1.0,  "#1A5A2A"],
        ],
        text=[[f"{v:.0f}%" for v in row] for row in pivot_plot.values],
        texttemplate="%{text}",
        showscale=True,
        colorbar=dict(
            title=dict(text="% Viable", font=dict(size=10, color="#7A9180")),
            tickfont=dict(size=10, color="#7A9180"),
            thickness=12,
        ),
        hovertemplate="<b>%{y}</b> — %{x}<br>Viable: %{z:.1f}%<extra></extra>",
        textfont=dict(family="IBM Plex Mono", size=10),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(22,32,25,0.6)",
        font=dict(family="IBM Plex Mono", color="#EDF2EE"),
        xaxis=dict(tickfont=dict(size=11), side="top"),
        yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
        margin=dict(l=70, r=60, t=40, b=10),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Regime comparison
    if annual_df is not None:
        st.markdown("---")
        st.markdown('<div class="section-header">Constraint Regime Summary</div>', unsafe_allow_html=True)

        ann_filtered = annual_df[annual_df["station_id"].isin(station_ids)].copy()
        ann_filtered["regime"] = ann_filtered["station_id"].map(REGIME_MAP).fillna("Unknown")

        col1, col2 = st.columns(2)

        rh_constrained  = ann_filtered[ann_filtered["regime"] == "RH-constrained"]
        wind_constrained = ann_filtered[ann_filtered["regime"] == "Wind-constrained"]

        def safe_mean(df, col):
            if col in df.columns and len(df) > 0:
                return df[col].mean()
            return None

        viable_col = "mean_viable_days" if "mean_viable_days" in ann_filtered.columns else "viable_days_per_year"

        with col1:
            st.markdown("""
            <div class="metric-card">
              <div class="label" style="color:#7FD99A">RH-Constrained Stations</div>
              <div style="font-size:11px;color:#7A9180;margin-top:4px">
                RH too wet limits windows; wind dispersal not binding.
                Higher overall viability.
              </div>
            </div>
            """, unsafe_allow_html=True)
            if viable_col in rh_constrained.columns and len(rh_constrained) > 0:
                mean_viable = rh_constrained[viable_col].mean()
                st.markdown(f'<div class="metric-card"><div class="label">Mean Viable Days / Year</div><div class="value">{mean_viable:.0f}</div></div>', unsafe_allow_html=True)
            for _, row in rh_constrained.iterrows():
                v = row.get(viable_col, "—")
                v_str = f"{v:.0f}" if isinstance(v, float) else str(v)
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;font-size:12px;
                            padding:5px 0;border-bottom:1px solid #2C3E30">
                  <span style="font-family:monospace;color:#7FD99A">{row['station_id']}</span>
                  <span style="color:#7A9180">{v_str} viable days/yr</span>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="metric-card">
              <div class="label" style="color:#E8A24A">Wind-Constrained Stations</div>
              <div style="font-size:11px;color:#7A9180;margin-top:4px">
                Wind too calm — smoke dispersal floor not met.
                Lower viability; any window is significant.
              </div>
            </div>
            """, unsafe_allow_html=True)
            if viable_col in wind_constrained.columns and len(wind_constrained) > 0:
                mean_viable = wind_constrained[viable_col].mean()
                st.markdown(f'<div class="metric-card"><div class="label">Mean Viable Days / Year</div><div class="value">{mean_viable:.0f}</div></div>', unsafe_allow_html=True)
            for _, row in wind_constrained.iterrows():
                v = row.get(viable_col, "—")
                v_str = f"{v:.0f}" if isinstance(v, float) else str(v)
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;font-size:12px;
                            padding:5px 0;border-bottom:1px solid #2C3E30">
                  <span style="font-family:monospace;color:#E8A24A">{row['station_id']}</span>
                  <span style="color:#7A9180">{v_str} viable days/yr</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-box" style="margin-top:16px">
          Temperature (< 90°F) almost never constrains PNW windows — max 376 temp-fail hours/year at WSRO3.
          This is an ecologically meaningful finding: PNW prescribed fire programs are limited by fuel moisture and
          smoke dispersal, not temperature.
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TAB 5 — BRIEFING
# ─────────────────────────────────────────────
def render_briefing_tab(data, selected_station, filtered_stations):
    """Coordinator-facing plain-English situation report."""

    forecast_df = data["forecast"]
    daily_df    = data["daily"]
    climo_df    = data["climo"]
    annual_df   = data["annual"]
    stations_df = data["stations"]

    station_meta = stations_df[stations_df["station_id"] == selected_station]
    sname = station_meta["station_name"].values[0] if len(station_meta) > 0 else selected_station
    state = station_meta["state"].values[0] if len(station_meta) > 0 else ""
    regime = REGIME_MAP.get(selected_station, "unknown")

    from datetime import date
    today_str = date.today().strftime("%B %d, %Y")

    # ── Page header
    st.markdown(f"""
    <div style="margin-bottom:24px">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:600;color:#E8A24A">
        Situation Briefing
      </div>
      <div style="font-size:12px;color:#4A6050;margin-top:2px;font-family:monospace">
        Generated {today_str} · Station: {selected_station} ({sname}, {state})
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # SECTION 1 — WHAT IS THIS TOOL
    # ══════════════════════════════════════════
    st.markdown('<div class="section-header">About This Tool</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:13px;color:#C8D8C8;line-height:1.75;max-width:860px">
      <p>This dashboard identifies viable prescribed burn windows across 15 RAWS weather stations in Washington
      and Oregon. A <b style="color:#E8A24A">burn window</b> is a period when temperature, relative humidity,
      and wind speed all fall within USFS-standard thresholds simultaneously — conditions under which a
      prescribed fire can be safely ignited and controlled.</p>
      <p>The tool draws on two data sources: roughly one year of hourly historical observations from each station
      (used to build climatological baselines), and a 7-day NOAA NDFD weather forecast (used to flag upcoming
      candidate windows). Use the sidebar to switch between stations and filter by state or constraint regime.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════
    # SECTION 2 — HOW TO READ EACH TAB
    # ══════════════════════════════════════════
    st.markdown('<div class="section-header">How to Read Each Panel</div>', unsafe_allow_html=True)

    panels = [
        (
            "📍 Station Map",
            "Each dot represents a RAWS weather station. The color indicates the best burn window quality "
            "forecast in the next 7 days: dark green means a full window (6+ viable hours) is expected, "
            "amber means marginal conditions, dark red means no window is forecast. Click any station "
            "marker for its name and constraint regime. The table to the right summarizes viable-day "
            "percentage from historical data and each station's typical peak burn season."
        ),
        (
            "📅 7-Day Forecast",
            "The bar chart shows how many hours per day are forecast to meet all three burn thresholds "
            "(RH 25–55%, wind 5–15 mph, temp < 90°F). Taller green bars are better. The triangles above "
            "bars are anomaly markers: ▲ means this day has more viable hours than is typical for this "
            "month historically, ▼ means fewer. The heatmap below shows the same information for all 15 "
            "stations at once — useful for identifying which stations have the best windows on a given day "
            "if you have flexibility on burn location."
        ),
        (
            "📊 Historical Record",
            "The monthly bar chart shows what percentage of days in each month have historically had at "
            "least one viable burn hour at this station. Higher bars = more reliable burn months. The "
            "stacked bar chart below it breaks down what is causing failures each month — whether hours "
            "are lost to RH being too wet, wind being too calm, wind being too strong, and so on. This "
            "helps you understand not just when windows open, but why they close."
        ),
        (
            "🌲 Climatology",
            "The network heatmap shows viable-day percentage for every station across every month — "
            "darker green cells are the best station-month combinations across the network. Stations are "
            "grouped by constraint regime (RH-constrained vs. wind-constrained). Below the heatmap, "
            "each regime is summarized separately with per-station annual viable-day counts."
        ),
    ]

    for title, explanation in panels:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
                      color:#E8A24A;margin-bottom:8px">{title}</div>
          <div style="font-size:13px;color:#C8D8C8;line-height:1.7">{explanation}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════
    # SECTION 3 — THRESHOLDS EXPLAINED
    # ══════════════════════════════════════════
    st.markdown('<div class="section-header">Burn Window Thresholds — What They Mean and Why</div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:13px;color:#C8D8C8;line-height:1.75;max-width:860px;margin-bottom:16px">
      The three thresholds used throughout this tool come from USFS fire weather planning guides and reflect
      the physical conditions that make prescribed fire both effective and controllable.
    </div>
    """, unsafe_allow_html=True)

    threshold_explanations = [
        (
            "Relative Humidity — 25% to 55%",
            "RH is the primary indicator of fine fuel moisture — how wet or dry the grasses, duff, and "
            "small woody material are that carry the fire. Below 25%, fuels are critically dry: the fire "
            "may spread faster and more intensely than crews can manage. Above 55%, fuels are too moist "
            "to carry a consistent fire, and ignition and spread become unreliable. The 25–55% band is "
            "where fire behavior is predictable and manageable."
        ),
        (
            "Wind Speed — 5 to 15 mph",
            "Wind has two roles in prescribed fire. On the lower end, a minimum of 5 mph is required for "
            "smoke dispersal — without adequate wind, smoke from the burn accumulates at ground level, "
            "creating air quality and visibility hazards for crews and nearby roads. On the upper end, "
            "winds above 15 mph increase spotting potential (embers lofted across containment lines) and "
            "can cause rapid, unpredictable fire runs. The 5–15 mph range keeps smoke moving while "
            "maintaining control."
        ),
        (
            "Temperature — Below 90°F",
            "High temperatures accelerate fuel drying and increase fire intensity. The 90°F ceiling is "
            "a conservative upper bound for safe ignition conditions. In the Pacific Northwest, this "
            "threshold is rarely reached — the data across all 15 stations shows temperature almost "
            "never drives window failures. RH and wind are the operative constraints in this region."
        ),
        (
            "Window Quality Tiers",
            "A single hour meeting all three thresholds is necessary but rarely sufficient for a burn "
            "operation. Full windows (6+ viable hours) allow time for full ignition sequences, adequate "
            "holding periods, and mop-up. Partial windows (3–5 hours) may support smaller units or "
            "early-morning burns. Marginal windows (1–2 hours) are noted but rarely operationally "
            "useful — conditions may shift before a crew can safely complete ignition."
        ),
    ]

    col1, col2 = st.columns(2)
    for i, (title, body) in enumerate(threshold_explanations):
        col = col1 if i % 2 == 0 else col2
        with col:
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:12px;min-height:160px">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
                          color:#E8A24A;margin-bottom:8px">{title}</div>
              <div style="font-size:12px;color:#C8D8C8;line-height:1.7">{body}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════
    # SECTION 4 — SELECTED STATION BRIEFING
    # ══════════════════════════════════════════
    st.markdown(f'<div class="section-header">Station Briefing — {selected_station} ({sname})</div>', unsafe_allow_html=True)

    # Regime explanation
    if regime == "RH-constrained":
        regime_text = (
            f"{selected_station} is an <b style='color:#7FD99A'>RH-constrained</b> station. "
            "Relative humidity is the primary limiting factor here — windows close most often because "
            "conditions are too wet (RH above 55%), not because wind is insufficient. This station "
            "tends to have higher overall viability than wind-constrained stations, and its windows "
            "are most reliably available during drier periods — typically late spring through early fall."
        )
    else:
        regime_text = (
            f"{selected_station} is a <b style='color:#E8A24A'>wind-constrained</b> station. "
            "Wind speed is the primary limiting factor here — the 5 mph smoke dispersal floor is "
            "frequently not met. This is common in sheltered valley or basin locations where terrain "
            "suppresses ambient wind. Viable windows at this station are less frequent overall, which "
            "means any forecast window is operationally significant and worth tracking closely."
        )

    st.markdown(f"""
    <div class="metric-card" style="margin-bottom:16px">
      <div style="font-size:13px;color:#C8D8C8;line-height:1.75">{regime_text}</div>
    </div>
    """, unsafe_allow_html=True)

    # Annual stats prose
    if annual_df is not None and selected_station in annual_df["station_id"].values:
        ann = annual_df[annual_df["station_id"] == selected_station].iloc[0]
        viable_col = "mean_viable_days" if "mean_viable_days" in ann.index else "viable_days_per_year"
        viable_days = ann.get(viable_col)
        peak_season = ann.get("peak_season", None)
        limiting    = str(ann.get("limiting_factor", "")).replace("_", " ")
        full_days   = ann.get("full_window_days")

        parts = []
        if viable_days is not None and not pd.isna(viable_days):
            parts.append(
                f"Over the past year, <b style='color:#E8A24A'>{viable_days:.0f} days</b> at this station "
                f"had at least one viable burn hour."
            )
        if full_days is not None and not pd.isna(full_days):
            parts.append(
                f"Of those, <b style='color:#7FD99A'>{full_days:.0f} days</b> had a full window of 6 or more hours — "
                "the tier most likely to support a complete burn operation."
            )
        if peak_season:
            parts.append(
                f"The historical peak burn season at this station is <b style='color:#E8A24A'>{peak_season}</b>, "
                "when the combination of RH, wind, and temperature most reliably falls within thresholds."
            )
        if limiting:
            parts.append(
                f"The primary limiting factor is <b style='color:#E8A24A'>{limiting}</b> — "
                "the variable most frequently responsible for hours falling outside the burn window."
            )

        if parts:
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:16px">
              <div style="font-size:13px;color:#C8D8C8;line-height:1.85">
                {"<br>".join(parts)}
              </div>
            </div>
            """, unsafe_allow_html=True)

    # Forecast prose for selected station
    if forecast_df is not None:
        sub = forecast_df[forecast_df["station_id"] == selected_station].copy()
        if not sub.empty:
            sub = sub.sort_values("forecast_date")
            hrs_col = "viable_hours" if "viable_hours" in sub.columns else "window_hours"

            best_row   = sub.loc[sub[hrs_col].idxmax()] if hrs_col in sub.columns else None
            viable_ct  = (sub["window_quality"] != "no_window").sum()
            full_ct    = (sub["window_quality"] == "full").sum()
            above_ct   = (sub.get("anomaly_class", pd.Series(dtype=str)) == "above_normal").sum() if "anomaly_class" in sub.columns else 0
            below_ct   = (sub.get("anomaly_class", pd.Series(dtype=str)) == "below_normal").sum() if "anomaly_class" in sub.columns else 0

            forecast_parts = []

            if viable_ct == 0:
                forecast_parts.append(
                    "The 7-day forecast shows <b style='color:#D4622A'>no viable burn windows</b> at this station. "
                    "All forecast days are expected to fail at least one threshold condition."
                )
            else:
                forecast_parts.append(
                    f"The 7-day forecast shows viable burn windows on <b style='color:#E8A24A'>{viable_ct} of 7 days</b> "
                    f"at this station, including <b style='color:#7FD99A'>{full_ct} full-window day{'s' if full_ct != 1 else ''}</b> "
                    f"with 6 or more viable hours."
                )

            if best_row is not None and hrs_col in sub.columns:
                best_hrs  = best_row[hrs_col]
                best_date = pd.Timestamp(best_row["forecast_date"]).strftime("%A, %B %d")
                if best_hrs > 0:
                    forecast_parts.append(
                        f"The best single-day window is forecast for <b style='color:#E8A24A'>{best_date}</b>, "
                        f"with approximately <b style='color:#7FD99A'>{best_hrs:.0f} viable hours</b>."
                    )

            if above_ct > 0:
                forecast_parts.append(
                    f"{above_ct} forecast day{'s are' if above_ct > 1 else ' is'} classified as "
                    f"<b style='color:#7FD99A'>above-normal</b> relative to the April climatological baseline — "
                    "meaning conditions are better than historically typical for this time of year."
                )
            if below_ct > 0:
                forecast_parts.append(
                    f"{below_ct} forecast day{'s are' if below_ct > 1 else ' is'} classified as "
                    f"<b style='color:#D4622A'>below-normal</b> — conditions are worse than the historical average "
                    "for April at this station."
                )

            st.markdown(f"""
            <div class="metric-card">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#4A6050;
                          margin-bottom:8px;letter-spacing:0.08em">7-DAY FORECAST SUMMARY</div>
              <div style="font-size:13px;color:#C8D8C8;line-height:1.85">
                {"<br><br>".join(forecast_parts)}
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════
    # SECTION 5 — NETWORK CONTEXT
    # ══════════════════════════════════════════
    st.markdown('<div class="section-header">Network Context — Key Findings Across All Stations</div>', unsafe_allow_html=True)

    findings = [
        (
            "Two Constraint Regimes",
            "The 15 stations split cleanly into two groups. Seven stations (ANEW1, DRYW1, GRFW1, HIBW1, "
            "KOSW1, LBFO3, PEFW1) are primarily limited by RH being too wet — humidity is the binding "
            "constraint, and wind dispersal is usually met when RH cooperates. The other eight stations "
            "(CGFO3, CMFW1, EVFO3, MILW1, TPEO3, TT246, VPFW1, WSRO3) are primarily limited by wind "
            "being too calm — the 5 mph smoke dispersal floor is frequently not met, often due to terrain "
            "sheltering. Understanding which regime a station falls into helps set expectations: "
            "RH-constrained stations benefit most from dry-spell forecasts; wind-constrained stations "
            "need synoptic wind events to open windows."
        ),
        (
            "Temperature Is Not the Limiting Factor in the PNW",
            "Across all 15 stations and one full year of data, temperature (exceeding 90°F) accounts for "
            "a negligible share of window failures — the highest recorded was 376 temperature-fail hours "
            "at WSRO3 over the full year. In practice, PNW prescribed fire programs are not temperature-"
            "limited; they are moisture- and smoke-dispersal-limited. This means the 90°F ceiling in the "
            "USFS threshold criteria, while appropriate nationally, rarely affects burn planning in this "
            "region. The dashboard retains it for completeness and consistency with standard criteria."
        ),
        (
            "LBFO3 (Lava Butte, OR) — Best Year-Round Station",
            "Lava Butte has the most even seasonal distribution of any station in the network — viable "
            "windows occur in every month, including winter. Its high-elevation exposure means it "
            "regularly meets the wind dispersal threshold, and its semi-arid climate keeps RH in range "
            "more consistently than west-side stations. For planning purposes, it offers the most "
            "scheduling flexibility of any station in the network."
        ),
        (
            "EVFO3 (Evans Creek, OR) — Operationally Non-Viable Under Standard Thresholds",
            "Evans Creek averages approximately 5 viable days per year — the lowest in the network. "
            "The station logs over 8,600 calm-hour failures annually, driven by its valley location and "
            "persistent low-wind conditions. Under the standard 5 mph smoke dispersal floor, this station "
            "rarely qualifies for burn operations. Coordinators planning burns in the Evans Creek drainage "
            "may need to work with modified threshold criteria or wait for infrequent synoptic wind events."
        ),
    ]

    for title, body in findings:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
                      color:#E8A24A;margin-bottom:8px">{title}</div>
          <div style="font-size:13px;color:#C8D8C8;line-height:1.75">{body}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════
    # SECTION 6 — DATA NOTES
    # ══════════════════════════════════════════
    st.markdown('<div class="section-header">Data Notes and Limitations</div>', unsafe_allow_html=True)

    notes = [
        ("RAWS Observation Period",
         "Historical data covers approximately April 2025 through April 2026 — one year of hourly "
         "observations. Climatological baselines derived from a single year should be interpreted "
         "with caution; multi-year averages would produce more stable seasonal patterns. The current "
         "baselines are sufficient for relative comparisons across stations but may not capture "
         "interannual variability."),
        ("NDFD Forecast Temperature",
         "NOAA NDFD does not serve temperature forecasts for the PNW gridpoint product used here. "
         "A fill value of 50°F is applied to all forecast hours, which passes the < 90°F threshold. "
         "This is consistent with PNW climatology (temperature rarely constrains windows) and is "
         "documented as a design decision. Forecast window assessments are effectively based on "
         "RH and wind only."),
        ("Forecast Anomaly Classification",
         "Anomaly labels (above-normal / near-normal / below-normal) compare forecast viable hours "
         "against the same-month climatological mean. The threshold is ±1.5 hours from the monthly "
         "mean — days within that band are classified as near-normal. This is a relative measure; "
         "a day labeled above-normal at a wind-constrained station may still have fewer viable hours "
         "than a near-normal day at an RH-constrained station."),
        ("Station Coverage",
         "The 15 stations represent a sample of available PNW RAWS sites, chosen to span the "
         "Washington and Oregon Cascades and eastern slopes. Gaps exist — particularly in the "
         "Olympic Peninsula and far northeast Washington. Coordinators planning burns outside "
         "the coverage area should treat the nearest station as an approximate reference only."),
    ]

    col1, col2 = st.columns(2)
    for i, (title, body) in enumerate(notes):
        col = col1 if i % 2 == 0 else col2
        with col:
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:12px">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
                          color:#7A9180;margin-bottom:6px;letter-spacing:0.06em">{title.upper()}</div>
              <div style="font-size:12px;color:#8A9BA8;line-height:1.7">{body}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    data = load_all()

    selected_station, filtered_stations = render_sidebar(data)

    # Header
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.markdown("""
        <div style="padding-bottom:16px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:24px;font-weight:600;
                      color:#E8A24A;letter-spacing:-0.01em">
            Fire Weather Windows
          </div>
          <div style="font-size:13px;color:#7A9180;margin-top:2px">
            Prescribed Burn Planning · Pacific Northwest · USDA Forest Service
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_status:
        n_stations = len(filtered_stations)
        has_forecast = data["forecast"] is not None
        has_history  = data["daily"] is not None
        st.markdown(f"""
        <div class="metric-card" style="text-align:right">
          <div class="label">Data Status</div>
          <div style="font-size:12px;color:#7A9180;margin-top:4px">
            {"✓" if has_history  else "✗"} Historical RAWS<br>
            {"✓" if has_forecast else "✗"} NDFD Forecast<br>
            {n_stations} stations loaded
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋  Briefing",
        "📍  Station Map",
        "📅  7-Day Forecast",
        "📊  Historical Record",
        "🌲  Climatology",
    ])

    with tab1:
        render_briefing_tab(data, selected_station, filtered_stations)

    with tab2:
        render_map_tab(data, filtered_stations)

    with tab3:
        render_forecast_tab(data, selected_station)

    with tab4:
        render_calendar_tab(data, selected_station)

    with tab5:
        render_climo_tab(data, filtered_stations)


if __name__ == "__main__":
    main()