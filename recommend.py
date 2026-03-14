"""
Daily training recommendation engine.

Reads today's morning check-in, yesterday's training, recent load,
sleep, and weather — then outputs what to do today and why.

Usage:
    python3 recommend.py
    python3 recommend.py --date 14.03
"""

import argparse
import sys
from datetime import date, datetime, timedelta

from db import get_connection
from training_load import get_metrics, tsb_intensity_hint
from recovery import get_hrv_status, get_muscle_freshness
from alerts import get_alerts, interpret_metrics


# ---------------------------------------------------------------------------
# Garmin sport key → human label + category
# ---------------------------------------------------------------------------

SPORT_META = {
    "running":          {"label": "Road Run",        "category": "run",    "lower_load": True,  "upper_load": False},
    "trail_running":    {"label": "Trail Run",        "category": "run",    "lower_load": True,  "upper_load": False},
    "cycling":          {"label": "Road Bike",        "category": "bike",   "lower_load": True,  "upper_load": False},
    "mountain_biking":  {"label": "XC MTB",           "category": "bike",   "lower_load": True,  "upper_load": False},
    "indoor_cycling":   {"label": "Stationary Bike",  "category": "bike",   "lower_load": True,  "upper_load": False},
    "bouldering":       {"label": "Bouldering",       "category": "climb",  "lower_load": False, "upper_load": True},
    "resort_skiing":    {"label": "Skiing",           "category": "ski",    "lower_load": True,  "upper_load": False},
    "indoor_cardio":    {"label": "Cardio",           "category": "cardio", "lower_load": True,  "upper_load": False},
    "strength_training":{"label": "Gym (Garmin)",     "category": "gym",    "lower_load": False, "upper_load": False},
}


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------

