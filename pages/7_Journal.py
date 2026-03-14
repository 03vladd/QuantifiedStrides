"""
Daily Journal — free-text entries + full history of readiness check-ins,
post-workout reflections, and journal notes, with trend charts.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta

from db import get_connection
from session import current_user_id

st.set_page_config(page_title="Journal", page_icon="📓", layout="wide")
st.title("📓 Journal")

USER_ID = current_user_id()

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#fafafa",
    margin=dict(l=40, r=20, t=40, b=40),
)


# ---------------------------------------------------------------------------
# Ensure journal_entries table exists
# ---------------------------------------------------------------------------

def _ensure_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            entry_id   SERIAL PRIMARY KEY,
            user_id    INT  NOT NULL,
            entry_date DATE NOT NULL,
            content    TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (user_id, entry_date)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

_ensure_table()


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=120)
def load_history(user_id, days):
    """All days with any data: readiness + reflection + journal note."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            d.entry_date,
            r.overall_feel, r.legs_feel, r.upper_body_feel, r.joint_feel,
            r.injury_note, r.time_available, r.going_out_tonight,
            wr.session_rpe, wr.session_quality, wr.notes AS reflection_notes,
            je.content AS journal_note
        FROM (
            SELECT entry_date FROM daily_readiness
            WHERE user_id = %s AND entry_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            UNION
            SELECT entry_date FROM workout_reflection
            WHERE user_id = %s AND entry_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            UNION
            SELECT entry_date FROM journal_entries
            WHERE user_id = %s AND entry_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ) d
        LEFT JOIN daily_readiness r
            ON r.entry_date = d.entry_date AND r.user_id = %s
        LEFT JOIN workout_reflection wr
            ON wr.entry_date = d.entry_date AND wr.user_id = %s
        LEFT JOIN journal_entries je
            ON je.entry_date = d.entry_date AND je.user_id = %s
        ORDER BY d.entry_date DESC
    """, (user_id, days, user_id, days, user_id, days, user_id, user_id, user_id))
    cols = [
        "entry_date",
        "overall", "legs", "upper", "joints",
        "injury_note", "time_available", "going_out",
        "rpe", "session_quality", "reflection_notes",
        "journal_note",
    ]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


@st.cache_data(ttl=120)
def load_entry(user_id, entry_date):
    """Load existing journal entry for a specific date."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT content FROM journal_entries WHERE user_id = %s AND entry_date = %s",
        (user_id, entry_date)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else ""


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_write, tab_history, tab_trends = st.tabs(["✏️ Write Entry", "📅 History", "📈 Trends"])


# ── Write Entry ──────────────────────────────────────────────────────────────

