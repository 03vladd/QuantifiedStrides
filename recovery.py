"""
Recovery analytics: HRV trend analysis and per-muscle fatigue decay.

HRV Trend
---------
Compares last night's HRV against a personal 7-day rolling baseline.
Deviation in SD units is a reliable proxy for systemic recovery status —
more robust than raw HRV because it accounts for individual baseline variance.

Muscle Fatigue Decay
--------------------
Models residual fatigue per muscle as an exponential decay:
    fatigue(t) = peak_load × e^(−λ × t_days)

where λ = ln(2) / half_life is muscle-group-specific.
Freshness (0–1) = 1 − clipped(total_fatigue / calibration_cap)

Fatigue is accumulated from TWO sources:
  1. Strength sessions — load = systemic_fatigue × num_sets per exercise
  2. Endurance workouts — load = load_per_hour × duration_hours, sport-specific

Time resolution is fractional days (hours), not integer days, so the graph
moves continuously as the session recedes into the past.

Used by the recommendation engine to prefer muscles that are more recovered
when two exercises score similarly on the main deficit × quality_fit ranking.
"""

import math
from datetime import datetime, timedelta, time as dtime


# ---------------------------------------------------------------------------
# HRV trend
# ---------------------------------------------------------------------------

def get_hrv_status(cur, today, window=7, user_id=1):
    """
    Compare today's HRV against a rolling personal baseline.

    Returns a dict:
        baseline   : rolling mean HRV over last `window` days (excl. today)
        baseline_sd: rolling SD
        last_hrv   : most recent valid HRV reading
        deviation  : (last_hrv − baseline) / baseline_sd  (SD units)
        status     : 'elevated' | 'normal' | 'suppressed' | 'no_data'
        trend      : 'rising' | 'stable' | 'falling'  (3-day vs 7-day mean)
    """
    start = today - timedelta(days=window + 4)
    cur.execute("""
        SELECT sleep_date, overnight_hrv
        FROM sleep_sessions
        WHERE user_id = %s
          AND sleep_date BETWEEN %s AND %s
          AND overnight_hrv IS NOT NULL
        ORDER BY sleep_date
    """, (user_id, start, today))
    rows = cur.fetchall()

    if len(rows) < 3:
        return {"status": "no_data", "last_hrv": None, "baseline": None,
                "baseline_sd": None, "deviation": None, "trend": None}

    last_date, last_hrv = rows[-1]
    baseline_rows = [r[1] for r in rows if r[0] < last_date][-window:]
    if len(baseline_rows) < 3:
        return {"status": "no_data", "last_hrv": last_hrv, "baseline": None,
                "baseline_sd": None, "deviation": None, "trend": None}

    mean  = sum(baseline_rows) / len(baseline_rows)
    sd    = math.sqrt(sum((v - mean) ** 2 for v in baseline_rows) / len(baseline_rows))
    sd    = max(sd, 1.0)

    deviation = (last_hrv - mean) / sd
    if deviation > 0.5:
        status = "elevated"
    elif deviation < -1.0:
        status = "suppressed"
    else:
        status = "normal"

    recent3   = [r[1] for r in rows[-3:]]
    trend_val = sum(recent3) / len(recent3) - mean
    if trend_val > 3:
        trend = "rising"
    elif trend_val < -3:
        trend = "falling"
    else:
        trend = "stable"

    return {
        "baseline":    round(mean, 1),
        "baseline_sd": round(sd, 1),
        "last_hrv":    round(last_hrv, 1),
        "deviation":   round(deviation, 2),
        "status":      status,
        "trend":       trend,
    }


# ---------------------------------------------------------------------------
# Muscle fatigue decay
# ---------------------------------------------------------------------------

# Half-life in days per muscle group — informed by fibre-type literature
_HALF_LIFE = {
    "lower_back":    3.0,
    "hip_flexors":   3.0,
    "lats":          2.5,
    "upper_back":    2.5,
    "rhomboids":     2.5,
    "traps":         2.5,
    "chest":         2.0,
    "quads":         2.0,
    "hamstrings":    2.0,
    "glutes":        2.0,
    "front_delt":    1.5,
    "side_delt":     1.5,
    "rear_delt":     1.5,
    "biceps":        1.5,
    "triceps":       1.5,
    "abs":           1.5,
    "obliques":      1.5,
    "calves":        1.5,
    "forearms":      1.5,
    "hip_abductors": 2.0,
    "hip_adductors": 2.0,
    "tibialis":      1.5,
    "peroneals":     1.5,
}
_DEFAULT_HALF_LIFE = 2.0

