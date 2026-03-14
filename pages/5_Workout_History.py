"""
Workout History — browse past workouts and explore per-activity detail.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from db import get_connection
from session import current_user_id
from options import sport_icon, sport_display
from analytics.running_economy import get_workout_gap, get_aerobic_decoupling

st.set_page_config(page_title="Workout History", page_icon="📋", layout="wide")
st.title("📋 Workout History")

USER_ID = current_user_id()

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#fafafa",
    margin=dict(l=40, r=20, t=40, b=40),
)

ZONE_COLORS = ["#74b9ff", "#55efc4", "#fdcb6e", "#e17055", "#d63031"]
ZONE_LABELS = ["Z1 Recovery", "Z2 Aerobic", "Z3 Tempo", "Z4 Threshold", "Z5 VO2max"]


def pace_str(pace_min_km):
    if pace_min_km is None or pace_min_km <= 0:
        return "—"
    mins = int(pace_min_km)
    secs = int((pace_min_km - mins) * 60)
    return f"{mins}:{secs:02d} /km"


def duration_str(seconds):
    if not seconds:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_workout_list(user_id, sport_filter, days):
    conn = get_connection()
    cur  = conn.cursor()

    sport_clause = "AND sport = %s" if sport_filter != "All" else ""
    params = [user_id]
    if sport_filter != "All":
        params.append(sport_filter)
    params.append(days)

    cur.execute(f"""
        SELECT
            workout_id, workout_date, sport, workout_type,
            EXTRACT(EPOCH FROM (end_time - start_time))::float AS duration_s,
            training_volume::float,
            avg_heart_rate::float, max_heart_rate::float,
            calories_burned::float,
            elevation_gain::float, elevation_loss::float,
            aerobic_training_effect::float, anaerobic_training_effect::float,
            vo2max_estimate::float, training_stress_score::float,
            location
        FROM workouts
        WHERE user_id = %s
          {sport_clause}
          AND workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY workout_date DESC, start_time DESC
    """, params)

    cols = [
        "workout_id", "workout_date", "sport", "workout_type",
        "duration_s", "training_volume", "avg_hr", "max_hr",
        "calories", "elev_gain", "elev_loss",
        "aerobic_te", "anaerobic_te", "vo2max", "tss", "location",
    ]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


@st.cache_data(ttl=300)
def load_strength_session(user_id, workout_date):
    """Return exercises + sets for a strength session on the given date."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT ss.session_id, ss.session_type,
               se.exercise_id, se.exercise_order, se.name, se.notes
        FROM strength_sessions ss
        JOIN strength_exercises se ON se.session_id = ss.session_id
        WHERE ss.user_id = %s AND ss.session_date = %s
        ORDER BY se.exercise_order
    """, (user_id, workout_date,))
    ex_rows = cur.fetchall()
    if not ex_rows:
        cur.close()
        conn.close()
        return None

    session_type = ex_rows[0][1]
    exercises = {}
    for row in ex_rows:
        eid = row[2]
        if eid not in exercises:
            exercises[eid] = {"order": row[3], "name": row[4], "notes": row[5], "sets": []}

    exercise_ids = list(exercises.keys())
    cur.execute("""
        SELECT exercise_id, set_number, reps, duration_seconds,
               total_weight_kg, is_bodyweight, band_color, per_hand, per_side
        FROM strength_sets
        WHERE exercise_id = ANY(%s)
        ORDER BY exercise_id, set_number
    """, (exercise_ids,))
    for s in cur.fetchall():
        eid = s[0]
        exercises[eid]["sets"].append({
            "set_number":       s[1],
            "reps":             s[2],
            "duration_seconds": s[3],
            "total_weight_kg":  s[4],
            "is_bodyweight":    s[5],
            "band_color":       s[6],
            "per_hand":         s[7],
            "per_side":         s[8],
        })

    cur.close()
    conn.close()
    return {"session_type": session_type,
            "exercises": sorted(exercises.values(), key=lambda e: e["order"])}


@st.cache_data(ttl=300)
def load_workout_detail(workout_id):
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            workout_id, workout_date, sport, workout_type,
            start_time, end_time,
            EXTRACT(EPOCH FROM (end_time - start_time))::float AS duration_s,
            training_volume::float, avg_heart_rate::float, max_heart_rate::float,
            calories_burned::float, vo2max_estimate::float, lactate_threshold_bpm::float,
            time_in_hr_zone_1::float, time_in_hr_zone_2::float, time_in_hr_zone_3::float,
            time_in_hr_zone_4::float, time_in_hr_zone_5::float,
            elevation_gain::float, elevation_loss::float,
            aerobic_training_effect::float, anaerobic_training_effect::float,
            training_stress_score::float, normalized_power::float,
            avg_power::float, max_power::float,
            avg_running_cadence::float, max_running_cadence::float,
            avg_ground_contact_time::float, avg_vertical_oscillation::float,
            avg_stride_length::float, avg_vertical_ratio::float,
            total_steps, location,
            start_latitude::float, start_longitude::float
        FROM workouts WHERE workout_id = %s
    """, (workout_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None, None

    cols = [
        "workout_id", "workout_date", "sport", "workout_type",
        "start_time", "end_time", "duration_s",
        "distance_m", "avg_hr", "max_hr",
        "calories", "vo2max", "lactate_threshold",
        "z1", "z2", "z3", "z4", "z5",
        "elev_gain", "elev_loss",
        "aerobic_te", "anaerobic_te",
        "tss", "norm_power", "avg_power", "max_power",
        "avg_cadence", "max_cadence",
        "avg_gct", "avg_vo", "avg_stride", "avg_vr",
        "total_steps", "location",
        "lat", "lon",
    ]
    detail = dict(zip(cols, row))

    # Time-series metrics
    cur.execute("""
        SELECT metric_timestamp, heart_rate, pace, cadence,
               altitude, gradient_pct, power,
               ground_contact_time, vertical_oscillation, distance,
               latitude, longitude
        FROM workout_metrics
        WHERE workout_id = %s
        ORDER BY metric_timestamp
    """, (workout_id,))
    ts_cols = ["ts", "hr", "pace", "cadence", "altitude", "gradient",
               "power", "gct", "vo", "distance", "lat", "lon"]
    ts = [dict(zip(ts_cols, r)) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return detail, ts


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_sport_options(user_id):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT DISTINCT sport FROM workouts WHERE user_id = %s ORDER BY sport", (user_id,))
    sports = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ["All"] + sports


f1, f2, f3 = st.columns([2, 2, 1])

sport_options = load_sport_options(USER_ID)
sport_filter = f1.selectbox(
    "Sport", sport_options,
    format_func=lambda s: (
        "All sports" if s == "All"
        else sport_display(s)
    ),
)

days_options = {90: "Last 3 months", 180: "Last 6 months", 365: "Last year", 730: "Last 2 years"}
days = f2.selectbox("Period", list(days_options.keys()), format_func=lambda d: days_options[d], index=2)

if f3.button("🔄 Refresh"):
    load_workout_list.clear()
    load_workout_detail.clear()
    st.toast("Refreshed", icon="✅")

workouts = load_workout_list(USER_ID, sport_filter, days)

if not workouts:
    st.info("No workouts found for the selected filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Workout list
# ---------------------------------------------------------------------------

col_list, col_detail = st.columns([1, 2])

with col_list:
    st.markdown(f"**{len(workouts)} workouts**")

    if "selected_workout_id" not in st.session_state:
        st.session_state.selected_workout_id = workouts[0]["workout_id"]

    for w in workouts:
        icon    = sport_icon(w["sport"])
        dist_km = f"{w['training_volume'] / 1000:.1f} km" if w["training_volume"] else ""
        dur     = duration_str(w["duration_s"])
        elev    = f" ↑{w['elev_gain']:.0f}m" if w["elev_gain"] else ""
        label   = f"{icon} **{w['workout_date'].strftime('%d %b %Y')}**  \n{w['sport'].replace('_', ' ').title()} · {dist_km} · {dur}{elev}"

        is_selected = st.session_state.selected_workout_id == w["workout_id"]
        if st.button(label, key=f"w_{w['workout_id']}",
                     use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.selected_workout_id = w["workout_id"]
            load_workout_detail.clear()
            st.rerun()

# ---------------------------------------------------------------------------
# Workout detail
# ---------------------------------------------------------------------------

with col_detail:
    wid = st.session_state.selected_workout_id
    detail, ts = load_workout_detail(wid)

    if not detail:
        st.warning("Could not load workout detail.")
        st.stop()

    icon = sport_icon(detail["sport"])
    st.markdown(f"## {icon} {detail['workout_type'] or detail['sport'].replace('_', ' ').title()}")
    st.caption(
        f"{detail['workout_date'].strftime('%A, %d %B %Y')}  ·  "
        f"{detail['start_time'].strftime('%H:%M') if detail['start_time'] else ''}  ·  "
        f"{detail.get('location') or ''}"
    )

    # ── Key metrics ──────────────────────────────────────────────────────────
    dist_km  = (detail["distance_m"] or 0) / 1000
    avg_pace = None
    if dist_km > 0 and detail["duration_s"]:
        avg_pace = (detail["duration_s"] / 60) / dist_km   # min/km

    # Row 1 — always shown (core stats every sport has)
    r1_metrics = []
    if dist_km:
        r1_metrics.append(("Distance",  f"{dist_km:.2f} km"))
    r1_metrics.append(("Duration",  duration_str(detail["duration_s"])))
    if detail["avg_hr"]:
        r1_metrics.append(("Avg HR",   f"{int(detail['avg_hr'])} bpm"))
    if avg_pace:
        r1_metrics.append(("Avg Pace", pace_str(avg_pace)))
    if detail["calories"]:
        r1_metrics.append(("Calories", f"{int(detail['calories'])} kcal"))

    cols = st.columns(len(r1_metrics))
    for col, (label, value) in zip(cols, r1_metrics):
        col.metric(label, value)

    # Row 2 — secondary stats (only render non-null values)
    r2_metrics = []
    if detail["elev_gain"]:
        r2_metrics.append(("Elev Gain",  f"{detail['elev_gain']:.0f} m"))
    if detail["elev_loss"]:
        r2_metrics.append(("Elev Loss",  f"{detail['elev_loss']:.0f} m"))
    if detail["aerobic_te"]:
        r2_metrics.append(("Aerobic TE", f"{detail['aerobic_te']:.1f}"))
    if detail["anaerobic_te"]:
        r2_metrics.append(("Anaerobic TE", f"{detail['anaerobic_te']:.1f}"))
    if detail["vo2max"]:
        r2_metrics.append(("VO2max Est", f"{detail['vo2max']:.1f}"))
    if detail["tss"]:
        r2_metrics.append(("TSS",        f"{detail['tss']:.0f}"))

    if r2_metrics:
        cols2 = st.columns(len(r2_metrics))
        for col, (label, value) in zip(cols2, r2_metrics):
            col.metric(label, value)

    # Row 3 — running biomechanics (only if any data present)
    if detail["sport"] in ("running", "trail_running"):
        r3_metrics = []
        if detail["avg_cadence"]:
            r3_metrics.append(("Avg Cadence", f"{detail['avg_cadence']:.0f} spm"))
        if detail["avg_gct"]:
            r3_metrics.append(("Avg GCT",     f"{detail['avg_gct']:.0f} ms"))
        if detail["avg_stride"]:
            r3_metrics.append(("Avg Stride",  f"{detail['avg_stride']:.2f} m"))
        if detail["avg_vo"]:
            r3_metrics.append(("Vert Osc",    f"{detail['avg_vo']:.1f} cm"))
        if detail["total_steps"]:
            r3_metrics.append(("Total Steps", f"{int(detail['total_steps']):,}"))
        if r3_metrics:
            cols3 = st.columns(len(r3_metrics))
            for col, (label, value) in zip(cols3, r3_metrics):
                col.metric(label, value)

    # Row 4 — cycling power (only if power data present)
    if detail["avg_power"]:
        r4_metrics = [("Avg Power", f"{detail['avg_power']:.0f} W")]
        if detail["max_power"]:
            r4_metrics.append(("Max Power",  f"{detail['max_power']:.0f} W"))
        if detail["norm_power"]:
            r4_metrics.append(("Norm Power", f"{detail['norm_power']:.0f} W"))
        cols4 = st.columns(len(r4_metrics))
        for col, (label, value) in zip(cols4, r4_metrics):
            col.metric(label, value)

    st.divider()

    # ── HR Zone breakdown ─────────────────────────────────────────────────────
    zone_seconds = [detail["z1"], detail["z2"], detail["z3"], detail["z4"], detail["z5"]]
    zone_seconds = [float(z or 0) for z in zone_seconds]
    total_zone_s = sum(zone_seconds)

    if total_zone_s > 0:
        st.markdown("**Heart Rate Zones**")
        fig_zones = go.Figure()
        for i, (z_s, label, color) in enumerate(zip(zone_seconds, ZONE_LABELS, ZONE_COLORS)):
            pct = z_s / total_zone_s * 100
            fig_zones.add_trace(go.Bar(
                x=[z_s / 60], y=["Zones"], orientation="h",
                name=label,
                marker_color=color,
                text=f"{label}  {pct:.0f}%  ({duration_str(z_s)})",
                textposition="inside" if z_s / total_zone_s > 0.08 else "none",
                hovertemplate=f"{label}: {duration_str(z_s)} ({pct:.1f}%)<extra></extra>",
            ))
        fig_zones.update_layout(
            barmode="stack", height=80,
            showlegend=False,
            xaxis=dict(title="minutes", gridcolor="#2a2a2a"),
            yaxis=dict(showticklabels=False),
            **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            margin=dict(l=10, r=10, t=10, b=30),
        )
        st.plotly_chart(fig_zones, width="stretch")

    # ── Time-series charts ────────────────────────────────────────────────────
    if ts:
        timestamps = [r["ts"] for r in ts]
        has_hr      = any(r["hr"]       for r in ts)
        has_pace    = any(r["pace"]      for r in ts)
        has_alt     = any(r["altitude"]  for r in ts)
        has_cadence = any(r["cadence"]   for r in ts)
        has_power   = any(r["power"]     for r in ts)
        has_gct     = any(r["gct"]       for r in ts)
        has_gps     = any(r["lat"]       for r in ts)

        # ── HR + Pace/Power dual-axis chart ──────────────────────────────────
        if has_hr or has_pace or has_power:
            fig_main = make_subplots(specs=[[{"secondary_y": True}]])

            if has_hr:
                fig_main.add_trace(go.Scatter(
                    x=timestamps, y=[r["hr"] for r in ts],
                    name="HR (bpm)", line=dict(color="#ff6b6b", width=1.5),
                    hovertemplate="HR: %{y} bpm<extra></extra>",
                ), secondary_y=False)

            if has_power:
                fig_main.add_trace(go.Scatter(
                    x=timestamps, y=[r["power"] for r in ts],
                    name="Power (W)", line=dict(color="#ff9933", width=1),
                    opacity=0.8,
                    hovertemplate="Power: %{y} W<extra></extra>",
                ), secondary_y=True)
            elif has_pace:
                pace_vals = [r["pace"] if r["pace"] and 0 < r["pace"] < 20 else None for r in ts]
                fig_main.add_trace(go.Scatter(
                    x=timestamps, y=pace_vals,
                    name="Pace (min/km)", line=dict(color="#4da6ff", width=1.5),
                    hovertemplate="Pace: %{y:.2f} min/km<extra></extra>",
                    connectgaps=False,
                ), secondary_y=True)

            fig_main.update_layout(
                height=220, legend=dict(orientation="h", y=1.1),
                xaxis=dict(gridcolor="#2a2a2a"),
                yaxis=dict(title="HR (bpm)", gridcolor="#2a2a2a"),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            )
            if has_power:
                fig_main.update_yaxes(title_text="Power (W)", secondary_y=True)
            elif has_pace:
                fig_main.update_yaxes(title_text="Pace (min/km)", autorange="reversed", secondary_y=True)

            st.plotly_chart(fig_main, width="stretch")

        # ── Altitude + Gradient ───────────────────────────────────────────────
        if has_alt:
            alt_vals  = [r["altitude"]  for r in ts]
            grad_vals = [r["gradient"]  for r in ts]

            fig_alt = make_subplots(specs=[[{"secondary_y": True}]])
            fig_alt.add_trace(go.Scatter(
                x=timestamps, y=alt_vals,
                name="Altitude (m)", fill="tozeroy",
                fillcolor="rgba(0,200,130,0.15)",
                line=dict(color="#00cc7a", width=1.5),
                hovertemplate="Alt: %{y:.0f} m<extra></extra>",
            ), secondary_y=False)

            if any(g for g in grad_vals if g is not None):
                fig_alt.add_trace(go.Scatter(
                    x=timestamps, y=grad_vals,
                    name="Gradient (%)", line=dict(color="#fdcb6e", width=1),
                    opacity=0.7,
                    hovertemplate="Gradient: %{y:.1f}%<extra></extra>",
                ), secondary_y=True)

            fig_alt.update_layout(
                height=180, legend=dict(orientation="h", y=1.1),
                xaxis=dict(gridcolor="#2a2a2a"),
                yaxis=dict(title="Altitude (m)", gridcolor="#2a2a2a"),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            )
            fig_alt.update_yaxes(title_text="Gradient (%)", secondary_y=True)
            st.plotly_chart(fig_alt, width="stretch")

        # ── Biomechanics (cadence + GCT) ──────────────────────────────────────
        if has_cadence or has_gct:
            fig_bio = make_subplots(specs=[[{"secondary_y": True}]])

            if has_cadence:
                fig_bio.add_trace(go.Scatter(
                    x=timestamps,
                    y=[r["cadence"] if r["cadence"] and r["cadence"] > 0 else None for r in ts],
                    name="Cadence (spm)", line=dict(color="#a29bfe", width=1.5),
                    hovertemplate="Cadence: %{y:.0f} spm<extra></extra>",
                    connectgaps=False,
                ), secondary_y=False)

            if has_gct:
                fig_bio.add_trace(go.Scatter(
                    x=timestamps,
                    y=[r["gct"] if r["gct"] and r["gct"] > 0 else None for r in ts],
                    name="GCT (ms)", line=dict(color="#fd79a8", width=1.5),
                    hovertemplate="GCT: %{y:.0f} ms<extra></extra>",
                    connectgaps=False,
                ), secondary_y=True)

            fig_bio.update_layout(
                height=180, legend=dict(orientation="h", y=1.1),
                xaxis=dict(gridcolor="#2a2a2a"),
                yaxis=dict(title="Cadence (spm)", gridcolor="#2a2a2a"),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            )
            fig_bio.update_yaxes(title_text="GCT (ms)", secondary_y=True)
            st.plotly_chart(fig_bio, width="stretch")

        # ── GPS map ───────────────────────────────────────────────────────────
        if has_gps:
            gps_pts = [(r["lat"], r["lon"]) for r in ts if r["lat"] and r["lon"]]
            if len(gps_pts) > 10:
                st.markdown("**Route**")
                map_df_data = {"lat": [p[0] for p in gps_pts],
                               "lon": [p[1] for p in gps_pts]}
                import pandas as pd
                st.map(pd.DataFrame(map_df_data), zoom=13)

    # ── Strength session exercises ────────────────────────────────────────────
    if detail["sport"] == "strength_training":
        st.divider()
        st.markdown("**Exercises Performed**")

        strength = load_strength_session(USER_ID, detail["workout_date"])
        if strength:
            st.caption(f"Session type: {strength['session_type'].capitalize()}")
            for ex in strength["exercises"]:
                sets = ex["sets"]
                mods = []
                if sets and sets[0].get("per_hand"): mods.append("per hand")
                if sets and sets[0].get("per_side"): mods.append("per side")
                mod_str = f"  _{', '.join(mods)}_" if mods else ""
                note_str = f" — _{ex['notes']}_" if ex["notes"] else ""

                # Summarise sets into a compact string
                set_strs = []
                for s in sets:
                    if s.get("is_bodyweight"):
                        w = "BW"
                    elif s.get("band_color"):
                        w = f"band({s['band_color']})"
                    elif s.get("total_weight_kg") is not None:
                        w = f"{s['total_weight_kg']:.1f} kg"
                    else:
                        w = "—"
                    r = f"{s['duration_seconds']}s" if s.get("duration_seconds") else str(s.get("reps") or "?")
                    set_strs.append(f"{r} @ {w}")

                # Collapse identical sets
                if len(set(set_strs)) == 1:
                    summary = f"{len(sets)} × {set_strs[0]}"
                else:
                    summary = "  /  ".join(f"S{i+1}: {v}" for i, v in enumerate(set_strs))

                st.markdown(f"**{ex['order']}. {ex['name']}**{note_str}{mod_str}  \n{summary}")
        else:
            st.info("No strength session recorded for this date.")

    # ── Running-specific analytics ────────────────────────────────────────────
    if detail["sport"] in ("running", "trail_running") and ts:
        st.divider()
        st.markdown("**Running Analytics**")

        conn = get_connection()
        gap    = get_workout_gap(wid, conn)
        decoup = get_aerobic_decoupling(wid, conn)
        conn.close()

        ac1, ac2, ac3 = st.columns(3)

        if gap:
            ac1.metric("Avg Pace",       pace_str(gap["avg_pace"]))
            ac2.metric("Grade-Adj Pace", pace_str(gap["avg_gap"]))
            ac3.metric("Terrain Cost",
                       f"+{gap['gap_vs_pace_pct']:.1f}%" if gap["gap_vs_pace_pct"] >= 0
                       else f"{gap['gap_vs_pace_pct']:.1f}%",
                       help="How much harder the terrain made this run vs flat equivalent")

        if decoup:
            d1, d2, d3 = st.columns(3)
            color = "normal" if decoup["decoupling_pct"] < 5 else "inverse"
            d1.metric("Aerobic Decoupling", f"{decoup['decoupling_pct']:.1f}%",
                      help="Pa:HR drift first half vs second half. <5% = efficient aerobic base.")
            status_map = {"efficient": "✅ Efficient", "moderate_drift": "⚠️ Moderate drift",
                          "cardiac_drift": "❌ Cardiac drift"}
            d2.metric("Status", status_map.get(decoup["status"], decoup["status"]))
            d3.metric("Data points", f"{decoup['rows_used']:,}")
