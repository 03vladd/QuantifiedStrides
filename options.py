"""
options.py

Single source of truth for all dropdown / multiselect options used across
the Streamlit pages.  Everything is pulled from the database so it stays
in sync with the actual data — add a new exercise with a new muscle and it
appears everywhere automatically.

All functions are cached for 1 hour (options rarely change mid-session).
When there is no data to query (empty DB), each function returns a sensible
fallback so the UI never breaks with an empty list.
"""

import streamlit as st
from db import get_connection


# ---------------------------------------------------------------------------
# Exercise taxonomy — derived from the exercises table
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_muscles() -> list[str]:
    """All distinct muscle names across primary + secondary, alphabetically."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT unnest(primary_muscles || COALESCE(secondary_muscles, '{}'))
        FROM exercises
        WHERE primary_muscles IS NOT NULL
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["quads", "hamstrings", "glutes", "chest", "lats", "triceps", "biceps"]


@st.cache_data(ttl=3600)
def get_equipment() -> list[str]:
    """All distinct equipment values used in exercises, alphabetically."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT unnest(equipment)
        FROM exercises
        WHERE equipment IS NOT NULL AND array_length(equipment, 1) > 0
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["barbell", "dumbbell", "bodyweight"]


@st.cache_data(ttl=3600)
def get_movement_patterns() -> list[str]:
    """All movement pattern values present in the exercises table."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT movement_pattern
        FROM exercises
        WHERE movement_pattern IS NOT NULL
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["push_h", "push_v", "pull_h", "pull_v", "hinge", "squat",
                      "carry", "rotation", "plyo", "isolation", "stability"]


@st.cache_data(ttl=3600)
def get_quality_focuses() -> list[str]:
    """All quality focus values present in the exercises table."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT quality_focus
        FROM exercises
        WHERE quality_focus IS NOT NULL
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["power", "strength", "hypertrophy", "endurance", "stability"]


@st.cache_data(ttl=3600)
def get_contraction_types() -> list[str]:
    """All contraction type values present in the exercises table."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT contraction_type
        FROM exercises
        WHERE contraction_type IS NOT NULL
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["explosive", "controlled", "isometric", "mixed"]


@st.cache_data(ttl=3600)
def get_skill_levels() -> list[str]:
    """All skill level values present in the exercises table, ordered easy→hard."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT skill_level
        FROM exercises
        WHERE skill_level IS NOT NULL
    """)
    raw = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    order = ["beginner", "intermediate", "advanced"]
    return [s for s in order if s in raw] or order


@st.cache_data(ttl=3600)
def get_joints() -> list[str]:
    """
    All joint keys that appear in at least one exercise's joint_stress JSONB.
    Ordered anatomically (upper → lower).
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT jsonb_object_keys(joint_stress)
        FROM exercises
        WHERE joint_stress IS NOT NULL AND joint_stress != '{}'
    """)
    raw = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    order = ["neck", "shoulder", "elbow", "wrist", "spine",
             "lower_back", "hip", "knee", "ankle"]
    ordered = [j for j in order if j in raw]
    extras  = sorted(raw - set(order))
    return (ordered + extras) or ["shoulder", "elbow", "wrist", "knee", "hip", "lower_back", "ankle"]


@st.cache_data(ttl=3600)
def get_sport_carryover_keys() -> list[str]:
    """All sport keys that appear in at least one exercise's sport_carryover JSONB."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT jsonb_object_keys(sport_carryover)
        FROM exercises
        WHERE sport_carryover IS NOT NULL AND sport_carryover != '{}'
        ORDER BY 1
    """)
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result or ["xc_mtb", "trail_run", "climbing", "ski", "snowboard"]


# ---------------------------------------------------------------------------
# Workout sports — derived from actual recorded workouts
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_recorded_sports(user_id: int = 1) -> list[str]:
    """All distinct sport values recorded for this user, alphabetically."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT sport FROM workouts WHERE user_id = %s ORDER BY sport
    """, (user_id,))
    result = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return result


@st.cache_data(ttl=3600)
def get_sport_options_with_all(user_id: int = 1) -> list[str]:
    """['All'] + all recorded sports. Used in history page filter dropdowns."""
    return ["All"] + get_recorded_sports(user_id)


# ---------------------------------------------------------------------------
# Display helpers — not DB-backed but centralised so they're one place to change
# ---------------------------------------------------------------------------

SPORT_ICONS: dict[str, str] = {
    "running":          "🏃",
    "trail_running":    "🏔️",
    "cycling":          "🚴",
    "mountain_biking":  "🚵",
    "indoor_cycling":   "🚴",
    "bouldering":       "🧗",
    "climbing":         "🧗",
    "resort_skiing":    "⛷️",
    "skiing":           "⛷️",
    "snowboarding":     "🏂",
    "strength_training":"🏋️",
    "indoor_cardio":    "🏃",
    "swimming":         "🏊",
    "hiking":           "🥾",
}

DEFAULT_SPORT_ICON = "🏅"


def sport_icon(sport: str) -> str:
    return SPORT_ICONS.get(sport, DEFAULT_SPORT_ICON)


def sport_label(sport: str) -> str:
    return sport.replace("_", " ").title()


def sport_display(sport: str) -> str:
    """'🏃 Running' style label for use in selectboxes."""
    return f"{sport_icon(sport)} {sport_label(sport)}"
