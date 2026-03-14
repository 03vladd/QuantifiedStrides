"""
Sleep History — browse past sleep sessions and view per-night detail.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from db import get_connection
from session import current_user_id

st.set_page_config(page_title="Sleep History", page_icon="🌙", layout="wide")
st.title("🌙 Sleep History")

USER_ID = current_user_id()

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#fafafa",
    margin=dict(l=40, r=20, t=40, b=40),
)

STAGE_COLORS = {
    "Deep":  "#4a6fa5",
    "Light": "#74b9ff",
    "REM":   "#a29bfe",
    "Awake": "#636e72",
}

HRV_STATUS_LABELS = {
    "BALANCED":       "Balanced",
    "UNBALANCED":     "Unbalanced",
    "LOW":            "Low",
    "HIGH":           "High",
    "POOR":           "Poor",
}

FEEDBACK_LABELS = {
    "POSITIVE_RECOVERING":       "Recovering well",
    "POSITIVE_TRAINING_ADAPTED": "Training adapted",
    "POSITIVE_RESTORATIVE":      "Restorative",
    "NEGATIVE_POOR_SLEEP":       "Poor sleep",
    "NEGATIVE_HIGH_ACTIVITY":    "High activity stress",
    "NEUTRAL_BALANCED":          "Balanced",
    "NEGATIVE_UNUSUAL_HR":       "Unusual HR",
    "POSITIVE_LATE_BED_TIME":    "Good sleep (late bedtime)",
}


def score_color(score):
    if score is None:
        return "#666"
    if score >= 80:
        return "#00cc7a"
    if score >= 60:
        return "#fdcb6e"
    return "#ff6b6b"


def hrv_delta_color(hrv, baseline):
    if hrv is None or baseline is None:
        return "off"
    return "normal" if hrv >= baseline else "inverse"


def fmt_duration(minutes):
    if not minutes:
        return "—"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m:02d}m"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_sleep_list(user_id, days):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            sleep_id, sleep_date,
            duration_minutes, sleep_score,
            overnight_hrv, rhr,
            body_battery_change,
            hrv_status, sleep_score_feedback
        FROM sleep_sessions
        WHERE user_id = %s
          AND sleep_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY sleep_date DESC
    """, (user_id, days,))
    cols = ["sleep_id", "sleep_date", "duration_min", "score", "hrv",
            "rhr", "battery_change", "hrv_status", "feedback"]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


