"""
analytics/biomechanics.py

Biomechanics analytics computed from workout_metrics time-series.

1. Fatigue Signature
   Compare first 20% vs last 20% of a run:
   - Cadence drift    (steps/min — drops when tired)
   - GCT drift        (ms — rises when tired, heavier footstrike)
   - HR drift         (bpm — rises even at same pace)
   - Pace drift       (min/km — slowing down)
   - VO drift         (cm — oscillation increases with fatigue)

2. Cadence-Speed Relationship
   At each speed band, what is the average cadence?
   Good runners maintain cadence and adjust stride length.
   Overstriding shows as cadence dropping sharply with pace.

3. Per-Workout Biomechanics Summary
   Single-row summary per workout: avg/std of each biomechanics metric.

4. Longitudinal Biomechanics Trends
   Rolling stats over time to see if GCT, cadence, VO are improving.
"""

from __future__ import annotations

from typing import Optional

from db import get_connection


# ---------------------------------------------------------------------------
# Single-workout: fatigue signature
# ---------------------------------------------------------------------------

def get_fatigue_signature(workout_id: int, window_pct: float = 0.20, conn=None) -> Optional[dict]:
    """
    Compare biomechanics in the first `window_pct` vs last `window_pct` of a run.

    window_pct: fraction of the run to use as early/late window (default 20%).

    Returns dict with per-metric drift values, or None if insufficient data.
    Positive drift means the metric increased (e.g. GCT got worse).
    For cadence, negative drift = cadence dropped (bad).
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT metric_timestamp, heart_rate, pace, cadence,
               ground_contact_time, vertical_oscillation
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()

    if close:
        conn.close()

    n = len(rows)
    if n < 50:
        return None

    win = max(10, int(n * window_pct))
    early = rows[:win]
    late  = rows[n - win:]

    def safe_avg(data, idx):
        vals = [r[idx] for r in data if r[idx] is not None]
        return sum(vals) / len(vals) if vals else None

    def drift(early_avg, late_avg):
        if early_avg is None or late_avg is None or early_avg == 0:
            return None
        return round(late_avg - early_avg, 3)

    def drift_pct(early_avg, late_avg):
        if early_avg is None or late_avg is None or early_avg == 0:
            return None
        return round((late_avg - early_avg) / early_avg * 100, 2)

    metrics = {
        "heart_rate":           2,
        "pace":                 3,
        "cadence":              4,
        "ground_contact_time":  5,
        "vertical_oscillation": 6,
    }

    result = {
        "workout_id": workout_id,
        "n_rows":     n,
        "window_pct": window_pct,
        "window_size": win,
    }

    for name, idx in metrics.items():
        # adjust idx: rows are (timestamp, hr, pace, cadence, gct, vo) → indices 1-5
        col_idx = idx - 1   # 0-based into the tuple after timestamp
        early_avg = safe_avg(early, col_idx)
        late_avg  = safe_avg(late,  col_idx)
        result[f"{name}_early"] = round(early_avg, 3) if early_avg is not None else None
        result[f"{name}_late"]  = round(late_avg,  3) if late_avg  is not None else None
        result[f"{name}_drift"] = drift(early_avg, late_avg)
        result[f"{name}_drift_pct"] = drift_pct(early_avg, late_avg)

    # Summary: overall fatigue score (0-100, higher = more fatigued)
    # Combine GCT drift + HR drift + cadence drop (inverted)
    scores = []
    if result.get("ground_contact_time_drift_pct") is not None:
        scores.append(min(100, max(0, result["ground_contact_time_drift_pct"] * 5)))
    if result.get("heart_rate_drift_pct") is not None:
        scores.append(min(100, max(0, result["heart_rate_drift_pct"] * 10)))
    if result.get("cadence_drift_pct") is not None:
        scores.append(min(100, max(0, -result["cadence_drift_pct"] * 10)))

    result["fatigue_score"] = round(sum(scores) / len(scores), 1) if scores else None

    return result


# ---------------------------------------------------------------------------
# Single-workout: cadence-speed relationship
# ---------------------------------------------------------------------------

def get_cadence_speed_profile(workout_id: int, conn=None) -> Optional[list[dict]]:
    """
    Group data points by pace band (0.5 min/km buckets) and compute
    mean cadence for each band.

    Returns list of dicts sorted by pace_band ascending (slow → fast),
    or None if insufficient data.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT pace, cadence
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
          AND cadence IS NOT NULL AND cadence > 0
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()

    if close:
        conn.close()

    if len(rows) < 20:
        return None

    # Bucket by 0.5 min/km bands
    buckets: dict[float, list[float]] = {}
    for pace, cadence in rows:
        band = round(pace * 2) / 2   # nearest 0.5
        if band not in buckets:
            buckets[band] = []
        buckets[band].append(cadence)

    return [
        {
            "pace_band":    band,
            "avg_cadence":  round(sum(vals) / len(vals), 1),
            "count":        len(vals),
        }
        for band, vals in sorted(buckets.items())
        if len(vals) >= 5   # only bands with enough data
    ]


