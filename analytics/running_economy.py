"""
analytics/running_economy.py

Three running economy metrics computed from workout_metrics time-series:

1. Grade-Adjusted Pace (GAP)
   Uses Minetti et al. metabolic cost model to normalise pace for gradient.
   Answers: what was the true aerobic effort, independent of terrain?

2. Aerobic Decoupling
   Compares the pace:HR ratio in the first half vs second half of each run.
   < 5%  → aerobically efficient (strong base)
   5-10% → moderate drift
   > 10% → cardiac drift, base needs work

3. Running Economy Index
   Primary: normalised power / speed  (W / (m/s)) — lower is more efficient.
   Fallback: HR / speed — a proxy when power is unavailable.
   Trend over time reveals whether fitness is translating to efficiency.
"""

from __future__ import annotations

import math
from typing import Optional

from db import get_connection


# ---------------------------------------------------------------------------
# Minetti et al. (2002) metabolic cost of running on slopes
# doi:10.1152/japplphysiol.01177.2001
#
# Cost of transport (J/kg/m) as function of gradient g (dimensionless, not %):
#   Cr(g) = 155.4·g^5 - 30.4·g^4 - 43.3·g^3 + 46.3·g^2 + 19.5·g + 3.6
#
# GAP multiplier = Cr(0) / Cr(g)   →  multiply actual pace by this to get GAP
# ---------------------------------------------------------------------------

def _minetti_cost(g: float) -> float:
    """Metabolic cost of running at gradient g (dimensionless fraction, not %)."""
    return (155.4 * g**5
            - 30.4 * g**4
            - 43.3 * g**3
            + 46.3 * g**2
            + 19.5 * g
            + 3.6)


_FLAT_COST = _minetti_cost(0.0)   # 3.6 J/kg/m


def gap_multiplier(gradient_pct: float) -> float:
    """
    Return the pace multiplier for a given gradient.
    GAP = actual_pace * gap_multiplier(gradient_pct)

    Clamped to ±45% gradient — beyond that Minetti's polynomial is unreliable.
    """
    g = max(-0.45, min(0.45, gradient_pct / 100.0))
    cost = _minetti_cost(g)
    if cost <= 0:
        return 1.0
    return _FLAT_COST / cost


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_workout_gap(workout_id: int, conn=None) -> Optional[dict]:
    """
    Compute Grade-Adjusted Pace summary for a single workout.

    Returns dict:
        workout_id      : int
        avg_pace        : float  (min/km, pace > 0 points only)
        avg_gap         : float  (min/km, gradient-adjusted)
        gap_vs_pace_pct : float  (how much harder terrain made it, %)
        gradient_profile: list of {gradient_pct, count} buckets
        rows_used       : int
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT pace, gradient_pct
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL
          AND pace > 0
          AND pace < 20          -- filter GPS glitches (> 20 min/km)
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()
    if close:
        conn.close()

    if not rows:
        return None

    pace_vals = []
    gap_vals  = []
    bucket_counts = {}

    for pace, grad in rows:
        pace_vals.append(pace)
        if grad is not None:
            multiplier = gap_multiplier(grad)
            gap_vals.append(pace * multiplier)
            # bucket to nearest 2%
            b = round(grad / 2) * 2
            bucket_counts[b] = bucket_counts.get(b, 0) + 1
        else:
            gap_vals.append(pace)   # no gradient → GAP = pace

    avg_pace = sum(pace_vals) / len(pace_vals)
    avg_gap  = sum(gap_vals)  / len(gap_vals)

    gap_vs_pace_pct = ((avg_pace - avg_gap) / avg_gap * 100) if avg_gap > 0 else 0.0

    gradient_profile = [
        {"gradient_pct": k, "count": v}
        for k, v in sorted(bucket_counts.items())
    ]

    return {
        "workout_id":       workout_id,
        "avg_pace":         round(avg_pace, 3),
        "avg_gap":          round(avg_gap, 3),
        "gap_vs_pace_pct":  round(gap_vs_pace_pct, 2),
        "gradient_profile": gradient_profile,
        "rows_used":        len(rows),
    }


def get_aerobic_decoupling(workout_id: int, conn=None) -> Optional[dict]:
    """
    Aerobic decoupling (Pa:HR drift) for a single workout.

    Splits the workout into two equal halves by row count.
    Computes pace:HR ratio for each half.
    Decoupling % = (ratio_first - ratio_second) / ratio_first × 100

    Positive = HR rising faster than pace (cardiac drift / fatigue).
    Negative = getting stronger (unusual, often GPS artefact in short runs).

    Returns dict or None if insufficient data.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT pace, heart_rate
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
          AND heart_rate IS NOT NULL AND heart_rate > 40
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()
    if close:
        conn.close()

    if len(rows) < 40:   # need at least 40 data points for a meaningful split
        return None

    mid   = len(rows) // 2
    first  = rows[:mid]
    second = rows[mid:]

    def pa_hr_ratio(half):
        # pace:HR  →  higher = more efficient (fast pace, low HR)
        # We invert pace (speed = 1/pace in km/min) so higher = better
        speeds = [1.0 / p for p, _ in half]
        hrs    = [h for _, h in half]
        return (sum(speeds) / len(speeds)) / (sum(hrs) / len(hrs))

    ratio_first  = pa_hr_ratio(first)
    ratio_second = pa_hr_ratio(second)

    if ratio_first == 0:
        return None

    decoupling_pct = (ratio_first - ratio_second) / ratio_first * 100

    if decoupling_pct < 5:
        status = "efficient"
    elif decoupling_pct < 10:
        status = "moderate_drift"
    else:
        status = "cardiac_drift"

    return {
        "workout_id":      workout_id,
        "decoupling_pct":  round(decoupling_pct, 2),
        "ratio_first":     round(ratio_first, 6),
        "ratio_second":    round(ratio_second, 6),
        "status":          status,
        "rows_used":       len(rows),
    }


