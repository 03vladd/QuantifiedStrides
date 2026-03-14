"""
Analytics — training load history, HRV trend, sleep quality, 1RM progression.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta

from db import get_connection
from training_load import get_history, get_hrv_history
from session import current_user_id

st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")
st.title("📈 Analytics")

USER_ID = current_user_id()

today = date.today()

# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_training_history(today_iso, days):
    conn = get_connection()
    cur  = conn.cursor()
    history = get_history(cur, date.fromisoformat(today_iso), days=days)
    cur.close()
    conn.close()
    return history


@st.cache_data(ttl=300)
def load_hrv_history(today_iso, days):
    conn = get_connection()
    cur  = conn.cursor()
    history = get_hrv_history(cur, date.fromisoformat(today_iso), days=days)
    cur.close()
    conn.close()
    return history


@st.cache_data(ttl=300)
def load_sleep_history(today_iso, days):
    start = date.fromisoformat(today_iso) - timedelta(days=days)
    conn  = get_connection()
    cur   = conn.cursor()
    cur.execute("""
        SELECT sleep_date, duration_minutes, sleep_score, overnight_hrv, rhr
        FROM sleep_sessions
        WHERE user_id = %s AND sleep_date BETWEEN %s AND %s
        ORDER BY sleep_date
    """, (USER_ID, start, date.fromisoformat(today_iso)))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@st.cache_data(ttl=300)
def load_1rm_history(today_iso, exercise_name, days):
    start = date.fromisoformat(today_iso) - timedelta(days=days)
    conn  = get_connection()
    cur   = conn.cursor()
    # Epley: 1RM = w × (1 + reps/30)
    cur.execute("""
        SELECT ss.session_date,
               MAX(st.total_weight_kg * (1 + st.reps / 30.0)) AS epley_1rm
        FROM strength_sessions ss
        JOIN strength_exercises se ON se.session_id = ss.session_id
        JOIN strength_sets st ON st.exercise_id = se.exercise_id
        WHERE ss.user_id = %s
          AND se.name = %s
          AND ss.session_date BETWEEN %s AND %s
          AND st.total_weight_kg IS NOT NULL
          AND st.reps IS NOT NULL
          AND st.reps > 0
          AND st.reps <= 10
        GROUP BY ss.session_date
        ORDER BY ss.session_date
    """, (USER_ID, exercise_name, start, date.fromisoformat(today_iso)))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@st.cache_data(ttl=3600)
def load_tracked_exercises():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT se.name
        FROM strength_exercises se
        JOIN strength_sets st ON st.exercise_id = se.exercise_id
        WHERE st.total_weight_kg IS NOT NULL AND st.reps IS NOT NULL AND st.reps BETWEEN 1 AND 10
        ORDER BY se.name
    """)
    names = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return names


# ---------------------------------------------------------------------------
# Shared layout helpers
# ---------------------------------------------------------------------------

DARK_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="#FAFAFA",
    margin=dict(l=10, r=10, t=30, b=30),
)


# ---------------------------------------------------------------------------
# Section 1 — Training Load (CTL / ATL / TSB)
# ---------------------------------------------------------------------------

tl_col, tl_btn = st.columns([6, 1])
tl_col.subheader("Training Load History")
if tl_btn.button("🔄", key="ref_tl", help="Refresh training load"):
    load_training_history.clear()
    st.toast("Training load refreshed", icon="✅")

days_tl = st.select_slider("Lookback", options=[30, 60, 90], value=60, key="tl_days")
history  = load_training_history(today.isoformat(), days_tl)

if history:
    dates = [h["date"] for h in history]
    ctl   = [h["ctl"]  for h in history]
    atl   = [h["atl"]  for h in history]
    tsb   = [h["tsb"]  for h in history]
    load  = [h["load"] for h in history]

    fig_tl = go.Figure()
    fig_tl.add_trace(go.Scatter(x=dates, y=ctl, name="CTL (Fitness)",
                                line=dict(color="#00C851", width=2)))
    fig_tl.add_trace(go.Scatter(x=dates, y=atl, name="ATL (Fatigue)",
                                line=dict(color="#FF4B4B", width=2)))
    fig_tl.add_trace(go.Scatter(x=dates, y=tsb, name="TSB (Form)",
                                line=dict(color="#FFA500", width=2),
                                fill="tozeroy",
                                fillcolor="rgba(255,165,0,0.08)"))
    fig_tl.add_trace(go.Bar(x=dates, y=load, name="Daily Load",
                            marker_color="rgba(100,149,237,0.4)",
                            yaxis="y2"))
    # TSB zone bands
    fig_tl.add_hrect(y0=5, y1=100, fillcolor="rgba(0,200,81,0.05)",
                     line_width=0, annotation_text="Fresh", annotation_position="top right")
    fig_tl.add_hrect(y0=-15, y1=-0.01, fillcolor="rgba(255,165,0,0.05)",
                     line_width=0, annotation_text="Productive fatigue")
    fig_tl.add_hrect(y0=-100, y1=-15, fillcolor="rgba(255,75,75,0.07)",
                     line_width=0, annotation_text="Overreached")

    fig_tl.update_layout(
        **DARK_LAYOUT,
        height=350,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="Load / Form"),
        yaxis2=dict(title="Daily TRIMP", overlaying="y", side="right",
                    showgrid=False),
        hovermode="x unified",
    )
    st.plotly_chart(fig_tl, width="stretch")
