"""
QuantifiedStrides — Streamlit Dashboard
Run: streamlit run app.py
"""

import subprocess
import sys
import os
import streamlit as st
from datetime import date, timedelta

import plotly.graph_objects as go

from db import get_connection
from recommend import (
    get_readiness, get_yesterdays_training, get_last_nights_sleep,
    get_latest_weather, get_recent_load, get_consecutive_training_days,
    get_gym_analysis, get_exercise_suggestions, build_recommendation,
)
from training_load import get_metrics, tsb_intensity_hint
from recovery import get_hrv_status, get_muscle_freshness
from alerts import get_alerts, interpret_metrics

st.set_page_config(
    page_title="QuantifiedStrides",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------

@st.cache_data(ttl=180)
def load_data(today_iso):
    today = date.fromisoformat(today_iso)
    yesterday = today - timedelta(days=1)
    conn = get_connection()
    cur  = conn.cursor()

    readiness    = get_readiness(cur, today)
    yday         = get_yesterdays_training(cur, yesterday)
    sleep        = get_last_nights_sleep(cur, today)
    weather      = get_latest_weather(cur)
    load         = get_recent_load(cur, today)
    consecutive  = get_consecutive_training_days(cur, today)
    gym_analysis = get_gym_analysis(cur, today)
    tl           = get_metrics(cur, today)
    hrv          = get_hrv_status(cur, today)
    alerts       = get_alerts(cur, today, tl, hrv, readiness)
    freshness    = get_muscle_freshness(cur, today)

    cur.close()
    conn.close()
    return readiness, yday, sleep, weather, load, consecutive, gym_analysis, tl, hrv, alerts, freshness


@st.cache_data(ttl=180)
def load_exercises(today_iso):
    today = date.fromisoformat(today_iso)
    conn  = get_connection()
    cur   = conn.cursor()
    readiness, yday, sleep, weather, load, consecutive, gym_analysis, tl, hrv, alerts, _ = load_data(today_iso)
    if not readiness:
        cur.close(); conn.close()
        return None, None
    rec = build_recommendation(readiness, yday, sleep, weather, load, consecutive, gym_analysis, today, tl)
    exs = get_exercise_suggestions(cur, rec.get("gym_rec"), today)
    cur.close(); conn.close()
    return rec, exs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def severity_color(sev):
    return {"critical": "#FF4B4B", "warning": "#FFA500", "info": "#1E90FF"}.get(sev, "#888")

def severity_icon(sev):
    return {"critical": "🚨", "warning": "⚡", "info": "ℹ️"}.get(sev, "")

def tsb_color(tsb):
    if tsb > 5:   return "#00C851"
    if tsb >= -15: return "#FFA500"
    return "#FF4B4B"

def freshness_color(score):
    if score >= 0.7: return "#00C851"
    if score >= 0.4: return "#FFA500"
    return "#FF4B4B"


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

today = date.today()
today_iso = today.isoformat()

title_col, sync_col, refresh_col = st.columns([5, 1, 1])
title_col.title("⚡ QuantifiedStrides")
title_col.caption(f"{today.strftime('%A, %d %B %Y')}")

if sync_col.button("⬇️ Sync", help="Pull latest data from Garmin + weather"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with st.spinner("Syncing data from Garmin…"):
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True, text=True,
            cwd=script_dir, timeout=120,
        )
    if result.returncode == 0:
        st.cache_data.clear()
        st.toast("Sync complete — data updated", icon="✅")
    else:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        last = lines[-1] if lines else "unknown error"
        st.toast(f"Sync failed: {last}", icon="❌")

if refresh_col.button("🔄 Refresh", help="Clear cache and reload all data"):
    st.cache_data.clear()
    st.toast("All data refreshed", icon="✅")

(readiness, yday, sleep, weather, load,
 consecutive, gym_analysis, tl, hrv, alerts, freshness) = load_data(today_iso)

# ── Alerts ──────────────────────────────────────────────────────────────────
critical_alerts = [a for a in alerts if a[0] == "critical"]
warning_alerts  = [a for a in alerts if a[0] == "warning"]

if critical_alerts:
    for _, msg in critical_alerts:
        st.error(f"🚨 {msg}")
if warning_alerts:
    for _, msg in warning_alerts:
        st.warning(f"⚡ {msg}")

# ── No check-in ─────────────────────────────────────────────────────────────
if not readiness:
    st.info("No morning check-in yet. Head to **Check-In** to log how you feel.")
    col1, col2, col3 = st.columns(3)
else:
    rec, exercises = load_exercises(today_iso)
    col1, col2, col3 = st.columns(3)

    # ── TODAY card ──────────────────────────────────────────────────────────
    with col1:
        st.subheader("Today")
        st.markdown(f"### {rec['primary']}")
        if rec.get("intensity"):
            st.markdown(f"**Intensity:** {rec['intensity'].capitalize()}")
        if rec.get("duration"):
            st.markdown(f"**Duration:** {rec['duration']}")
        st.caption(rec.get("why", ""))

        if rec.get("avoid"):
            st.markdown("**Avoid today:**")
            for a in rec["avoid"]:
                st.markdown(f"- {a}")

    # ── Exercise suggestions ─────────────────────────────────────────────────
    with col2:
        st.subheader("Session Plan")
        if exercises:
            for i, ex in enumerate(exercises, 1):
                dur = ex.get("duration")
                reps_str = f"{ex['sets']} × {dur}s" if dur else f"{ex['sets']} × {ex['reps']}"
                st.markdown(f"**{i}. {ex['name']}** — {reps_str} @ {ex['weight_str']}")
                if ex.get("note"):
                    st.caption(f"→ {ex['note']}")
        else:
            st.caption("No gym session today — enjoy the rest.")

    # ── Context ─────────────────────────────────────────────────────────────
    with col3:
        st.subheader("Context")
        r = readiness
        st.markdown(
            f"**Feel:** {r['overall']}/10 · legs {r['legs']}/10 · "
            f"upper {r['upper']}/10 · joints {r['joints']}/10"
        )
        if r.get("injury_note"):
            st.caption(f"🩹 {r['injury_note']}")
        st.markdown(f"**Time:** {r['time']} · going out: {'yes' if r['going_out'] else 'no'}")

        if sleep and sleep.get("duration"):
            score_str = f" · score {sleep['score']:.0f}" if sleep.get("score") else ""
            hrv_str   = ""
            if hrv["status"] != "no_data":
                dev_sign = "+" if hrv["deviation"] >= 0 else ""
                trend    = {"rising": " ↗", "falling": " ↘", "stable": ""}.get(hrv["trend"], "")
                hrv_str  = f" · HRV {hrv['last_hrv']:.0f} ({dev_sign}{hrv['deviation']:.1f}SD{trend})"
            st.markdown(f"**Sleep:** {sleep['duration']} min{score_str}{hrv_str}")
        elif sleep:
            st.caption("Sleep: Garmin still processing")

        if weather:
            rain = f" · rain {weather['rain']} mm" if weather.get("rain") and weather["rain"] > 0 else ""
            st.markdown(f"**Weather:** {weather['temp']:.1f}°C · wind {weather['wind']:.1f} m/s{rain}")

st.divider()

# ── Fitness metrics ──────────────────────────────────────────────────────────
st.subheader("Fitness Snapshot")
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("CTL (Fitness)",  f"{tl['ctl']:.0f}", help="42-day chronic training load")
m2.metric("ATL (Fatigue)",  f"{tl['atl']:.0f}", help="7-day acute training load")
m3.metric("TSB (Form)",     f"{tl['tsb']:+.0f}", delta=f"{tl['ramp_rate']:+.1f} /wk",
          help="Training Stress Balance = CTL − ATL")
if hrv["status"] != "no_data":
    dev_sign = "+" if hrv["deviation"] >= 0 else ""
    m4.metric("HRV", f"{hrv['last_hrv']:.0f} ms",
              delta=f"{dev_sign}{hrv['deviation']:.1f} SD",
              help=f"vs 7-day baseline {hrv['baseline']:.0f} ms")
else:
    m4.metric("HRV", "–")

acwr = tl["atl"] / tl["ctl"] if tl["ctl"] > 5 else None
m5.metric("ACWR", f"{acwr:.2f}" if acwr else "–",
          help="Acute:Chronic Workload Ratio — optimal 0.8–1.3")

# ── Interpretations ──────────────────────────────────────────────────────────
interpretations = interpret_metrics(tl, hrv)
if interpretations:
    with st.expander("📊 What the numbers mean", expanded=True):
        for line in interpretations:
            st.markdown(f"→ {line}")

st.divider()

# ── Muscle freshness ──────────────────────────────────────────────────────────
if freshness:
    st.subheader("Muscle Freshness")
    sorted_muscles = sorted(freshness.items(), key=lambda x: x[1])
    muscles = [m for m, _ in sorted_muscles]
    scores  = [s * 100 for _, s in sorted_muscles]
    colors  = [freshness_color(s / 100) for s in scores]

    fig = go.Figure(go.Bar(
        x=scores, y=muscles, orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}%" for s in scores],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(300, len(muscles) * 22),
        xaxis=dict(range=[0, 110], title="% fresh"),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=10, r=40, t=10, b=30),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    st.plotly_chart(fig, width="stretch")