@st.cache_data(ttl=300)
def load_sleep_detail(user_id, sleep_id):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            sleep_id, sleep_date,
            duration_minutes, sleep_score,
            overnight_hrv, hrv, rhr,
            time_in_deep, time_in_light, time_in_rem, time_awake,
            avg_sleep_stress,
            sleep_score_feedback, sleep_score_insight,
            hrv_status, body_battery_change
        FROM sleep_sessions
        WHERE sleep_id = %s
    """, (sleep_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None

    cols = [
        "sleep_id", "sleep_date", "duration_min", "score",
        "overnight_hrv", "hrv", "rhr",
        "deep_min", "light_min", "rem_min", "awake_min",
        "sleep_stress", "feedback", "insight",
        "hrv_status", "battery_change",
    ]
    detail = dict(zip(cols, row))

    # Rolling 7-day baseline for comparison (excluding this night)
    cur.execute("""
        SELECT
            AVG(overnight_hrv)    AS avg_hrv,
            AVG(rhr)              AS avg_rhr,
            AVG(sleep_score)      AS avg_score,
            AVG(duration_minutes) AS avg_dur
        FROM (
            SELECT overnight_hrv, rhr, sleep_score, duration_minutes
            FROM sleep_sessions
            WHERE user_id = %s
              AND sleep_date < %s
              AND sleep_date >= %s - INTERVAL '7 days'
              AND overnight_hrv IS NOT NULL
        ) sub
    """, (user_id, detail["sleep_date"], detail["sleep_date"]))
    baseline = cur.fetchone()
    detail["baseline_hrv"]   = float(baseline[0]) if baseline[0] else None
    detail["baseline_rhr"]   = float(baseline[1]) if baseline[1] else None
    detail["baseline_score"] = float(baseline[2]) if baseline[2] else None
    detail["baseline_dur"]   = float(baseline[3]) if baseline[3] else None

    cur.close()
    conn.close()
    return detail


@st.cache_data(ttl=300)
def load_sleep_trends(user_id, days):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT sleep_date, sleep_score, overnight_hrv, rhr,
               duration_minutes, body_battery_change
        FROM sleep_sessions
        WHERE user_id = %s
          AND sleep_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY sleep_date
    """, (user_id, days,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

f1, f2 = st.columns([3, 1])
days_options = {30: "Last 30 days", 60: "Last 60 days", 90: "Last 3 months", 180: "Last 6 months"}
days = f1.selectbox("Period", list(days_options.keys()),
                    format_func=lambda d: days_options[d], index=2)

if f2.button("🔄 Refresh"):
    load_sleep_list.clear()
    load_sleep_detail.clear()
    load_sleep_trends.clear()
    st.toast("Refreshed", icon="✅")

# ---------------------------------------------------------------------------
# Trend overview charts (above the list/detail split)
# ---------------------------------------------------------------------------

trend_rows = load_sleep_trends(USER_ID, days)

if trend_rows:
    t_dates  = [r[0] for r in trend_rows]
    t_score  = [r[1] for r in trend_rows]
    t_hrv    = [r[2] for r in trend_rows]
    t_rhr    = [r[3] for r in trend_rows]
    t_dur    = [r[4] for r in trend_rows]
    t_batt   = [r[5] for r in trend_rows]

    tc1, tc2 = st.columns(2)

    with tc1:
        fig_score = go.Figure()
        fig_score.add_trace(go.Bar(
            x=t_dates, y=t_score,
            name="Sleep Score",
            marker_color=[score_color(s) for s in t_score],
            hovertemplate="%{x}<br>Score: %{y}<extra></extra>",
        ))
        # 7-day rolling avg
        rolling = []
        for i in range(len(t_score)):
            window = [s for s in t_score[max(0, i-6):i+1] if s is not None]
            rolling.append(sum(window) / len(window) if window else None)
        fig_score.add_trace(go.Scatter(
            x=t_dates, y=rolling, name="7-day avg",
            line=dict(color="white", width=1.5, dash="dot"),
            hovertemplate="%{x}<br>7d avg: %{y:.0f}<extra></extra>",
        ))
        fig_score.add_hline(y=80, line_color="#00cc7a", line_dash="dash",
                            line_width=1, annotation_text="80")
        fig_score.add_hline(y=60, line_color="#fdcb6e", line_dash="dash",
                            line_width=1, annotation_text="60")
        fig_score.update_layout(
            title="Sleep Score", height=200,
            legend=dict(orientation="h", y=1.15),
            yaxis=dict(range=[0, 100], gridcolor="#2a2a2a"),
            xaxis=dict(gridcolor="#2a2a2a"),
            **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
        )
        st.plotly_chart(fig_score, width="stretch")

    with tc2:
        fig_hrv = make_subplots(specs=[[{"secondary_y": True}]])
        fig_hrv.add_trace(go.Scatter(
            x=t_dates, y=t_hrv, name="HRV (ms)",
            line=dict(color="#00cc7a", width=2),
            hovertemplate="%{x}<br>HRV: %{y} ms<extra></extra>",
        ), secondary_y=False)
        fig_hrv.add_trace(go.Scatter(
            x=t_dates, y=t_rhr, name="RHR (bpm)",
            line=dict(color="#ff6b6b", width=1.5, dash="dot"),
            hovertemplate="%{x}<br>RHR: %{y} bpm<extra></extra>",
        ), secondary_y=True)
        fig_hrv.update_layout(
            title="HRV & Resting HR", height=200,
            legend=dict(orientation="h", y=1.15),
            xaxis=dict(gridcolor="#2a2a2a"),
            yaxis=dict(title="HRV (ms)", gridcolor="#2a2a2a"),
            **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
        )
        fig_hrv.update_yaxes(title_text="RHR (bpm)", secondary_y=True)
        st.plotly_chart(fig_hrv, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# List + Detail
# ---------------------------------------------------------------------------

sleep_list = load_sleep_list(USER_ID, days)

if not sleep_list:
    st.info("No sleep data found for the selected period.")
    st.stop()

col_list, col_detail = st.columns([1, 2])

if "selected_sleep_id" not in st.session_state:
    st.session_state.selected_sleep_id = sleep_list[0]["sleep_id"]

with col_list:
    st.markdown(f"**{len(sleep_list)} nights**")

    for s in sleep_list:
        score     = s["score"]
        hrv       = s["hrv"]
        dur       = fmt_duration(s["duration_min"])
        color_dot = "🟢" if score and score >= 80 else "🟡" if score and score >= 60 else "🔴" if score else "⚪"
        feedback  = FEEDBACK_LABELS.get(s["feedback"] or "", "")
        batt      = f" ⚡{s['battery_change']:+d}" if s["battery_change"] is not None else ""

        label = (
            f"{color_dot} **{s['sleep_date'].strftime('%d %b %Y')}**  \n"
            f"Score {score or '—'} · {dur} · HRV {hrv or '—'} ms{batt}"
        )
        if feedback:
            label += f"  \n_{feedback}_"

        is_selected = st.session_state.selected_sleep_id == s["sleep_id"]
        if st.button(label, key=f"s_{s['sleep_id']}",
                     use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.selected_sleep_id = s["sleep_id"]
            load_sleep_detail.clear()
            st.rerun()

with col_detail:
    sid    = st.session_state.selected_sleep_id
    detail = load_sleep_detail(USER_ID, sid)

    if not detail:
        st.warning("Could not load sleep detail.")
        st.stop()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"## 🌙 {detail['sleep_date'].strftime('%A, %d %B %Y')}")

    feedback_text = FEEDBACK_LABELS.get(detail["feedback"] or "", "")
    insight_text  = FEEDBACK_LABELS.get(detail["insight"]  or "", "")
    if feedback_text:
        st.caption(feedback_text + (f"  ·  {insight_text}" if insight_text and insight_text != feedback_text else ""))

    # ── Key metrics ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric(
        "Sleep Score", f"{detail['score']:.0f}" if detail["score"] else "—",
        delta=f"{detail['score'] - detail['baseline_score']:.0f} vs 7d avg"
              if detail["score"] and detail["baseline_score"] else None,
    )
    m2.metric(
        "Duration", fmt_duration(detail["duration_min"]),
        delta=f"{(detail['duration_min'] or 0) - (detail['baseline_dur'] or 0):+.0f} min vs 7d avg"
              if detail["duration_min"] and detail["baseline_dur"] else None,
    )
    m3.metric(
        "HRV", f"{detail['overnight_hrv']:.0f} ms" if detail["overnight_hrv"] else "—",
        delta=f"{(detail['overnight_hrv'] or 0) - (detail['baseline_hrv'] or 0):+.1f} vs 7d avg"
              if detail["overnight_hrv"] and detail["baseline_hrv"] else None,
    )
    m4.metric(
        "Resting HR", f"{detail['rhr']} bpm" if detail["rhr"] else "—",
        delta=f"{(detail['rhr'] or 0) - (detail['baseline_rhr'] or 0):+.1f} vs 7d avg"
              if detail["rhr"] and detail["baseline_rhr"] else None,
        delta_color="inverse",
    )
    m5.metric(
        "Body Battery", f"{detail['battery_change']:+d}" if detail["battery_change"] is not None else "—",
        help="Body battery change overnight",
    )

    row2 = st.columns(3)
    row2[0].metric("HRV Status",    HRV_STATUS_LABELS.get(detail["hrv_status"] or "", detail["hrv_status"] or "—"))
    row2[1].metric("Sleep Stress",  f"{detail['sleep_stress']:.0f}" if detail["sleep_stress"] else "—")
    row2[2].metric("Raw HRV",       f"{detail['hrv']:.0f} ms" if detail["hrv"] else "—",
                   help="Garmin's raw overnight HRV reading")

    st.divider()

    # ── Sleep stages ──────────────────────────────────────────────────────────
    stages = {
        "Deep":  detail["deep_min"]  or 0,
        "REM":   detail["rem_min"]   or 0,
        "Light": detail["light_min"] or 0,
        "Awake": detail["awake_min"] or 0,
    }
    total_stage_min = sum(stages.values())

    if total_stage_min > 0:
        st.markdown("**Sleep Stages**")
        sc1, sc2 = st.columns([2, 1])

        with sc1:
            # Stacked horizontal bar
            fig_stages = go.Figure()
            for stage, minutes in stages.items():
                if minutes > 0:
                    pct = minutes / total_stage_min * 100
                    fig_stages.add_trace(go.Bar(
                        x=[minutes], y=["Stages"], orientation="h",
                        name=stage,
                        marker_color=STAGE_COLORS[stage],
                        text=f"{stage}  {fmt_duration(minutes)}  ({pct:.0f}%)",
                        textposition="inside" if minutes / total_stage_min > 0.1 else "none",
                        hovertemplate=f"{stage}: {fmt_duration(minutes)} ({pct:.1f}%)<extra></extra>",
                    ))
            fig_stages.update_layout(
                barmode="stack", height=80,
                showlegend=True,
                legend=dict(orientation="h", y=1.6, x=0),
                xaxis=dict(title="minutes", gridcolor="#2a2a2a"),
                yaxis=dict(showticklabels=False),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
                margin=dict(l=10, r=10, t=40, b=30),
            )
            st.plotly_chart(fig_stages, width="stretch")

        with sc2:
            # Donut
            fig_donut = go.Figure(go.Pie(
                labels=list(stages.keys()),
                values=list(stages.values()),
                hole=0.6,
                marker_colors=[STAGE_COLORS[s] for s in stages],
                textinfo="percent",
                hovertemplate="%{label}: %{value} min (%{percent})<extra></extra>",
            ))
            fig_donut.update_layout(
                height=200, showlegend=False,
                annotations=[dict(text=fmt_duration(total_stage_min),
                                  x=0.5, y=0.5, font_size=14, showarrow=False,
                                  font_color="#fafafa")],
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
                margin=dict(l=0, r=0, t=10, b=10),
            )
            st.plotly_chart(fig_donut, width="stretch")

        # Quality flags
        deep_pct  = stages["Deep"]  / total_stage_min * 100 if total_stage_min else 0
        rem_pct   = stages["REM"]   / total_stage_min * 100 if total_stage_min else 0
        awake_pct = stages["Awake"] / total_stage_min * 100 if total_stage_min else 0

        flags = []
        if deep_pct >= 20:
            flags.append("✅ Good deep sleep (≥20%)")
        elif deep_pct > 0:
            flags.append(f"⚠️ Low deep sleep ({deep_pct:.0f}% — target ≥20%)")

        if rem_pct >= 20:
            flags.append("✅ Good REM (≥20%)")
        elif rem_pct > 0:
            flags.append(f"⚠️ Low REM ({rem_pct:.0f}% — target ≥20%)")

        if awake_pct > 10:
            flags.append(f"⚠️ Fragmented sleep — {awake_pct:.0f}% awake time")

        for f in flags:
            st.caption(f)

    # ── HRV context ───────────────────────────────────────────────────────────
    if detail["overnight_hrv"] and detail["baseline_hrv"]:
        st.divider()
        st.markdown("**HRV vs Baseline**")

        hrv_val  = detail["overnight_hrv"]
        baseline = detail["baseline_hrv"]
        delta    = hrv_val - baseline
        pct      = delta / baseline * 100

        hc1, hc2 = st.columns(2)
        hc1.metric("Tonight's HRV",  f"{hrv_val:.0f} ms")
        hc1.metric("7-day Baseline", f"{baseline:.1f} ms",
                   delta=f"{delta:+.1f} ms ({pct:+.0f}%)",
                   delta_color="normal" if delta >= 0 else "inverse")

        if delta > 3:
            hc2.success("HRV elevated — good recovery signal. Autonomic nervous system well-balanced.")
        elif delta < -5:
            hc2.error("HRV suppressed — parasympathetic withdrawal. Consider reducing training load.")
        elif -5 <= delta <= -1:
            hc2.warning("HRV slightly below baseline — monitor. Normal variation unless sustained.")
        else:
            hc2.info("HRV tracking baseline closely — stable recovery.")
