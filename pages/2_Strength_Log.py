"""
Strength session logger.
Replaces the CLI strength_log.py with a Streamlit form.
"""

import streamlit as st
from datetime import date

from db import get_connection
from session import current_user_id
from options import (
    get_muscles, get_equipment, get_joints, get_sport_carryover_keys,
    get_movement_patterns, get_quality_focuses, get_contraction_types,
    get_skill_levels,
)

st.set_page_config(page_title="Strength Log", page_icon="🏋️", layout="wide")
st.title("🏋️ Strength Log")

BAR_WEIGHT_KG = 20.0
USER_ID = current_user_id()

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "sl_exercises" not in st.session_state:
    st.session_state.sl_exercises = []   # list of exercise dicts
if "sl_saved" not in st.session_state:
    st.session_state.sl_saved = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_exercise_names():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT name FROM exercises ORDER BY name")
    names = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return names


def compute_total(weight_kg, plus_bar, incl_bar, per_hand):
    if weight_kg is None:
        return None
    if plus_bar:
        return weight_kg + BAR_WEIGHT_KG
    if incl_bar:
        return weight_kg  # already includes bar; stored separately
    if per_hand:
        return weight_kg * 2
    return weight_kg


def weight_display(s):
    if s.get("is_bodyweight"):
        return "BW"
    if s.get("band_color"):
        return f"band({s['band_color']})"
    tw = s.get("total_weight_kg")
    return f"{tw} kg" if tw is not None else "—"


def reps_display(s):
    if s.get("duration_seconds"):
        return f"{s['duration_seconds']}s"
    return str(s.get("reps") or "?")


# ---------------------------------------------------------------------------
# Date / session type header
# ---------------------------------------------------------------------------

col_date, col_type = st.columns([1, 1])
session_date = col_date.date_input("Session date", value=date.today())
session_type = col_type.radio("Session type", ["upper", "lower"], horizontal=True)

st.divider()

# ---------------------------------------------------------------------------
# Add exercise form
# ---------------------------------------------------------------------------

exercise_names = load_exercise_names()

with st.expander("➕ Add Exercise", expanded=len(st.session_state.sl_exercises) == 0):
    with st.form("add_exercise_form", clear_on_submit=True):
        st.markdown("#### Exercise details")
        ec1, ec2 = st.columns([2, 2])
        ex_name  = ec1.selectbox("Exercise", exercise_names, index=0)
        ex_notes = ec2.text_input("Notes (optional)")

        st.markdown("#### Modifiers")
        mc1, mc2 = st.columns(2)
        per_hand = mc1.checkbox("Per hand (each arm counted separately)")
        per_side = mc2.checkbox("Per side (each leg counted separately)")

        st.markdown("#### Weight")
        wc1, wc2 = st.columns([1, 2])
        weight_type = wc1.radio("Weight type", ["kg", "bodyweight", "band"], key="wt_radio")

        weight_kg   = None
        plus_bar    = False
        incl_bar    = False
        band_color  = None

        if weight_type == "kg":
            w_col1, w_col2 = wc2.columns(2)
            weight_kg = w_col1.number_input("Weight (kg)", min_value=0.0, step=0.5, value=0.0)
            bar_opt   = w_col2.radio("Barbell", ["no bar", "+20 kg bar", "includes bar"], key="bar_radio")
            plus_bar  = bar_opt == "+20 kg bar"
            incl_bar  = bar_opt == "includes bar"
        elif weight_type == "band":
            BAND_COLORS = ["yellow", "blue", "green", "red", "black"]
            band_color = wc2.selectbox("Band color", BAND_COLORS)

        st.markdown("#### Sets")
        sc1, sc2, sc3 = st.columns(3)
        n_sets   = sc1.number_input("Number of sets", min_value=1, max_value=20, value=3)
        is_timed = sc2.toggle("Time-based (seconds)", value=False)
        if is_timed:
            duration = sc3.number_input("Duration per set (s)", min_value=1, value=30)
            reps_val = None
        else:
            reps_val = sc3.number_input("Reps per set", min_value=1, value=8)
            duration = None

        add_btn = st.form_submit_button("Add to session", type="primary")

    if add_btn:
        if weight_type == "kg" and incl_bar and weight_kg is not None:
            stored_weight = weight_kg - BAR_WEIGHT_KG
        else:
            stored_weight = weight_kg if weight_type == "kg" else None

        total = compute_total(
            stored_weight if weight_type == "kg" else None,
            plus_bar, incl_bar, per_hand
        )

        sets = []
        for i in range(int(n_sets)):
            sets.append({
                "set_number":          i + 1,
                "reps":                int(reps_val) if reps_val is not None else None,
                "duration_seconds":    int(duration) if duration is not None else None,
                "weight_kg":           stored_weight if weight_type == "kg" else None,
                "is_bodyweight":       weight_type == "bodyweight",
                "band_color":          band_color if weight_type == "band" else None,
                "per_hand":            per_hand,
                "per_side":            per_side,
                "plus_bar":            plus_bar,
                "weight_includes_bar": incl_bar,
                "total_weight_kg":     total,
            })

        st.session_state.sl_exercises.append({
            "exercise_order": len(st.session_state.sl_exercises) + 1,
            "name":   ex_name,
            "notes":  ex_notes or None,
            "sets":   sets,
        })
        st.session_state.sl_saved = False
        st.rerun()