else:
    st.info("Not enough training data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — HRV Trend
# ---------------------------------------------------------------------------

hrv_col, hrv_btn = st.columns([6, 1])
hrv_col.subheader("HRV Trend")
if hrv_btn.button("🔄", key="ref_hrv", help="Refresh HRV data"):
    load_hrv_history.clear()
    st.toast("HRV data refreshed", icon="✅")

days_hrv = st.select_slider("Lookback", options=[14, 30, 60], value=30, key="hrv_days")
hrv_hist  = load_hrv_history(today.isoformat(), days_hrv)

if hrv_hist:
    h_dates    = [h["date"]     for h in hrv_hist]
    h_hrv      = [h["hrv"]      for h in hrv_hist]
    h_baseline = [h["baseline"] for h in hrv_hist]
    h_rhr      = [h["rhr"]      for h in hrv_hist if h.get("rhr")]
    h_rhr_d    = [h["date"]     for h in hrv_hist if h.get("rhr")]

    fig_hrv = go.Figure()
    fig_hrv.add_trace(go.Scatter(x=h_dates, y=h_baseline, name="7-day baseline",
                                 line=dict(color="#888", dash="dash", width=1.5)))
    fig_hrv.add_trace(go.Scatter(x=h_dates, y=h_hrv, name="HRV",
                                 mode="lines+markers",
                                 line=dict(color="#00C851", width=2),
                                 marker=dict(size=5)))
    if h_rhr:
        fig_hrv.add_trace(go.Scatter(x=h_rhr_d, y=h_rhr, name="RHR",
                                     line=dict(color="#FF4B4B", width=1.5),
                                     yaxis="y2"))

    fig_hrv.update_layout(
        **DARK_LAYOUT,
        height=300,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="HRV (ms)"),
        yaxis2=dict(title="RHR (bpm)", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
    )
    st.plotly_chart(fig_hrv, width="stretch")
else:
    st.info("No HRV data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Sleep Quality
# ---------------------------------------------------------------------------

sl_col, sl_btn = st.columns([6, 1])
sl_col.subheader("Sleep")
if sl_btn.button("🔄", key="ref_sleep", help="Refresh sleep data"):
    load_sleep_history.clear()
    st.toast("Sleep data refreshed", icon="✅")

days_sleep  = st.select_slider("Lookback", options=[14, 30, 60, 90], value=30, key="sleep_days")
sleep_rows  = load_sleep_history(today.isoformat(), days_sleep)

if sleep_rows:
    s_dates    = [r[0] for r in sleep_rows]
    s_duration = [round(r[1] / 60, 1) if r[1] else None for r in sleep_rows]
    s_score    = [r[2] for r in sleep_rows]

    fig_sleep = go.Figure()
    fig_sleep.add_trace(go.Bar(x=s_dates, y=s_duration, name="Duration (h)",
                               marker_color="rgba(100,149,237,0.6)"))
    fig_sleep.add_trace(go.Scatter(x=s_dates, y=s_score, name="Sleep Score",
                                   line=dict(color="#FFA500", width=2),
                                   yaxis="y2"))
    # Reference lines
    fig_sleep.add_hline(y=7.5, line_dash="dot", line_color="#00C851",
                        annotation_text="7.5h target", line_width=1,
                        annotation_position="top right")
    fig_sleep.add_hline(y=6.5, line_dash="dot", line_color="#FF4B4B",
                        annotation_text="6.5h threshold", line_width=1)

    fig_sleep.update_layout(
        **DARK_LAYOUT,
        height=300,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="Sleep duration (h)", range=[0, 12]),
        yaxis2=dict(title="Sleep score", overlaying="y", side="right",
                    showgrid=False, range=[0, 100]),
        hovermode="x unified",
    )
    st.plotly_chart(fig_sleep, use_container_width=True)
else:
    st.info("No sleep data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — 1RM Progression
# ---------------------------------------------------------------------------

rm_hdr, rm_btn = st.columns([6, 1])
rm_hdr.subheader("1RM Progression (Epley estimate)")
if rm_btn.button("🔄", key="ref_rm", help="Refresh 1RM data"):
    load_1rm_history.clear()
    load_tracked_exercises.clear()
    st.toast("1RM data refreshed", icon="✅")

tracked = load_tracked_exercises()
if tracked:
    rm_col1, rm_col2 = st.columns([2, 1])
    selected_ex = rm_col1.selectbox("Exercise", tracked)
    days_rm     = rm_col2.select_slider("Lookback", options=[30, 60, 90, 180], value=90, key="rm_days")

    rm_rows = load_1rm_history(today.isoformat(), selected_ex, days_rm)

    if rm_rows and len(rm_rows) > 1:
        rm_dates = [r[0] for r in rm_rows]
        rm_vals  = [round(float(r[1]), 1) for r in rm_rows]

        fig_rm = go.Figure()
        fig_rm.add_trace(go.Scatter(
            x=rm_dates, y=rm_vals,
            mode="lines+markers",
            line=dict(color="#00C851", width=2),
            marker=dict(size=6),
            name="Epley 1RM",
            text=[f"{v} kg" for v in rm_vals],
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        ))
        fig_rm.update_layout(
            **DARK_LAYOUT,
            height=280,
            yaxis=dict(title="Estimated 1RM (kg)"),
            hovermode="x",
        )
        st.plotly_chart(fig_rm, use_container_width=True)

        # Best and recent
        best   = max(rm_vals)
        latest = rm_vals[-1]
        m1, m2, m3 = st.columns(3)
        m1.metric("Best (period)",  f"{best} kg")
        m2.metric("Latest",         f"{latest} kg")
        m3.metric("Change",         f"{latest - rm_vals[0]:+.1f} kg",
                  delta=f"{latest - rm_vals[0]:+.1f} kg")
    elif rm_rows:
        st.info("Only one data point — need at least two sessions to show progression.")
    else:
        st.info(f"No sets recorded for **{selected_ex}** in the selected period.")
else:
    st.info("Log some weighted exercises first to see 1RM progression.")

st.divider()

# ---------------------------------------------------------------------------
# Section 5 — Weekly Training Volume
# ---------------------------------------------------------------------------

vol_hdr, vol_btn = st.columns([6, 1])
vol_hdr.subheader("Weekly Training Volume")
if vol_btn.button("🔄", key="ref_vol", help="Refresh volume data"):
    load_weekly_volume.clear()
    st.toast("Volume data refreshed", icon="✅")

@st.cache_data(ttl=300)
def load_weekly_volume(today_iso, weeks=12):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT date_trunc('week', session_date)::date AS week_start,
               COUNT(DISTINCT session_date)            AS training_days,
               SUM(num_sets)                           AS total_sets
        FROM (
            SELECT ss.session_date,
                   COUNT(st.set_id) AS num_sets
            FROM strength_sessions ss
            JOIN strength_exercises se ON se.session_id = ss.session_id
            JOIN strength_sets st ON st.exercise_id = se.exercise_id
            WHERE ss.user_id = %s
              AND ss.session_date >= %s
            GROUP BY ss.session_date
        ) sub
        GROUP BY week_start
        ORDER BY week_start
    """, (USER_ID, date.fromisoformat(today_iso) - timedelta(weeks=weeks),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

vol_rows = load_weekly_volume(today.isoformat())
if vol_rows:
    w_weeks = [r[0] for r in vol_rows]
    w_sets  = [int(r[2]) for r in vol_rows]
    w_days  = [int(r[1]) for r in vol_rows]

    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(x=w_weeks, y=w_sets, name="Total sets",
                             marker_color="rgba(100,149,237,0.65)"))
    fig_vol.add_trace(go.Scatter(x=w_weeks, y=w_days, name="Training days",
                                 line=dict(color="#FFA500", width=2),
                                 mode="lines+markers", yaxis="y2"))
    fig_vol.update_layout(
        **DARK_LAYOUT,
        height=280,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="Sets"),
        yaxis2=dict(title="Days", overlaying="y", side="right",
                    showgrid=False, range=[0, 7]),
        hovermode="x unified",
    )
    st.plotly_chart(fig_vol, use_container_width=True)
else:
    st.info("No strength session data yet.")
