"""
Morning check-in + post-workout reflection page.
"""

import streamlit as st
from datetime import date

from db import get_connection
from session import current_user_id

st.set_page_config(page_title="Check-In", page_icon="📋", layout="wide")
st.title("📋 Check-In")

USER_ID = current_user_id()

tab_morning, tab_post = st.tabs(["Morning Check-In", "Post-Workout Reflection"])


# ---------------------------------------------------------------------------
# Morning Check-In
# ---------------------------------------------------------------------------

with tab_morning:
    st.subheader("How are you feeling today?")

    entry_date = st.date_input("Date", value=date.today(), key="ci_date")

    # Check if already logged
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT overall_feel, legs_feel, upper_body_feel, joint_feel, "
        "injury_note, time_available, going_out_tonight "
        "FROM daily_readiness WHERE user_id = %s AND entry_date = %s",
        (USER_ID, entry_date,)
    )
    existing = cur.fetchone()
    cur.close()
    conn.close()

    if existing:
        st.info(f"Check-in for {entry_date.strftime('%d %b %Y')} already logged — update below.")
        defaults = {
            "overall": existing[0], "legs": existing[1],
            "upper": existing[2], "joints": existing[3],
            "injury_note": existing[4] or "",
            "time": existing[5] or "medium",
            "going_out": bool(existing[6]),
        }
    else:
        defaults = {
            "overall": 7, "legs": 7, "upper": 7, "joints": 8,
            "injury_note": "", "time": "medium", "going_out": False,
        }

    date_key = entry_date.isoformat()  # force widget reset when date changes
    with st.form("morning_checkin_form"):
        st.markdown("**Rate 1 (terrible) → 10 (perfect)**")
        c1, c2, c3, c4 = st.columns(4)
        overall = c1.slider("Overall feel",    1, 10, defaults["overall"], key=f"overall_{date_key}")
        legs    = c2.slider("Legs",            1, 10, defaults["legs"],    key=f"legs_{date_key}")
        upper   = c3.slider("Upper body",      1, 10, defaults["upper"],   key=f"upper_{date_key}")
        joints  = c4.slider("Joints / injury", 1, 10, defaults["joints"],  key=f"joints_{date_key}")

        injury_note = None
        if joints <= 6:
            injury_note = st.text_input(
                "What's bothering you?", value=defaults["injury_note"],
                placeholder="e.g. left knee slight ache"
            ) or None

        st.markdown("---")
        col_time, col_out = st.columns(2)
        time_available = col_time.radio(
            "Time available today",
            options=["short", "medium", "long"],
            index=["short", "medium", "long"].index(defaults["time"]),
            horizontal=True,
        )
        going_out = col_out.toggle("Going out tonight?", value=defaults["going_out"])

        label = "Update Check-In" if existing else "Save Check-In"
        submitted = st.form_submit_button(label, type="primary")

    if submitted:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO daily_readiness
                (user_id, entry_date, overall_feel, legs_feel, upper_body_feel,
                 joint_feel, injury_note, time_available, going_out_tonight)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                overall_feel      = EXCLUDED.overall_feel,
                legs_feel         = EXCLUDED.legs_feel,
                upper_body_feel   = EXCLUDED.upper_body_feel,
                joint_feel        = EXCLUDED.joint_feel,
                injury_note       = EXCLUDED.injury_note,
                time_available    = EXCLUDED.time_available,
                going_out_tonight = EXCLUDED.going_out_tonight
        """, (USER_ID, entry_date, overall, legs, upper, joints, injury_note, time_available, going_out))
        conn.commit()
        cur.close()
        conn.close()
        st.success("Check-in saved!")
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Post-Workout Reflection
# ---------------------------------------------------------------------------

with tab_post:
    st.subheader("Post-Workout Reflection")

    post_date = st.date_input("Date", value=date.today(), key="post_date")

    # Check existing
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT session_rpe, session_quality, notes "
        "FROM workout_reflection WHERE user_id = %s AND entry_date = %s",
        (USER_ID, post_date,)
    )
    existing_post = cur.fetchone()
    cur.close()
    conn.close()

    if existing_post:
        st.info(f"Reflection for {post_date.strftime('%d %b %Y')} already logged. You can update it below.")
        post_defaults = {
            "rpe": existing_post[0] or 6,
            "quality": existing_post[1] or 6,
            "notes": existing_post[2] or "",
        }
    else:
        post_defaults = {"rpe": 6, "quality": 7, "notes": ""}

    with st.form("post_workout_form"):
        pc1, pc2 = st.columns(2)
        rpe     = pc1.slider("Session RPE — how hard was it?", 1, 10, post_defaults["rpe"])
        quality = pc2.slider("Session quality — how well did it go?", 1, 10, post_defaults["quality"])
        notes   = st.text_area("Notes", value=post_defaults["notes"], placeholder="Anything notable about this session…")

        post_submitted = st.form_submit_button("Save Reflection", type="primary")

    if post_submitted:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO workout_reflection (user_id, entry_date, session_rpe, session_quality, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                session_rpe     = EXCLUDED.session_rpe,
                session_quality = EXCLUDED.session_quality,
                notes           = EXCLUDED.notes
        """, (USER_ID, post_date, rpe, quality, notes or None))
        conn.commit()
        cur.close()
        conn.close()
        st.success("Reflection saved!")
        st.rerun()