def get_running_economy_index(workout_id: int, conn=None) -> Optional[dict]:
    """
    Running Economy Index for a single workout.

    Primary (power available):
        REI = normalised_power / avg_speed_ms
        Lower REI = more economical (less watts per m/s).

    Fallback (no power):
        REI = avg_HR / avg_speed_ms
        Lower = more economical.

    Speed is derived from pace (min/km → m/s).

    Returns dict or None.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()

    # Try power-based first
    cur.execute("""
        SELECT pace, power
        FROM workout_metrics
        WHERE workout_id = %s
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
          AND power IS NOT NULL AND power > 0
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()

    mode = "power"
    if len(rows) < 20:
        # fallback to HR-based
        cur.execute("""
            SELECT pace, heart_rate
            FROM workout_metrics
            WHERE workout_id = %s
              AND pace IS NOT NULL AND pace > 0 AND pace < 20
              AND heart_rate IS NOT NULL AND heart_rate > 40
            ORDER BY metric_timestamp
        """, (workout_id,))
        rows = cur.fetchall()
        mode = "hr"

    if close:
        conn.close()

    if len(rows) < 20:
        return None

    speeds_ms   = [1000.0 / (p * 60.0) for p, _ in rows]   # pace min/km → m/s
    secondaries = [v for _, v in rows]

    avg_speed  = sum(speeds_ms)   / len(speeds_ms)
    avg_second = sum(secondaries) / len(secondaries)

    if avg_speed == 0:
        return None

    rei = avg_second / avg_speed

    return {
        "workout_id":  workout_id,
        "rei":         round(rei, 3),
        "mode":        mode,          # "power" or "hr"
        "avg_speed_ms": round(avg_speed, 3),
        "avg_power_or_hr": round(avg_second, 1),
        "rows_used":   len(rows),
    }


# ---------------------------------------------------------------------------
# Multi-workout trend queries (used by Streamlit + notebooks)
# ---------------------------------------------------------------------------

def get_running_trends(days: int = 365, conn=None) -> list[dict]:
    """
    For every running/trail_running workout in the last `days` days,
    compute GAP, decoupling, and REI.

    Returns list of dicts sorted by workout_date ascending.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT workout_id, workout_date, sport, training_volume,
               avg_heart_rate, normalized_power
        FROM workouts
        WHERE user_id = 1
          AND sport IN ('running', 'trail_running')
          AND workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY workout_date
    """, (days,))
    workouts = cur.fetchall()

    results = []
    for wid, wdate, sport, distance_m, avg_hr, norm_power in workouts:
        gap   = get_workout_gap(wid, conn)
        decoup = get_aerobic_decoupling(wid, conn)
        rei   = get_running_economy_index(wid, conn)

        row = {
            "workout_id":      wid,
            "workout_date":    wdate,
            "sport":           sport,
            "distance_km":     round((distance_m or 0) / 1000, 2),
            "avg_hr":          avg_hr,
            "normalized_power": norm_power,
            # GAP
            "avg_pace":        gap["avg_pace"]        if gap else None,
            "avg_gap":         gap["avg_gap"]         if gap else None,
            "gap_vs_pace_pct": gap["gap_vs_pace_pct"] if gap else None,
            # Decoupling
            "decoupling_pct":  decoup["decoupling_pct"] if decoup else None,
            "decoupling_status": decoup["status"]       if decoup else None,
            # REI
            "rei":             rei["rei"]   if rei else None,
            "rei_mode":        rei["mode"]  if rei else None,
        }
        results.append(row)

    if close:
        conn.close()

    return results