# ---------------------------------------------------------------------------
# Single-workout: biomechanics summary
# ---------------------------------------------------------------------------

def get_workout_biomechanics(workout_id: int, conn=None) -> Optional[dict]:
    """
    Single-row biomechanics summary for a workout.

    Returns averages and std devs for: cadence, GCT, VO, VR, pace, HR.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT
            AVG(cadence)                    AS avg_cadence,
            STDDEV(cadence)                 AS std_cadence,
            AVG(ground_contact_time)        AS avg_gct,
            STDDEV(ground_contact_time)     AS std_gct,
            AVG(vertical_oscillation)       AS avg_vo,
            STDDEV(vertical_oscillation)    AS std_vo,
            AVG(vertical_ratio)             AS avg_vr,
            STDDEV(vertical_ratio)          AS std_vr,
            AVG(pace)                       AS avg_pace,
            AVG(heart_rate)                 AS avg_hr,
            COUNT(*)                        AS n_rows
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
    """, (workout_id,))
    row = cur.fetchone()

    if close:
        conn.close()

    if not row or row[10] == 0:
        return None

    def r(v, digits=3):
        return round(float(v), digits) if v is not None else None

    return {
        "workout_id":   workout_id,
        "avg_cadence":  r(row[0], 1),
        "std_cadence":  r(row[1], 2),
        "avg_gct":      r(row[2], 1),
        "std_gct":      r(row[3], 2),
        "avg_vo":       r(row[4], 2),
        "std_vo":       r(row[5], 3),
        "avg_vr":       r(row[6], 2),
        "std_vr":       r(row[7], 3),
        "avg_pace":     r(row[8], 3),
        "avg_hr":       r(row[9], 1),
        "n_rows":       row[10],
    }


# ---------------------------------------------------------------------------
# Longitudinal trends
# ---------------------------------------------------------------------------

def get_biomechanics_trends(days: int = 365, conn=None) -> list[dict]:
    """
    Per-workout biomechanics summary + fatigue signature for all running
    workouts in the last `days` days, sorted by date.

    Used by both Streamlit and notebooks for trend charts.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT workout_id, workout_date, sport, training_volume
        FROM workouts
        WHERE user_id = 1
          AND sport IN ('running', 'trail_running')
          AND workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY workout_date
    """, (days,))
    workouts = cur.fetchall()
    cur.close()

    results = []
    for wid, wdate, sport, distance_m in workouts:
        try:
            bio = get_workout_biomechanics(wid, conn)
        except Exception:
            conn.rollback()
            bio = None
        try:
            fat = get_fatigue_signature(wid, conn)
        except Exception:
            conn.rollback()
            fat = None

        row = {
            "workout_id":   wid,
            "workout_date": wdate,
            "sport":        sport,
            "distance_km":  round((distance_m or 0) / 1000, 2),
        }

        if bio:
            row.update({
                "avg_cadence": bio["avg_cadence"],
                "avg_gct":     bio["avg_gct"],
                "avg_vo":      bio["avg_vo"],
                "avg_vr":      bio["avg_vr"],
                "avg_pace":    bio["avg_pace"],
                "avg_hr":      bio["avg_hr"],
            })
        else:
            row.update({k: None for k in
                        ["avg_cadence", "avg_gct", "avg_vo", "avg_vr", "avg_pace", "avg_hr"]})

        if fat:
            row.update({
                "fatigue_score":          fat["fatigue_score"],
                "cadence_drift_pct":      fat["cadence_drift_pct"],
                "gct_drift_pct":          fat["ground_contact_time_drift_pct"],
                "hr_drift_pct":           fat["heart_rate_drift_pct"],
            })
        else:
            row.update({k: None for k in
                        ["fatigue_score", "cadence_drift_pct", "gct_drift_pct", "hr_drift_pct"]})

        results.append(row)

    if close:
        conn.close()

    return results