with tab_write:
    entry_date = st.date_input("Entry date", value=date.today(), key="journal_date")
    existing   = load_entry(USER_ID, entry_date)

    if existing:
        st.info(f"Entry for {entry_date.strftime('%d %b %Y')} exists — editing it.")

    with st.form("journal_form"):
        content = st.text_area(
            "Journal entry",
            value=existing,
            height=220,
            placeholder=(
                "How did the day go? How's the body feeling? "
                "Anything notable about training, recovery, or life stress? …"
            ),
        )
        saved = st.form_submit_button("💾 Save Entry", type="primary")

    if saved:
        if not content.strip():
            st.error("Entry cannot be empty.")
        else:
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO journal_entries (user_id, entry_date, content)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, entry_date) DO UPDATE
                    SET content = EXCLUDED.content, created_at = now()
            """, (USER_ID, entry_date, content.strip()))
            conn.commit()
            cur.close()
            conn.close()
            load_entry.clear()
            load_history.clear()
            st.toast("Journal entry saved", icon="✅")

    # Show today's readiness and reflection as context
    day_data = load_history(USER_ID, 1)
    today_row = next((r for r in day_data if r["entry_date"] == entry_date), None)
    if today_row and any(today_row[k] for k in ("overall", "rpe", "reflection_notes")):
        st.divider()
        st.markdown("**Today's data context**")
        c1, c2 = st.columns(2)
        if today_row.get("overall"):
            c1.markdown(
                f"**Morning check-in:** feel {today_row['overall']}/10 · "
                f"legs {today_row['legs']}/10 · joints {today_row['joints']}/10"
            )
            if today_row.get("injury_note"):
                c1.caption(f"🩹 {today_row['injury_note']}")
        if today_row.get("rpe"):
            c2.markdown(
                f"**Post-workout:** RPE {today_row['rpe']}/10 · "
                f"quality {today_row['session_quality']}/10"
            )
        if today_row.get("reflection_notes"):
            st.caption(f"_Workout notes:_ {today_row['reflection_notes']}")


# ── History ───────────────────────────────────────────────────────────────────

with tab_history:
    h_col1, h_col2 = st.columns([2, 1])
    days_opt = {30: "Last 30 days", 90: "Last 3 months", 180: "Last 6 months", 365: "Last year"}
    days = h_col1.selectbox("Period", list(days_opt.keys()), format_func=lambda d: days_opt[d], index=1)
    if h_col2.button("🔄 Refresh", key="hist_refresh"):
        load_history.clear()
        st.toast("Refreshed", icon="✅")

    rows = load_history(USER_ID, days)

    if not rows:
        st.info("No entries yet in this period.")
    else:
        for row in rows:
            d = row["entry_date"]
            day_label = d.strftime("%A, %d %b %Y")
            has_readiness   = row.get("overall") is not None
            has_reflection  = row.get("rpe") is not None
            has_journal     = bool(row.get("journal_note"))

            # Build compact header summary
            badges = []
            if has_readiness:
                badges.append(f"feel {row['overall']}/10")
            if has_reflection:
                badges.append(f"RPE {row['rpe']}/10")
            if has_journal:
                badges.append("📓")
            if row.get("injury_note"):
                badges.append("🩹")

            summary = "  ·  ".join(badges) if badges else "no data"

            with st.expander(f"**{day_label}**  —  {summary}"):
                left, right = st.columns(2)

                with left:
                    if has_readiness:
                        st.markdown("**Morning check-in**")
                        st.markdown(
                            f"Overall **{row['overall']}/10** · legs {row['legs']}/10 · "
                            f"upper {row['upper']}/10 · joints {row['joints']}/10"
                        )
                        if row.get("injury_note"):
                            st.caption(f"🩹 {row['injury_note']}")
                        parts = []
                        if row.get("time_available"):
                            parts.append(f"time: {row['time_available']}")
                        if row.get("going_out"):
                            parts.append("going out tonight")
                        if parts:
                            st.caption("  ·  ".join(parts))
                    else:
                        st.caption("_No morning check-in_")

                with right:
                    if has_reflection:
                        st.markdown("**Post-workout reflection**")
                        st.markdown(f"RPE **{row['rpe']}/10** · quality {row['session_quality']}/10")
                        if row.get("reflection_notes"):
                            st.markdown(f"> {row['reflection_notes']}")
                    else:
                        st.caption("_No post-workout reflection_")

                if has_journal:
                    st.markdown("**Journal note**")
                    st.markdown(row["journal_note"])

                # Quick edit link
                if st.button("✏️ Edit journal entry", key=f"edit_{d}"):
                    st.session_state["journal_edit_date"] = d
                    st.switch_page("pages/7_Journal.py")


# ── Trends ────────────────────────────────────────────────────────────────────

with tab_trends:
    t_col1, t_col2 = st.columns([2, 1])
    trend_days_opt = {30: "30 days", 60: "60 days", 90: "90 days", 180: "180 days"}
    trend_days = t_col1.selectbox(
        "Period", list(trend_days_opt.keys()),
        format_func=lambda d: trend_days_opt[d], index=1, key="trend_days"
    )

    trend_rows = load_history(USER_ID, trend_days)

    # Filter to days with readiness data
    readiness_rows = [r for r in trend_rows if r.get("overall")]
    reflection_rows = [r for r in trend_rows if r.get("rpe")]

    if not readiness_rows and not reflection_rows:
        st.info("No check-in or reflection data in this period.")
    else:
        # ── Readiness scores trend ──────────────────────────────────────────
        if readiness_rows:
            dates     = [r["entry_date"] for r in readiness_rows]
            overall   = [r["overall"]    for r in readiness_rows]
            legs      = [r["legs"]       for r in readiness_rows]
            joints    = [r["joints"]     for r in readiness_rows]

            fig_feel = go.Figure()
            fig_feel.add_trace(go.Scatter(
                x=dates, y=overall, name="Overall",
                line=dict(color="#00cec9", width=2),
                hovertemplate="Overall: %{y}/10<extra></extra>",
            ))
            fig_feel.add_trace(go.Scatter(
                x=dates, y=legs, name="Legs",
                line=dict(color="#6c5ce7", width=1.5, dash="dot"),
                hovertemplate="Legs: %{y}/10<extra></extra>",
            ))
            fig_feel.add_trace(go.Scatter(
                x=dates, y=joints, name="Joints",
                line=dict(color="#fd79a8", width=1.5, dash="dot"),
                hovertemplate="Joints: %{y}/10<extra></extra>",
            ))
            # 7-day rolling avg for overall
            if len(overall) >= 7:
                from datetime import timedelta
                rolling, rdates = [], []
                for i, (d, v) in enumerate(zip(dates, overall)):
                    window = [overall[j] for j in range(max(0, i - 6), i + 1)]
                    rolling.append(sum(window) / len(window))
                    rdates.append(d)
                fig_feel.add_trace(go.Scatter(
                    x=rdates, y=rolling, name="7-day avg",
                    line=dict(color="#00cec9", width=2.5),
                    opacity=0.4,
                    hovertemplate="7d avg: %{y:.1f}<extra></extra>",
                ))

            fig_feel.update_layout(
                title="Readiness Scores",
                height=280,
                yaxis=dict(range=[0, 10.5], title="score /10", gridcolor="#2a2a2a"),
                xaxis=dict(gridcolor="#2a2a2a"),
                legend=dict(orientation="h", y=1.15),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            )
            st.plotly_chart(fig_feel, width="stretch")

        # ── RPE + session quality ───────────────────────────────────────────
        if reflection_rows:
            rdates  = [r["entry_date"]       for r in reflection_rows]
            rpe     = [r["rpe"]              for r in reflection_rows]
            quality = [r["session_quality"]  for r in reflection_rows]

            fig_rpe = go.Figure()
            fig_rpe.add_trace(go.Bar(
                x=rdates, y=rpe, name="RPE",
                marker_color="#e17055", opacity=0.7,
                hovertemplate="RPE: %{y}/10<extra></extra>",
            ))
            fig_rpe.add_trace(go.Scatter(
                x=rdates, y=quality, name="Session quality",
                line=dict(color="#55efc4", width=2),
                mode="lines+markers", marker_size=5,
                hovertemplate="Quality: %{y}/10<extra></extra>",
            ))
            fig_rpe.update_layout(
                title="Session RPE & Quality",
                height=240,
                barmode="overlay",
                yaxis=dict(range=[0, 10.5], title="score /10", gridcolor="#2a2a2a"),
                xaxis=dict(gridcolor="#2a2a2a"),
                legend=dict(orientation="h", y=1.15),
                **{k: v for k, v in DARK_LAYOUT.items() if k not in ("xaxis", "yaxis", "margin")},
            )
            st.plotly_chart(fig_rpe, width="stretch")

        # ── Injury flag timeline ────────────────────────────────────────────
        injury_rows = [r for r in readiness_rows if r.get("injury_note")]
        if injury_rows:
            st.markdown("**Injury / discomfort notes**")
            for r in injury_rows:
                st.markdown(f"- **{r['entry_date'].strftime('%d %b %Y')}**: {r['injury_note']}")