# Max accumulated load before freshness hits 0.
# Calibrated to one hard strength session:
#   e.g. 4 exercises × 4 sets × systemic_fatigue 3 = 48 primary load units
# An equivalent long/hard endurance session approaches this from the sport map.
_FATIGUE_CAP = 50.0

# Endurance sport → muscle load map.
# Values are load units per hour of activity, using the same scale as
# strength load = systemic_fatigue × num_sets (typical hard set ≈ 3 units).
# Calibration examples:
#   1-hour easy run    → quads ~8  → 8/50 = 16% fatigue  → 84% fresh  ✓
#   2-hour long run    → quads 16  → 32%  fatigue  → 68% fresh  ✓
#   2-hour bouldering  → forearms 30 → 60% fatigue → 40% fresh  ✓
_SPORT_MUSCLE_MAP: dict[str, dict[str, dict[str, float]]] = {
    "running": {
        "primary":   {"quads": 8.0, "calves": 8.0, "glutes": 5.0},
        "secondary": {"hamstrings": 5.0, "hip_flexors": 5.0, "tibialis": 3.0},
    },
    "trail_running": {
        "primary":   {"quads": 11.0, "calves": 9.0, "glutes": 8.0},
        "secondary": {"hamstrings": 7.0, "hip_flexors": 6.0, "tibialis": 5.0},
    },
    "cycling": {
        "primary":   {"quads": 9.0, "glutes": 5.0},
        "secondary": {"hamstrings": 3.0, "calves": 3.0, "hip_flexors": 4.0},
    },
    "mountain_biking": {
        "primary":   {"quads": 10.0, "glutes": 7.0},
        "secondary": {"hamstrings": 4.0, "calves": 4.0, "hip_flexors": 4.0,
                      "lower_back": 5.0, "abs": 4.0},
    },
    "indoor_cycling": {
        "primary":   {"quads": 8.0, "glutes": 4.0},
        "secondary": {"hamstrings": 3.0, "calves": 3.0, "hip_flexors": 3.0},
    },
    "bouldering": {
        "primary":   {"lats": 12.0, "forearms": 15.0, "biceps": 9.0},
        "secondary": {"upper_back": 7.0, "rhomboids": 6.0,
                      "front_delt": 5.0, "abs": 5.0},
    },
    "climbing": {
        "primary":   {"lats": 12.0, "forearms": 15.0, "biceps": 9.0},
        "secondary": {"upper_back": 7.0, "rhomboids": 6.0,
                      "front_delt": 5.0, "abs": 5.0},
    },
    "hiking": {
        "primary":   {"quads": 4.0, "glutes": 4.0, "calves": 4.0},
        "secondary": {"hamstrings": 3.0, "hip_flexors": 3.0},
    },
    "resort_skiing": {
        "primary":   {"quads": 11.0, "glutes": 7.0},
        "secondary": {"hamstrings": 5.0, "abs": 5.0, "hip_abductors": 6.0},
    },
    "skiing": {
        "primary":   {"quads": 11.0, "glutes": 7.0},
        "secondary": {"hamstrings": 5.0, "abs": 5.0, "hip_abductors": 6.0},
    },
    "snowboarding": {
        "primary":   {"quads": 8.0, "glutes": 7.0},
        "secondary": {"hamstrings": 5.0, "abs": 6.0,
                      "hip_abductors": 5.0, "calves": 4.0},
    },
    "swimming": {
        "primary":   {"lats": 9.0, "triceps": 6.0},
        "secondary": {"biceps": 4.0, "front_delt": 7.0, "rhomboids": 5.0},
    },
}


def _decay(peak: float, half_life: float, t_days: float) -> float:
    lam = math.log(2) / half_life
    return peak * math.exp(-lam * t_days)


def _t_days_from_end(end_dt: datetime, now: datetime) -> float:
    """
    Fractional days elapsed since a workout ended.
    Strips timezone info if present (DB timestamps vs naive datetime.now()).
    Clamped to a minimum of 15 minutes to avoid division artifacts.
    """
    if end_dt.tzinfo is not None:
        end_dt = end_dt.replace(tzinfo=None)
    elapsed = (now - end_dt).total_seconds()
    return max(elapsed / 86400, 15 / 1440)   # min 15 minutes