# ---------------------------------------------------------------------------
# Session preview
# ---------------------------------------------------------------------------

if st.session_state.sl_exercises:
    st.subheader(f"Session — {session_type.capitalize()} — {session_date.strftime('%d %b %Y')}")

    for idx, ex in enumerate(st.session_state.sl_exercises):
        s0       = ex["sets"][0]
        n_sets   = len(ex["sets"])
        all_reps = list({reps_display(s) for s in ex["sets"]})
        all_wts  = list({weight_display(s) for s in ex["sets"]})
        reps_str = all_reps[0] if len(all_reps) == 1 else " / ".join(sorted(all_reps))
        wt_str   = all_wts[0]  if len(all_wts)  == 1 else " / ".join(sorted(all_wts))
        mods     = []
        if s0.get("per_hand"): mods.append("per hand")
        if s0.get("per_side"): mods.append("per side")
        mod_str  = f"  _{', '.join(mods)}_" if mods else ""

        col_ex, col_del = st.columns([8, 1])
        note_str = f" _{ex['notes']}_" if ex["notes"] else ""
        col_ex.markdown(f"**{idx+1}. {ex['name']}**{note_str}  \n"
                        f"{n_sets} × {reps_str} @ {wt_str}{mod_str}")
        if col_del.button("✕", key=f"del_{idx}", help="Remove exercise"):
            st.session_state.sl_exercises.pop(idx)
            # renumber
            for i, e in enumerate(st.session_state.sl_exercises):
                e["exercise_order"] = i + 1
            st.rerun()

    st.divider()

    # Per-set weight editing (optional advanced section)
    with st.expander("Edit individual set weights / reps"):
        for ex_idx, ex in enumerate(st.session_state.sl_exercises):
            st.markdown(f"**{ex['name']}**")
            for s in ex["sets"]:
                sc1, sc2, sc3 = st.columns(3)
                skey = f"ex{ex_idx}_s{s['set_number']}"
                if s.get("is_bodyweight"):
                    sc1.markdown(f"Set {s['set_number']}: BW")
                elif s.get("band_color"):
                    sc1.markdown(f"Set {s['set_number']}: band({s['band_color']})")
                else:
                    new_total = sc1.number_input(
                        f"Set {s['set_number']} total kg",
                        value=float(s.get("total_weight_kg") or 0),
                        step=0.5, key=f"{skey}_w"
                    )
                    s["total_weight_kg"] = new_total if new_total > 0 else None

                if s.get("duration_seconds") is not None:
                    new_dur = sc2.number_input(
                        "Duration (s)", value=int(s["duration_seconds"]),
                        min_value=1, key=f"{skey}_d"
                    )
                    s["duration_seconds"] = new_dur
                else:
                    new_reps = sc2.number_input(
                        "Reps", value=int(s.get("reps") or 1),
                        min_value=1, key=f"{skey}_r"
                    )
                    s["reps"] = new_reps

    # Save button
    save_col, clear_col = st.columns([2, 1])
    save_btn  = save_col.button("💾 Save Session", type="primary",
                                 disabled=st.session_state.sl_saved)
    clear_btn = clear_col.button("🗑 Clear All")

    if clear_btn:
        st.session_state.sl_exercises = []
        st.session_state.sl_saved = False
        st.rerun()

    if save_btn:
        conn = get_connection()
        cur  = conn.cursor()

        cur.execute("""
            INSERT INTO strength_sessions (user_id, session_date, session_type, raw_notes)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (user_id, session_date) DO UPDATE SET
                session_type = EXCLUDED.session_type
            RETURNING session_id
        """, (USER_ID, session_date, session_type))
        session_id = cur.fetchone()[0]

        cur.execute("DELETE FROM strength_exercises WHERE session_id = %s", (session_id,))

        for ex in st.session_state.sl_exercises:
            cur.execute("""
                INSERT INTO strength_exercises (session_id, exercise_order, name, notes)
                VALUES (%s, %s, %s, %s) RETURNING exercise_id
            """, (session_id, ex["exercise_order"], ex["name"], ex["notes"]))
            exercise_id = cur.fetchone()[0]

            for s in ex["sets"]:
                cur.execute("""
                    INSERT INTO strength_sets (
                        exercise_id, set_number, reps, duration_seconds,
                        weight_kg, is_bodyweight, band_color,
                        per_hand, per_side, plus_bar,
                        weight_includes_bar, total_weight_kg
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    exercise_id, s["set_number"], s.get("reps"), s.get("duration_seconds"),
                    s.get("weight_kg"), s.get("is_bodyweight"), s.get("band_color"),
                    s.get("per_hand"), s.get("per_side"), s.get("plus_bar"),
                    s.get("weight_includes_bar"), s.get("total_weight_kg"),
                ))

        conn.commit()
        cur.close()
        conn.close()

        st.session_state.sl_saved = True
        st.success(f"Session saved! ({len(st.session_state.sl_exercises)} exercises)")
        st.cache_data.clear()
        st.rerun()

else:
    st.info("No exercises added yet. Use the form above to build your session.")


# ---------------------------------------------------------------------------
# Add custom exercise to the database
# ---------------------------------------------------------------------------

st.divider()

with st.expander("🆕 Add Custom Exercise to Library"):
    _muscles     = get_muscles()
    _equipment   = get_equipment()
    _joints      = get_joints()
    _sports      = get_sport_carryover_keys()
    _movements   = [""] + get_movement_patterns()
    _qualities   = [""] + get_quality_focuses()
    _contractions = [""] + get_contraction_types()
    _skill_levels = get_skill_levels()

    with st.form("new_exercise_form"):
        st.markdown("#### Identity")
        n1, n2 = st.columns([2, 1])
        ex_name_new = n1.text_input("Exercise name *", placeholder="e.g. Copenhagen Plank")
        ex_source   = "custom"

        st.markdown("#### Movement taxonomy")
        t1, t2, t3 = st.columns(3)
        movement_pattern = t1.selectbox("Movement pattern *", _movements)
        quality_focus    = t2.selectbox("Quality focus *",    _qualities)
        contraction_type = t3.selectbox("Contraction type *", _contractions)

        st.markdown("#### Muscles")
        m1, m2 = st.columns(2)
        primary_muscles   = m1.multiselect("Primary muscles *", _muscles)
        secondary_muscles = m2.multiselect("Secondary muscles", _muscles)

        st.markdown("#### Equipment & difficulty")
        d1, d2, d3, d4 = st.columns(4)
        equipment   = d1.multiselect("Equipment", _equipment)
        skill_level = d2.selectbox("Skill level", _skill_levels)
        bilateral   = d3.checkbox("Bilateral", value=True)

        st.markdown("#### Fatigue profile")
        f1, f2 = st.columns(2)
        systemic_fatigue = f1.slider("Systemic fatigue (1–5)", 1, 5, 3,
                                     help="How much does this tax the whole body? 1=minimal, 5=very high")
        cns_load         = f2.slider("CNS load (1–5)", 1, 5, 2,
                                     help="Central nervous system demand. High for heavy compound lifts and plyometrics.")

        st.markdown("#### Joint stress _(optional)_")
        js_cols = st.columns(len(_joints)) if _joints else st.columns(1)
        joint_stress = {}
        for col, joint in zip(js_cols, _joints):
            v = col.number_input(joint, min_value=0, max_value=5, value=0, step=1,
                                 key=f"js_{joint}")
            if v > 0:
                joint_stress[joint] = v

        st.markdown("#### Sport carryover _(optional)_")
        sp_cols = st.columns(len(_sports)) if _sports else st.columns(1)
        sport_carryover = {}
        for col, sport in zip(sp_cols, _sports):
            v = col.number_input(sport.replace("_", " "), min_value=0, max_value=5, value=0, step=1,
                                 key=f"sc_{sport}")
            if v > 0:
                sport_carryover[sport] = v

        st.markdown("#### Notes _(optional)_")
        ex_notes_new = st.text_area("Notes", placeholder="Cues, variations, links…")

        submitted = st.form_submit_button("Add to Exercise Library", type="primary")

    if submitted:
        errors = []
        if not ex_name_new.strip():
            errors.append("Exercise name is required.")
        if not movement_pattern:
            errors.append("Movement pattern is required.")
        if not quality_focus:
            errors.append("Quality focus is required.")
        if not contraction_type:
            errors.append("Contraction type is required.")
        if not primary_muscles:
            errors.append("At least one primary muscle is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            import json
            conn = get_connection()
            cur  = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO exercises (
                        name, source,
                        movement_pattern, quality_focus, contraction_type,
                        primary_muscles, secondary_muscles,
                        equipment, skill_level, bilateral,
                        systemic_fatigue, cns_load,
                        joint_stress, sport_carryover,
                        notes
                    ) VALUES (
                        %s, 'custom',
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s
                    )
                """, (
                    ex_name_new.strip(),
                    movement_pattern, quality_focus, contraction_type,
                    primary_muscles, secondary_muscles or [],
                    equipment or [], skill_level, bilateral,
                    systemic_fatigue, cns_load,
                    json.dumps(joint_stress) if joint_stress else "{}",
                    json.dumps(sport_carryover) if sport_carryover else "{}",
                    ex_notes_new.strip() or None,
                ))
                conn.commit()
                load_exercise_names.clear()
                st.toast(f'"{ex_name_new.strip()}" added to library', icon="✅")
            except Exception as e:
                conn.rollback()
                if "unique" in str(e).lower():
                    st.error(f'An exercise named "{ex_name_new.strip()}" already exists.')
                else:
                    st.error(f"Database error: {e}")
            finally:
                cur.close()
                conn.close()