def get_readiness(cur, today):
    cur.execute("""
        SELECT overall_feel, legs_feel, upper_body_feel, joint_feel,
               injury_note, time_available, going_out_tonight
        FROM daily_readiness
        WHERE user_id = 1 AND entry_date = %s
    """, (today,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "overall":       row[0],
        "legs":          row[1],
        "upper":         row[2],
        "joints":        row[3],
        "injury_note":   row[4],
        "time":          row[5],
        "going_out":     row[6],
    }


def get_yesterdays_training(cur, yesterday):
    """
    Returns a dict describing yesterday's training.
    Gym sessions take precedence over the Garmin strength_training entry.
    """
    # Check strength log first (gives us upper/lower)
    cur.execute("""
        SELECT session_type FROM strength_sessions
        WHERE user_id = 1 AND session_date = %s
    """, (yesterday,))
    row = cur.fetchone()
    if row:
        return {"source": "gym", "session_type": row[0], "sport": None}

    # Check Garmin workouts (skip strength_training — no detail there)
    cur.execute("""
        SELECT sport, workout_type, training_volume, avg_heart_rate
        FROM workouts
        WHERE user_id = 1 AND workout_date = %s
          AND sport != 'strength_training'
        ORDER BY start_time DESC
        LIMIT 1
    """, (yesterday,))
    row = cur.fetchone()
    if row:
        meta = SPORT_META.get(row[0], {"label": row[0], "category": "other",
                                        "lower_load": False, "upper_load": False})
        return {
            "source":       "garmin",
            "session_type": meta["category"],
            "sport":        row[0],
            "label":        meta["label"],
            "volume":       row[2],
            "avg_hr":       row[3],
            "lower_load":   meta["lower_load"],
            "upper_load":   meta["upper_load"],
        }

    return {"source": "rest", "session_type": "rest"}


def get_last_nights_sleep(cur, today):
    # Garmin labels sleep by the morning you wake up, so today's date = last night's sleep
    cur.execute("""
        SELECT duration_minutes, sleep_score, hrv, rhr,
               hrv_status, body_battery_change
        FROM sleep_sessions
        WHERE user_id = 1 AND sleep_date = %s
    """, (today,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "duration":      row[0],
        "score":         row[1],
        "hrv":           row[2],
        "rhr":           row[3],
        "hrv_status":    row[4],
        "body_battery":  row[5],
    }


def get_recent_load(cur, today, days=7):
    """Running km and bike minutes over the last N days."""
    since = today - timedelta(days=days)
    cur.execute("""
        SELECT sport, SUM(training_volume), SUM(
            EXTRACT(EPOCH FROM (end_time - start_time)) / 60
        )
        FROM workouts
        WHERE user_id = 1
          AND workout_date > %s AND workout_date < %s
          AND sport != 'strength_training'
        GROUP BY sport
    """, (since, today))
    rows = cur.fetchall()
    load = {"run_km": 0.0, "bike_min": 0.0, "climb_sessions": 0}
    for sport, volume, minutes in rows:
        if sport in ("running", "trail_running"):
            load["run_km"] += float(volume or 0) / 1000
        elif sport in ("cycling", "mountain_biking", "indoor_cycling"):
            load["bike_min"] += float(minutes or 0)
        elif sport == "bouldering":
            load["climb_sessions"] += 1
    return load


def get_latest_weather(cur):
    cur.execute("""
        SELECT temperature, precipitation, wind_speed
        FROM environment_data
        ORDER BY record_datetime DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return None
    return {"temp": row[0], "rain": row[1], "wind": row[2]}


def get_gym_analysis(cur, today):
    """
    Fetches the last 2 upper + 2 lower sessions with exercise labels.
    Returns per-session CNS totals, movement pattern breakdown, and muscle coverage
    so the engine can recommend what kind of gym day to do next.
    """
    cur.execute("""
        WITH ranked AS (
            SELECT ss.session_id, ss.session_date, ss.session_type,
                   ROW_NUMBER() OVER (PARTITION BY ss.session_type ORDER BY ss.session_date DESC) AS rn
            FROM strength_sessions ss
            WHERE ss.user_id = 1 AND ss.session_type IS NOT NULL
              AND ss.session_date < %s
        )
        SELECT r.session_date, r.session_type,
               e.movement_pattern, e.quality_focus,
               e.primary_muscles, e.cns_load, e.systemic_fatigue
        FROM ranked r
        JOIN strength_exercises se ON se.session_id = r.session_id
        LEFT JOIN exercises e ON e.name = se.name
        WHERE r.rn <= 2
        ORDER BY r.session_date DESC, se.exercise_order
    """, (today,))
    rows = cur.fetchall()

    from collections import defaultdict, Counter
    sessions = defaultdict(lambda: {"cns_total": 0, "fatigue_total": 0,
                                     "patterns": Counter(), "muscles": Counter(),
                                     "qualities": Counter()})
    session_order = []
    for session_date, session_type, pattern, quality, muscles, cns, fatigue in rows:
        key = (session_date, session_type)
        if key not in session_order:
            session_order.append(key)
        s = sessions[key]
        s["cns_total"]     += (cns or 0)
        s["fatigue_total"] += (fatigue or 0)
        if pattern:
            s["patterns"][pattern] += 1
        if quality:
            s["qualities"][quality] += 1
        for m in (muscles or []):
            s["muscles"][m] += 1

    # Organise into last_upper[0..1] and last_lower[0..1]
    result = {"upper": [], "lower": []}
    for key in session_order:
        session_date, session_type = key
        if session_type in result and len(result[session_type]) < 2:
            result[session_type].append({
                "date":          session_date,
                "cns_total":     sessions[key]["cns_total"],
                "fatigue_total": sessions[key]["fatigue_total"],
                "patterns":      dict(sessions[key]["patterns"]),
                "muscles":       dict(sessions[key]["muscles"]),
                "qualities":     dict(sessions[key]["qualities"]),
            })
    return result



def get_last_performance(cur, name):
    """
    Returns the sets from the most recent session for this exercise.
    Each row: (set_number, reps, duration_seconds, total_weight_kg,
                is_bodyweight, band_color, per_hand, per_side)
    """
    cur.execute("""
        SELECT st.set_number, st.reps, st.duration_seconds,
               st.weight_kg, st.total_weight_kg, st.is_bodyweight, st.band_color,
               st.per_hand, st.per_side
        FROM strength_sets st
        JOIN strength_exercises se ON st.exercise_id = se.exercise_id
        JOIN strength_sessions ss ON se.session_id = ss.session_id
        WHERE se.name = %s
          AND ss.session_date = (
              SELECT MAX(ss2.session_date)
              FROM strength_exercises se2
              JOIN strength_sessions ss2 ON se2.session_id = ss2.session_id
              WHERE se2.name = %s
          )
        ORDER BY st.set_number
    """, (name, name))
    rows = cur.fetchall()
    return rows if rows else None


_MED_BALL = {"Med Ball Chest-to-Ground Throws", "Med Ball Twist Throws"}


def _build_set_suggestion(name, pattern, quality_focus, bilateral, last_perf, is_light):
    """
    Returns a suggestion dict: sets, reps (or duration), weight string, note.

    Progression rules:
      power + BW plyo      → never add weight, quality focus
      power + weighted     → same reps, increase weight when 5 reps feels easy
      power + band         → maintain band, lighter when ready
      med ball             → fixed implement, no progression
      strength + BW        → reps → 15, then add weight
      strength + weighted  → 6-10 scheme, +2.5kg when all sets ≥ 8 reps
      stability            → maintain reps/duration
    """
    # Unpack last performance
    # Columns: set_number, reps, duration_seconds, weight_kg, total_weight_kg,
    #          is_bodyweight, band_color, per_hand, per_side
    is_bw    = bool(last_perf and last_perf[0][5])
    band     = last_perf[0][6] if last_perf else None
    wkg      = last_perf[0][3] if last_perf else None   # weight_kg (per-hand when per_hand=True)
    per_hand = bool(last_perf and last_perf[0][7])
    # Use per-hand weight for display/progression; total for single-implement exercises
    base_w   = wkg  # already per-hand when per_hand=True
    reps_list = [r[1] for r in last_perf if r[1] is not None] if last_perf else []
    dur_list  = [r[2] for r in last_perf if r[2] is not None] if last_perf else []

    avg_reps = sum(reps_list) / len(reps_list) if reps_list else None
    min_reps = min(reps_list) if reps_list else None

    # Set counts by quality and day intensity
    if quality_focus == "power":
        n_sets = 4 if is_light else 5
    elif quality_focus in ("strength", "hypertrophy"):
        n_sets = 3 if is_light else 4
    else:  # stability / isolation / endurance
        n_sets = 2 if is_light else 3

    def fmt_w(w):
        """Format weight for display: always per-hand value with /hand suffix when applicable."""
        if w is None:
            return "start light"
        return f"{w:g}kg" + ("/hand" if per_hand else "")

    # ── POWER ──────────────────────────────────────────────────────────────
    if quality_focus == "power":
        target_reps = int(avg_reps) if avg_reps else 4

        if name in _MED_BALL:
            return {"name": name, "sets": n_sets, "reps": target_reps,
                    "weight_str": "med ball", "note": "focus on speed and distance"}

        if is_bw:
            return {"name": name, "sets": n_sets, "reps": target_reps,
                    "weight_str": "BW",
                    "note": "focus on height / distance / reactive contact time"}

        if band:
            return {"name": name, "sets": n_sets, "reps": target_reps,
                    "weight_str": f"band({band})",
                    "note": "move to lighter band when reps feel explosive and easy"}

        # Weighted power (DB Squat Double Jumps, Explosive BB Row, …)
        return {"name": name, "sets": n_sets, "reps": target_reps,
                "weight_str": fmt_w(base_w),
                "note": "increase weight when 5 reps feels consistently easy (RPE ≤ 7)"}

    # ── STABILITY / ISOLATION ───────────────────────────────────────────────
    if quality_focus in ("stability", "endurance") or pattern == "isolation":
        if dur_list:
            avg_dur = int(sum(dur_list) / len(dur_list))
            w_str = "BW" if is_bw else fmt_w(base_w)
            return {"name": name, "sets": n_sets, "reps": None,
                    "duration": avg_dur, "weight_str": w_str, "note": ""}
        r = int(avg_reps) if avg_reps else 12
        w_str = ("BW" if is_bw
                 else f"band({band})" if band
                 else fmt_w(base_w))
        return {"name": name, "sets": n_sets, "reps": r, "weight_str": w_str, "note": ""}

    # ── STRENGTH / HYPERTROPHY ──────────────────────────────────────────────
    upper_threshold = 10 if quality_focus == "hypertrophy" else 8
    bw_rep_limit    = 15

    if not last_perf:
        return {"name": name, "sets": n_sets, "reps": 6,
                "weight_str": "start light", "note": "no history — start conservative"}

    if is_bw:
        if avg_reps and avg_reps >= bw_rep_limit:
            return {"name": name, "sets": n_sets, "reps": 8,
                    "weight_str": "+2.5kg",
                    "note": f"hit {bw_rep_limit} reps — time to add weight, aim for 8 reps"}
        suggest_reps = int(avg_reps) + 1 if avg_reps else bw_rep_limit - 3
        return {"name": name, "sets": n_sets, "reps": suggest_reps,
                "weight_str": "BW",
                "note": f"build to {bw_rep_limit} reps before adding weight"}

    if band:
        r = int(avg_reps) if avg_reps else 8
        return {"name": name, "sets": n_sets, "reps": r,
                "weight_str": f"band({band})", "note": ""}

    # Weighted strength: 6-10 scheme
    # base_w is per-hand when per_hand=True; add 2.5/hand on progression
    if min_reps is not None and min_reps >= upper_threshold:
        suggest_w = (base_w or 0) + 2.5
        note = f"+2.5kg{'/ hand' if per_hand else ''} (was {fmt_w(base_w)}) — aim for 6+ reps"
        r    = 6
    elif min_reps is not None and min_reps < 6:
        suggest_w = max((base_w or 0) - 2.5, 0)
        note = f"consider dropping to {fmt_w(suggest_w)} (fell below 6 reps last time)"
        r    = 8
    else:
        suggest_w = base_w
        r    = int(avg_reps) + 1 if avg_reps else 6
        note = f"add a rep (last avg: {avg_reps:.1f})" if avg_reps else ""
    return {"name": name, "sets": n_sets, "reps": r,
            "weight_str": fmt_w(suggest_w), "note": note}


# Athlete sport priority profile — weights 1-5
ATHLETE_SPORTS = {
    "xc_mtb":    5,
    "trail_run": 5,
    "climbing":  4,
    "ski":       2,
    "snowboard": 1,
}


def get_muscle_importance(cur):
    """
    Derives muscle importance from exercises table: for each muscle that appears
    as primary in any exercise, compute a weighted sport relevance score using
    ATHLETE_SPORTS × sport_carryover. Returns dict: muscle → importance score.
    """
    cur.execute("""
        SELECT primary_muscles, sport_carryover
        FROM exercises
        WHERE primary_muscles IS NOT NULL AND sport_carryover IS NOT NULL
    """)
    rows = cur.fetchall()

    totals = {}
    counts = {}
    for muscles, carryover in rows:
        if not muscles or not carryover:
            continue
        sport_score = sum(
            ATHLETE_SPORTS.get(sport, 0) * float(val)
            for sport, val in carryover.items()
        )
        for m in muscles:
            totals[m] = totals.get(m, 0) + sport_score
            counts[m] = counts.get(m, 0) + 1

    return {m: totals[m] / counts[m] for m in totals}


def get_weekly_muscle_frequency(cur, today):
    """
    Returns dict: muscle → number of gym sessions in the last 7 days
    where that muscle appeared as a primary muscle.
    """
    since = today - timedelta(days=7)
    cur.execute("""
        SELECT DISTINCT ss.session_date, e.primary_muscles
        FROM strength_sessions ss
        JOIN strength_exercises se ON se.session_id = ss.session_id
        JOIN exercises e ON e.name = se.name
        WHERE ss.user_id = 1
          AND ss.session_date >= %s AND ss.session_date < %s
          AND e.primary_muscles IS NOT NULL
    """, (since, today))
    rows = cur.fetchall()

    freq = {}
    for session_date, muscles in rows:
        for m in (muscles or []):
            freq[m] = freq.get(m, 0) + 1
    return freq


_UPPER_MUSCLES = {
    "chest", "front_delt", "side_delt", "rear_delt",
    "biceps", "triceps", "forearms",
    "upper_back", "lats", "rhomboids", "traps",
}
_LOWER_MUSCLES = {
    "quads", "hamstrings", "hip_flexors", "hip_abductors", "hip_adductors",
    "glutes", "calves", "tibialis", "peroneals",
}
# abs/obliques/lower_back are core — valid in both sessions
_SESSION_MUSCLE_FILTER = {
    "upper": _UPPER_MUSCLES | {"abs", "obliques"},
    "lower": _LOWER_MUSCLES | {"lower_back", "abs", "obliques"},
}


def get_exercise_suggestions(cur, gym_rec, today):
    """
    Selects 5 exercises for the recommended gym session.
    Filters by session type (upper/lower muscle region), uses deficit scoring
    weighted by quality fit (heavy vs light), and enforces within-session
    muscle overlap limit.
    """
    if not gym_rec:
        return []

    focus_patterns  = gym_rec["focus"]
    is_light        = gym_rec["intensity"] == "light"
    session_type    = gym_rec.get("session_type", "upper")
    allowed_muscles = _SESSION_MUSCLE_FILTER.get(session_type, _UPPER_MUSCLES)

    placeholders = ",".join(["%s"] * len(focus_patterns))
    cur.execute(f"""
        SELECT e.name, e.movement_pattern, e.quality_focus, e.cns_load,
               e.bilateral, e.primary_muscles, MAX(ss.session_date) AS last_done,
               e.contraction_type
        FROM exercises e
        LEFT JOIN strength_exercises se ON se.name = e.name
        LEFT JOIN strength_sessions ss ON ss.session_id = se.session_id
        WHERE e.movement_pattern IN ({placeholders})
        GROUP BY e.exercise_id, e.name, e.movement_pattern,
                 e.quality_focus, e.cns_load, e.bilateral, e.primary_muscles,
                 e.contraction_type
        ORDER BY (MAX(ss.session_date) IS NOT NULL) DESC,
                 CASE WHEN MAX(ss.session_date) >= %s THEN 0 ELSE 1 END DESC,
                 MAX(ss.session_date) DESC NULLS LAST
    """, focus_patterns + [today - timedelta(days=5)])

    # Filter to muscles appropriate for this session type
    candidates = [
        row for row in cur.fetchall()
        if not row[5] or bool(set(row[5]) & allowed_muscles)
    ]

    # Muscle importance and weekly frequency for deficit scoring
    importance      = get_muscle_importance(cur)
    weekly_freq     = get_weekly_muscle_frequency(cur, today)
    muscle_fresh    = get_muscle_freshness(cur, today)
    target_freq     = {m: max(1, round(score / 6)) for m, score in importance.items()}

    def deficit_score(muscles):
        """Higher = these muscles need work more urgently this week."""
        if not muscles:
            return 0
        return sum(
            max(0, target_freq.get(m, 1) - weekly_freq.get(m, 0)) * importance.get(m, 1)
            for m in muscles
        )

    def avg_freshness(muscles):
        """Mean freshness across primary muscles — prefer recovered muscles."""
        if not muscles:
            return 1.0
        scores = [muscle_fresh.get(m, 1.0) for m in muscles]
        return sum(scores) / len(scores)

    # On heavy days: prefer power/strength quality exercises
    # On light days: prefer strength/stability, deprioritise power
    def quality_fit(qf):
        if is_light:
            return {"power": 1, "strength": 2, "hypertrophy": 2,
                    "stability": 1, "endurance": 1}.get(qf, 1)
        else:
            return {"power": 2, "strength": 2, "hypertrophy": 1,
                    "stability": 0, "endurance": 0}.get(qf, 1)

    def familiar_factor(last_done):
        """Exercises never logged score 10× lower — prefer known movements."""
        return 1.0 if last_done is not None else 0.1

    def recency_factor(last_done):
        """Penalise exercises done in the last 7 days — you just did them this cycle."""
        if last_done is None:
            return 1.0
        days_ago = (today - last_done).days
        if days_ago <= 7:
            return 0.2   # done this week: strongly deprioritise
        if days_ago <= 14:
            return 0.8   # done last week: slight nudge away
        return 1.0

    # Rank: deficit × quality_fit × freshness × familiar × recency
    ranked = sorted(
        candidates,
        key=lambda r: -(
            deficit_score(r[5] or [])
            * quality_fit(r[2])
            * avg_freshness(r[5] or [])
            * familiar_factor(r[6])
            * recency_factor(r[6])
        ),
    )

    selected         = []
    session_muscles  = set()
    used_names       = set()
    covered_patterns = set()

    def _add(row, check_overlap=False):
        name, pattern, qf, cns, bilateral, muscles, last_done, ct = row
        if name in used_names:
            return False
        muscles = muscles or []
        if check_overlap and len(set(muscles) & session_muscles) >= 2:
            return False
        selected.append(row)
        session_muscles.update(muscles)
        used_names.add(name)
        covered_patterns.add(pattern)
        return True

    # Phase 0: guarantee one explosive opener (contraction_type = 'explosive')
    for row in ranked:
        if row[7] == "explosive" and _add(row):
            break

    # Phase 1: guarantee one exercise per remaining focus pattern, no overlap check
    for focus_pattern in focus_patterns:
        if focus_pattern in covered_patterns:
            continue
        for row in ranked:
            if row[1] == focus_pattern and _add(row):
                break

    # Phase 2: fill up to 5 total — overlap check active to avoid redundancy
    for row in ranked:
        if len(selected) >= 5:
            break
        _add(row, check_overlap=True)

    _ORDER = {"power": 0, "strength": 1, "hypertrophy": 1, "stability": 2,
              "endurance": 2, "isolation": 2}

    suggestions = []
    for name, pattern, qf, cns, bilateral, muscles, last_done, ct in selected:
        last_perf = get_last_performance(cur, name)
        s = _build_set_suggestion(name, pattern, qf, bilateral, last_perf, is_light)
        s["pattern"]   = pattern
        s["quality"]   = qf
        s["last_done"] = last_done
        s["_order"]    = _ORDER.get(qf, 1) if qf != "isolation" else _ORDER.get(pattern, 2)
        suggestions.append(s)

    suggestions.sort(key=lambda x: x["_order"])
    for s in suggestions:
        del s["_order"]

    return suggestions


def get_consecutive_training_days(cur, today):
    """How many days in a row has there been some training activity."""
    count = 0
    check = today - timedelta(days=1)
    for _ in range(14):
        cur.execute("""
            SELECT 1 FROM workouts WHERE user_id = 1 AND workout_date = %s
            UNION
            SELECT 1 FROM strength_sessions WHERE user_id = 1 AND session_date = %s
        """, (check, check))
        if cur.fetchone():
            count += 1
            check -= timedelta(days=1)
        else:
            break
    return count


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def apply_blocks(readiness, yesterday, weather):
    """
    Returns a dict of blocked options with reasons.
    Keys: run, trail_run, bike, climb, gym_upper, gym_lower, intensity
    """
    blocks = {}
    yesterday_type = yesterday.get("session_type")

    # Hard block: lower body gym yesterday → no running, no lower gym
    if yesterday_type == "lower":
        blocks["run"]       = "Lower body gym yesterday — legs need recovery"
        blocks["trail_run"] = "Lower body gym yesterday — legs need recovery"
        blocks["gym_lower"] = "Lower body gym yesterday — need at least 48h before next lower session"

    # Hard block: upper body gym yesterday → no climbing, no upper gym
    if yesterday_type == "upper":
        blocks["climb"]     = "Upper body gym yesterday — joints and ligaments need recovery"
        blocks["gym_upper"] = "Upper body gym yesterday — need at least 48h before next upper session"

    # Readiness gates
    if readiness:
        if readiness["legs"] and readiness["legs"] <= 4:
            blocks["run"]       = "Legs feel too poor for running"
            blocks["trail_run"] = "Legs feel too poor for running"
            blocks["gym_lower"] = blocks.get("gym_lower", f"Legs feel poor ({readiness['legs']}/10) — skip lower gym")
            blocks["bike"]      = blocks.get("bike", "Legs feel poor — easy Z2 only if biking")

        if readiness["upper"] and readiness["upper"] <= 4:
            blocks["climb"]     = f"Upper body feel too poor for climbing ({readiness['upper']}/10)"
            blocks["gym_upper"] = blocks.get("gym_upper", f"Upper body feel too poor ({readiness['upper']}/10) — skip upper gym")

        if readiness["joints"] and readiness["joints"] <= 4:
            blocks["run"]       = f"Joint/injury feel too low ({readiness['joints']}/10)"
            blocks["trail_run"] = f"Joint/injury feel too low ({readiness['joints']}/10)"
            blocks["climb"]     = f"Joint/injury feel too low ({readiness['joints']}/10)"
            blocks["gym_upper"] = blocks.get("gym_upper", f"Joint feel too low ({readiness['joints']}/10) — skip upper gym")
            blocks["gym_lower"] = blocks.get("gym_lower", f"Joint feel too low ({readiness['joints']}/10) — skip lower gym")

        if readiness["overall"] and readiness["overall"] <= 3:
            blocks["intensity"] = "Overall feel very low — rest or easy Z2 only"
            blocks["gym_upper"] = blocks.get("gym_upper", "Overall feel too low for gym")
            blocks["gym_lower"] = blocks.get("gym_lower", "Overall feel too low for gym")

    # Weather gates
    if weather:
        if weather["rain"] and weather["rain"] > 0.5:
            blocks["trail_run"]   = "Rain — technical trail too risky"
            blocks["xc_mtb"]      = "Rain — muddy and slippery on MTB"
            blocks["intensity"]   = blocks.get("intensity", "Rain — avoid threshold outdoor sessions")

        if weather["temp"] and weather["temp"] > 30:
            blocks["intensity"] = blocks.get("intensity", "Extreme heat — no high intensity outdoors")

    return blocks


# Complete movement pattern templates per session type.
# Heavy/light does NOT change which patterns are trained —
# it changes the quality_focus preference within each pattern
# (handled in get_exercise_suggestions via CNS scoring).
_SESSION_TEMPLATES = {
    # Upper/Lower (4x/week)
    "upper": ["push_h", "pull_v", "pull_h", "push_v", "isolation"],
    "lower": ["plyo", "hinge", "squat", "stability", "isolation"],
    # Push/Pull/Legs (3x/week) — future
    "push":  ["push_h", "push_v", "isolation"],
    "pull":  ["pull_v", "pull_h", "isolation"],
    "legs":  ["plyo", "hinge", "squat", "stability", "isolation"],
    # Full Body (2x/week) — future
    "full":  ["push_h", "pull_v", "hinge", "squat", "stability"],
}


def _describe_gym_day(gym_type, gym_analysis, today, tsb=0):
    """
    Returns the session descriptor: intensity (heavy/light), focus patterns, label, why.
    Patterns are always the full template for the session type.
    TSB modulates the heavy/light decision alongside last-session CNS.
    """
    focus = _SESSION_TEMPLATES.get(gym_type, _SESSION_TEMPLATES["upper"])
    sessions = gym_analysis.get(gym_type, [])

    if not sessions:
        return {
            "intensity":    "moderate",
            "focus":        focus,
            "focus_label":  "First session — moderate intensity",
            "why":          f"No {gym_type} gym history — start moderate",
            "session_type": gym_type,
        }

    last           = sessions[0]
    cns            = last["cns_total"]
    threshold      = 15 if gym_type == "upper" else 13
    last_was_heavy = cns >= threshold

    # TSB override: very fresh → push even if last was heavy;
    #               overreached → back off even if last was light
    if tsb > 10:
        last_was_heavy = False   # form is high — can push again
    elif tsb < -15:
        last_was_heavy = True    # overreached — force light regardless

    tsb_label, _ = tsb_intensity_hint(tsb)

    if gym_type == "upper":
        pushes = last["patterns"].get("push_h", 0) + last["patterns"].get("push_v", 0)
        pulls  = last["patterns"].get("pull_h", 0) + last["patterns"].get("pull_v", 0)
        if last_was_heavy:
            emphasis  = "pull-dominant" if pushes >= pulls else "push-dominant"
            label     = f"Full upper — {emphasis} emphasis"
            why       = f"CNS {cns} last upper + TSB {tsb:+.0f} ({tsb_label}) — light day, {emphasis}"
            intensity = "light"
        else:
            label     = "Full upper — heavy, balanced push + pull"
            why       = f"CNS {cns} last upper + TSB {tsb:+.0f} ({tsb_label}) — heavy day, full push + pull"
            intensity = "heavy"

    else:  # lower
        if last_was_heavy:
            label     = "Full lower — strength + stability focus"
            why       = f"CNS {cns} last lower + TSB {tsb:+.0f} ({tsb_label}) — strength/stability emphasis"
            intensity = "light"
        else:
            label     = "Full lower — power + strength focus"
            why       = f"CNS {cns} last lower + TSB {tsb:+.0f} ({tsb_label}) — power/strength day"
            intensity = "heavy"

    return {
        "intensity":    intensity,
        "focus":        focus,
        "focus_label":  label,
        "why":          why,
        "session_type": gym_type,
    }


def _days_since(last_date, today):
    """Returns number of days since last_date, or 99 if None."""
    if last_date is None:
        return 99
    return (today - last_date).days


def _pick_gym_type(gym_analysis, today):
    """
    Decides upper or lower based on which was done most recently.
    Returns 'upper' or 'lower'.
    """
    last_upper_date = gym_analysis["upper"][0]["date"] if gym_analysis["upper"] else None
    last_lower_date = gym_analysis["lower"][0]["date"] if gym_analysis["lower"] else None

    days_upper = _days_since(last_upper_date, today)
    days_lower = _days_since(last_lower_date, today)

    # Alternate: do whichever was done longer ago
    if days_upper < days_lower:
        return "lower"
    elif days_lower < days_upper:
        return "upper"
    return "upper"  # tie-break: upper


def build_recommendation(readiness, yesterday, sleep, weather, load, consecutive_days, gym_analysis, today, tl_metrics):
    """
    Core decision logic. Returns a recommendation dict.
    """
    tsb = tl_metrics["tsb"]
    blocks = apply_blocks(readiness, yesterday, weather)
    yesterday_type = yesterday.get("session_type", "rest")
    time_available = readiness["time"] if readiness else "medium"

    # Force rest if needed
    if consecutive_days >= 6:
        return {
            "primary":    "Rest Day",
            "intensity":  None,
            "duration":   None,
            "why":        f"You've trained {consecutive_days} days in a row — a rest day is not optional.",
            "avoid":      [],
            "notes":      [],
        }

    if readiness and readiness["overall"] and readiness["overall"] <= 3:
        return {
            "primary":   "Rest or very easy Z2 bike (20-30 min)",
            "intensity": "Z1/Z2",
            "duration":  "20-30 min",
            "why":       f"Overall feel is {readiness['overall']}/10 — your body is telling you something. Active recovery at most.",
            "avoid":     list(blocks.keys()),
            "notes":     [],
        }

    notes = []
    avoid = []

    # Sleep quality warning
    if sleep:
        if sleep["score"] and sleep["score"] < 60:
            notes.append(f"Poor sleep score ({sleep['score']:.0f}) — keep intensity conservative today")
        if sleep["hrv_status"] and sleep["hrv_status"] in ("UNBALANCED", "LOW"):
            notes.append(f"HRV status is {sleep['hrv_status']} — body still under stress")
        if sleep["body_battery"] and sleep["body_battery"] < 20:
            notes.append(f"Body battery only recovered {sleep['body_battery']} points overnight — take it easy")

    # Going out tonight warning
    if readiness and readiness["going_out"]:
        notes.append("You're going out tonight — keep today's session moderate, don't dig a hole")

    # Running load warning (10% weekly ramp rule)
    if load["run_km"] > 0:
        notes.append(f"Running load this week: {load['run_km']:.1f} km — stay within 10% increase week over week")

    # Gym urgency: days since last session of each type
    last_upper_date = gym_analysis["upper"][0]["date"] if gym_analysis["upper"] else None
    last_lower_date = gym_analysis["lower"][0]["date"] if gym_analysis["lower"] else None
    days_since_upper = _days_since(last_upper_date, today)
    days_since_lower = _days_since(last_lower_date, today)

    gym_rec = None  # will hold gym day description if gym is recommended

    # After lower gym day
    if yesterday_type == "lower":
        avoid.append("Running (lower body recovery)")
        # Upper gym is fresh candidate — check if overdue
        if time_available != "short" and "gym_upper" not in blocks and days_since_upper >= 2:
            gym_rec = _describe_gym_day("upper", gym_analysis, today, tsb)
            primary  = f"Upper Gym — {gym_rec['focus_label']}"
            intensity = gym_rec["intensity"].capitalize()
            duration  = "60-90 min"
            why = gym_rec["why"] + f" (last upper: {days_since_upper}d ago)"
        elif time_available == "short":
            primary = "Easy Z2 Stationary Bike (20-30 min)"
            intensity = "Z2"
            duration = "20-30 min"
            why = "Lower body trained yesterday. Short window — easy spin, legs moving without stress."
        else:
            primary = "Easy Z2 Stationary Bike (45-60 min)"
            intensity = "Z2"
            duration = "45-60 min"
            why = "Lower body trained yesterday. Bike keeps aerobic stimulus without impacting recovering legs."

    # After upper gym day
    elif yesterday_type == "upper":
        avoid.append("Climbing (upper body/joint recovery)")
        # Lower gym is fresh candidate — check if overdue
        if time_available != "short" and "gym_lower" not in blocks and days_since_lower >= 2:
            gym_rec = _describe_gym_day("lower", gym_analysis, today, tsb)
            primary  = f"Lower Gym — {gym_rec['focus_label']}"
            intensity = gym_rec["intensity"].capitalize()
            duration  = "60-90 min"
            why = gym_rec["why"] + f" (last lower: {days_since_lower}d ago)"
        elif time_available == "short":
            primary = "Easy Z2 Stationary Bike (20-30 min)"
            intensity = "Z2"
            duration = "20-30 min"
            why = "Upper body trained yesterday. Short window — easy bike, lower body only."
        elif time_available == "medium":
            primary = "Road Run (flat, easy pace)"
            intensity = "Z2"
            duration = "30-40 min"
            why = "Upper body trained yesterday — legs are fresh. Easy flat run to build the aerobic base."
        else:
            primary = "Road Run or Outdoor Bike (flat, easy)"
            intensity = "Z2"
            duration = "45-60 min"
            why = "Upper body trained yesterday — legs are fresh and ready. Good window for base building."

    # After sport day or rest — full menu including gym
    else:
        # Determine whether gym is the priority
        gym_type_candidate = _pick_gym_type(gym_analysis, today)
        gym_block_key = f"gym_{gym_type_candidate}"
        days_since_gym = days_since_upper if gym_type_candidate == "upper" else days_since_lower
        gym_is_priority = days_since_gym >= 2 and gym_block_key not in blocks

        if time_available == "short":
            primary = "Easy Z2 Stationary Bike (30 min)"
            intensity = "Z2"
            duration = "30 min"
            why = "Short window — stationary bike is the lowest friction option. Still moves the aerobic needle."

        elif time_available == "medium":
            if gym_is_priority:
                gym_rec = _describe_gym_day(gym_type_candidate, gym_analysis, today, tsb)
                primary  = f"{gym_type_candidate.capitalize()} Gym — {gym_rec['focus_label']}"
                intensity = gym_rec["intensity"].capitalize()
                duration  = "60-90 min"
                why = gym_rec["why"] + f" (last {gym_type_candidate}: {days_since_gym}d ago)"
            elif "climb" not in blocks and readiness and readiness["upper"] and readiness["upper"] >= 7:
                primary = "Bouldering (technique focus)"
                intensity = "Moderate"
                duration = "1.5-2 hrs"
                why = "Fresh day, good upper body feel, medium window — good day for technical climbing work."
            elif "run" not in blocks:
                primary = "Road Run (flat, easy)"
                intensity = "Z2"
                duration = "30-40 min"
                why = "Fresh day, medium window — easy flat run to build the running base back up."
            else:
                primary = "Easy Z2 Stationary Bike (45 min)"
                intensity = "Z2"
                duration = "45 min"
                why = "Other options blocked — stationary bike keeps the aerobic work going."

        else:  # long
            if gym_is_priority:
                gym_rec = _describe_gym_day(gym_type_candidate, gym_analysis, today, tsb)
                primary  = f"{gym_type_candidate.capitalize()} Gym — {gym_rec['focus_label']}"
                intensity = gym_rec["intensity"].capitalize()
                duration  = "75-105 min"
                why = gym_rec["why"] + f" (last {gym_type_candidate}: {days_since_gym}d ago)"
            elif "run" not in blocks and "trail_run" not in blocks:
                primary = "Road Run or Trail Run (easy pace)"
                intensity = "Z2"
                duration = "45-75 min"
                why = "Fresh day, long window — best opportunity for a longer aerobic run. Keep it easy, build the base."
            elif "climb" not in blocks:
                primary = "Bouldering + Z2 Bike"
                intensity = "Moderate + Z2"
                duration = "2-3 hrs total"
                why = "Fresh day, long window — combine climbing with a bike session for full training coverage."
            else:
                primary = "Long Z2 Bike (outdoor or stationary)"
                intensity = "Z2"
                duration = "60-90 min"
                why = "Fresh day, long window — solid base building ride."

    return {
        "primary":   primary,
        "intensity": intensity,
        "duration":  duration,
        "why":       why,
        "avoid":     avoid,
        "notes":     notes,
        "blocks":    blocks,
        "gym_rec":   gym_rec,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_recommendation(rec, exercises, readiness, sleep, yesterday, load, today, weather, tl_metrics, hrv_status, active_alerts):
    width = 52
    print("\n" + "=" * width)
    print(f"  TRAINING RECOMMENDATION — {today.strftime('%d.%m.%Y')}")
    print("=" * width)

    # Critical alerts go at the very top — before the recommendation
    critical = [a for a in active_alerts if a[0] == "critical"]
    if critical:
        print()
        for _, msg in critical:
            print(f"  ⚠  {msg}")

    print(f"\n  TODAY: {rec['primary']}")
    if rec["intensity"]:
        print(f"  Intensity : {rec['intensity']}")
    if rec["duration"]:
        print(f"  Duration  : {rec['duration']}")

    print(f"\n  Why: {rec['why']}")

    if exercises:
        print()
        for i, ex in enumerate(exercises, 1):
            dur = ex.get("duration")
            if dur:
                reps_str = f"{ex['sets']} × {dur}s"
            else:
                reps_str = f"{ex['sets']} × {ex['reps']}"
            line = f"  {i}. {ex['name']:<46} {reps_str}  @  {ex['weight_str']}"
            print(line)
            if ex.get("note"):
                print(f"     → {ex['note']}")

    if rec.get("avoid"):
        print("\n  Avoid today:")
        for a in rec["avoid"]:
            print(f"    - {a}")

    if rec.get("notes"):
        print("\n  Heads up:")
        for n in rec["notes"]:
            print(f"    ! {n}")

    # Readiness summary
    if readiness:
        print(f"\n  Readiness  : overall {readiness['overall']}/10  "
              f"legs {readiness['legs']}/10  "
              f"upper {readiness['upper']}/10  "
              f"joints {readiness['joints']}/10")
        if readiness["injury_note"]:
            print(f"  Injury note: {readiness['injury_note']}")
        print(f"  Time       : {readiness['time']}  |  "
              f"Going out: {'yes' if readiness['going_out'] else 'no'}")

    # Sleep + HRV summary
    if sleep and sleep["duration"]:
        score_str = f"  score {sleep['score']:.0f}" if sleep["score"] else ""
        bb_str    = f"  battery +{sleep['body_battery']}" if sleep["body_battery"] else ""
        if hrv_status["status"] != "no_data":
            dev_sign   = "+" if hrv_status["deviation"] >= 0 else ""
            trend_arrow = {"rising": " ↗", "falling": " ↘", "stable": ""}.get(hrv_status["trend"], "")
            hrv_str    = (f"  HRV {hrv_status['last_hrv']:.0f} "
                          f"({dev_sign}{hrv_status['deviation']:.1f}SD "
                          f"{hrv_status['status']}{trend_arrow})")
        else:
            hrv_str = f"  HRV {sleep['hrv']:.0f}" if sleep.get("hrv") else ""
        print(f"\n  Last night : {sleep['duration']} min sleep{score_str}{hrv_str}{bb_str}")
    elif sleep:
        print(f"\n  Last night : Garmin still processing sleep data")

    # Yesterday summary
    yday_label = yesterday.get("label") or yesterday.get("session_type", "Rest")
    print(f"  Yesterday  : {yday_label}")

    # Weather
    if weather:
        rain_str = f"  rain {weather['rain']} mm" if weather.get("rain") and weather["rain"] > 0 else "  no rain"
        print(f"  Weather    : {weather['temp']:.1f}°C  wind {weather['wind']:.1f} m/s{rain_str}")

    # Weekly load
    if load["run_km"] > 0 or load["bike_min"] > 0:
        parts = []
        if load["run_km"] > 0:
            parts.append(f"run {load['run_km']:.1f} km")
        if load["bike_min"] > 0:
            parts.append(f"bike {load['bike_min']:.0f} min")
        if load["climb_sessions"] > 0:
            parts.append(f"climb {load['climb_sessions']}x")
        print(f"  This week  : {', '.join(parts)}")

    # Training load metrics + interpretations
    tsb_label, _ = tsb_intensity_hint(tl_metrics["tsb"])
    ramp_str = f"  ramp {tl_metrics['ramp_rate']:+.1f}/wk" if tl_metrics["ramp_rate"] != 0 else ""
    print(f"  Fitness    : CTL {tl_metrics['ctl']:.0f}  ATL {tl_metrics['atl']:.0f}  "
          f"TSB {tl_metrics['tsb']:+.0f} ({tsb_label}){ramp_str}")

    interpretations = interpret_metrics(tl_metrics, hrv_status)
    if interpretations:
        print()
        for line in interpretations:
            print(f"  → {line}")

    # Warnings (non-critical alerts)
    warnings = [a for a in active_alerts if a[0] in ("warning", "info")]
    if warnings:
        print()
        for sev, msg in warnings:
            prefix = "⚡" if sev == "warning" else "ℹ"
            print(f"  {prefix}  {msg}")

    print("\n" + "=" * width + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_date(s):
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.strptime(f"{s}.2026", "%d.%m.%Y").date()
    except ValueError:
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date to recommend for (DD.MM or DD.MM.YYYY)")
    args = parser.parse_args()

    today = parse_date(args.date) if args.date else date.today()
    if not today:
        print("Invalid date.")
        sys.exit(1)

    yesterday = today - timedelta(days=1)

    conn = get_connection()
    cur  = conn.cursor()

    readiness         = get_readiness(cur, today)
    yesterday_session = get_yesterdays_training(cur, yesterday)
    sleep             = get_last_nights_sleep(cur, today)
    weather           = get_latest_weather(cur)
    load              = get_recent_load(cur, today)
    consecutive       = get_consecutive_training_days(cur, today)
    gym_analysis      = get_gym_analysis(cur, today)
    tl_metrics        = get_metrics(cur, today)
    hrv_status        = get_hrv_status(cur, today)
    active_alerts     = get_alerts(cur, today, tl_metrics, hrv_status, readiness)

    cur.close()
    conn.close()

    if not readiness:
        print("\nNo morning check-in found for today.")
        print("Run:  python3 checkin.py\n")
        sys.exit(0)

    rec = build_recommendation(readiness, yesterday_session, sleep, weather, load, consecutive, gym_analysis, today, tl_metrics)

    # Fetch exercise suggestions after rec is built (needs gym_rec from rec)
    conn2 = get_connection()
    cur2  = conn2.cursor()
    exercises = get_exercise_suggestions(cur2, rec.get("gym_rec"), today)
    cur2.close()
    conn2.close()

    print_recommendation(rec, exercises, readiness, sleep, yesterday_session, load, today, weather, tl_metrics, hrv_status, active_alerts)


if __name__ == "__main__":
    main()