def get_muscle_freshness(cur, today, lookback: int = 14, user_id: int = 1) -> dict:
    """
    Compute a freshness score (0–1) per muscle based on residual fatigue decay.
    1.0 = fully recovered, 0.0 = maximally fatigued.

    Accumulates fatigue from:
      - strength_sessions (load = systemic_fatigue × num_sets per exercise)
      - workouts (non-strength sports, load = load_per_hour × duration_h)

    Returns dict: muscle → freshness float
    """
    now   = datetime.now()
    start = today - timedelta(days=lookback)
    fatigue: dict[str, float] = {}

    # ── 1. Strength session fatigue ──────────────────────────────────────────
    cur.execute("""
        SELECT ss.session_date,
               e.primary_muscles,
               e.secondary_muscles,
               e.systemic_fatigue,
               COUNT(st.set_id) AS num_sets
        FROM strength_sessions ss
        JOIN strength_exercises se ON se.session_id = ss.session_id
        LEFT JOIN exercises e ON e.name = se.name
        JOIN strength_sets st ON st.exercise_id = se.exercise_id
        WHERE ss.user_id = %s
          AND ss.session_date BETWEEN %s AND %s
        GROUP BY ss.session_date, se.exercise_id,
                 e.primary_muscles, e.secondary_muscles, e.systemic_fatigue
    """, (user_id, start, today))

    for session_date, primary, secondary, systemic, num_sets in cur.fetchall():
        # Strength sessions have date only — assume noon for time resolution
        session_dt = datetime.combine(session_date, dtime(12, 0))
        t_days = _t_days_from_end(session_dt, now)
        load   = float(systemic or 2) * float(num_sets)

        for muscle in (primary or []):
            hl = _HALF_LIFE.get(muscle, _DEFAULT_HALF_LIFE)
            fatigue[muscle] = fatigue.get(muscle, 0.0) + _decay(load, hl, t_days)

        for muscle in (secondary or []):
            hl = _HALF_LIFE.get(muscle, _DEFAULT_HALF_LIFE)
            fatigue[muscle] = fatigue.get(muscle, 0.0) + _decay(load * 0.4, hl, t_days)

    # ── 2. Endurance workout fatigue ─────────────────────────────────────────
    # TSS (Training Stress Score) is used to scale load by intensity:
    #   intensity_factor = (tss / duration_h) / REFERENCE_TSS_PER_HOUR
    # At the reference (60 TSS/h ≈ steady Z2/Z3 effort), factor = 1.0.
    # An easy Z1 run (~40 TSS/h) scales load down to 0.67×.
    # A threshold session (~90 TSS/h) scales load up to 1.5×.
    # Clamped to [0.5, 2.0] to handle outliers and NULL TSS (falls back to 1.0).
    _REFERENCE_TSS_PER_HOUR = 60.0

    cur.execute("""
        SELECT sport,
               end_time,
               workout_date,
               EXTRACT(EPOCH FROM COALESCE(end_time - start_time,
                                           INTERVAL '1 hour'))::float / 3600 AS duration_h,
               training_stress_score::float
        FROM workouts
        WHERE user_id = %s
          AND workout_date BETWEEN %s AND %s
          AND sport != 'strength_training'
    """, (user_id, start, today))

    for sport, end_time, workout_date, duration_h, tss in cur.fetchall():
        muscle_map = _SPORT_MUSCLE_MAP.get(sport)
        if not muscle_map:
            continue

        # Use actual end_time when available; otherwise assume 20:00 that day
        if end_time is not None:
            ref_dt = end_time if isinstance(end_time, datetime) \
                     else datetime.combine(workout_date, end_time)
        else:
            ref_dt = datetime.combine(workout_date, dtime(20, 0))

        t_days     = _t_days_from_end(ref_dt, now)
        duration_h = float(duration_h or 1.0)

        # TSS intensity factor — falls back to 1.0 when TSS is NULL
        if tss and duration_h > 0:
            intensity_factor = float(tss) / duration_h / _REFERENCE_TSS_PER_HOUR
            intensity_factor = max(0.5, min(2.0, intensity_factor))
        else:
            intensity_factor = 1.0

        for muscle, load_per_h in muscle_map.get("primary", {}).items():
            load = load_per_h * duration_h * intensity_factor
            hl   = _HALF_LIFE.get(muscle, _DEFAULT_HALF_LIFE)
            fatigue[muscle] = fatigue.get(muscle, 0.0) + _decay(load, hl, t_days)

        for muscle, load_per_h in muscle_map.get("secondary", {}).items():
            load = load_per_h * duration_h * intensity_factor * 0.4
            hl   = _HALF_LIFE.get(muscle, _DEFAULT_HALF_LIFE)
            fatigue[muscle] = fatigue.get(muscle, 0.0) + _decay(load, hl, t_days)

    # Convert to freshness (1 = fully fresh, 0 = maximally loaded)
    return {
        muscle: round(1.0 - min(1.0, f / _FATIGUE_CAP), 3)
        for muscle, f in fatigue.items()
    }
