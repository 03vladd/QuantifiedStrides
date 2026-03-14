"""
analytics/terrain_response.py

Terrain response analytics: how your body responds to elevation changes.

1. HR-Gradient Response Curve
   Buckets all data points by gradient band and computes mean HR, mean pace,
   mean GAP for each band. Your personal "grade cost" table.

2. Per-Run Elevation vs HR Decoupling
   As cumulative elevation gain increases during a run, does HR rise
   disproportionately relative to pace? Separates terrain fatigue from
   flat-ground cardiac drift.

3. Grade Cost Model
   Fits a simple linear model: for each 1% of additional gradient,
   how many extra bpm does your HR add (at constant pace)?
   Compared against Minetti's theoretical model to see how close you track it.

4. Optimal Gradient Finder
   At which gradient is your pace:effort ratio (speed per HR beat) best?
   Most runners peak around -2 to 0%. Reveals whether you run downhills well.
"""

from __future__ import annotations

from typing import Optional

from db import get_connection
from analytics.running_economy import gap_multiplier


# ---------------------------------------------------------------------------
# HR-Gradient response curve
# ---------------------------------------------------------------------------

GRADIENT_BANDS = [
    ("steep_down",   None,  -8.0),
    ("down",         -8.0,  -4.0),
    ("slight_down",  -4.0,  -1.0),
    ("flat",         -1.0,   1.0),
    ("slight_up",     1.0,   4.0),
    ("up",            4.0,   8.0),
    ("steep_up",      8.0,  None),
]


def _band_for(gradient_pct: float) -> str:
    for name, lo, hi in GRADIENT_BANDS:
        if (lo is None or gradient_pct >= lo) and (hi is None or gradient_pct < hi):
            return name
    return "flat"


def get_hr_gradient_curve(days: int = 365, sport: str = "running", conn=None) -> list[dict]:
    """
    Aggregate HR and pace across all running workouts by gradient band.

    Returns list of dicts, one per band:
        band            : str  (label)
        gradient_mid    : float  (representative gradient for that band)
        avg_hr          : float
        avg_pace        : float  (min/km)
        avg_gap         : float  (grade-adjusted pace)
        efficiency      : float  (speed_ms / HR — higher = more efficient)
        count           : int
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT wm.heart_rate, wm.pace, wm.gradient_pct
        FROM workout_metrics wm
        JOIN workouts w ON w.workout_id = wm.workout_id
        WHERE w.user_id = 1
          AND w.sport = %s
          AND w.workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
          AND wm.heart_rate IS NOT NULL AND wm.heart_rate > 40
          AND wm.pace IS NOT NULL AND wm.pace > 0 AND wm.pace < 20
          AND wm.gradient_pct IS NOT NULL
          AND wm.gradient_pct BETWEEN -30 AND 30
    """, (sport, days))
    rows = cur.fetchall()

    if close:
        conn.close()

    if not rows:
        return []

    # Accumulate per band
    band_data: dict[str, dict] = {
        name: {"hr": [], "pace": [], "gap": []}
        for name, _, _ in GRADIENT_BANDS
    }
    band_mid = {
        "steep_down": -10.0, "down": -6.0, "slight_down": -2.5,
        "flat": 0.0, "slight_up": 2.5, "up": 6.0, "steep_up": 10.0,
    }

    for hr, pace, grad in rows:
        band = _band_for(grad)
        band_data[band]["hr"].append(hr)
        band_data[band]["pace"].append(pace)
        band_data[band]["gap"].append(pace * gap_multiplier(grad))

    result = []
    for name, _, _ in GRADIENT_BANDS:
        d = band_data[name]
        if len(d["hr"]) < 10:
            continue
        avg_hr   = sum(d["hr"])   / len(d["hr"])
        avg_pace = sum(d["pace"]) / len(d["pace"])
        avg_gap  = sum(d["gap"])  / len(d["gap"])
        speed_ms = 1000.0 / (avg_pace * 60.0)
        result.append({
            "band":         name,
            "gradient_mid": band_mid[name],
            "avg_hr":       round(avg_hr,   1),
            "avg_pace":     round(avg_pace, 3),
            "avg_gap":      round(avg_gap,  3),
            "efficiency":   round(speed_ms / avg_hr, 6),
            "count":        len(d["hr"]),
        })

    return result


# ---------------------------------------------------------------------------
# Per-run elevation vs HR decoupling
# ---------------------------------------------------------------------------

def get_elevation_hr_decoupling(workout_id: int, conn=None) -> Optional[dict]:
    """
    Within a single run, track how HR evolves as cumulative elevation gain grows.

    Splits the run into 4 quartiles of cumulative elevation gain.
    For each quartile: mean HR, mean pace, mean GAP.

    A well-trained runner holds steady HR even as elevation accumulates.
    Rising HR in Q3/Q4 relative to pace → terrain fatigue.

    Returns dict or None if insufficient elevation data.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT metric_timestamp, heart_rate, pace, altitude, gradient_pct
        FROM workout_metrics
        WHERE workout_id = %s
          AND altitude IS NOT NULL
          AND heart_rate IS NOT NULL AND heart_rate > 40
          AND pace IS NOT NULL AND pace > 0 AND pace < 20
        ORDER BY metric_timestamp
    """, (workout_id,))
    rows = cur.fetchall()

    if close:
        conn.close()

    if len(rows) < 50:
        return None

    # Compute cumulative elevation gain
    cum_gain = 0.0
    points = []
    prev_alt = rows[0][3]
    for ts, hr, pace, alt, grad in rows:
        d_alt = alt - prev_alt
        if d_alt > 0:
            cum_gain += d_alt
        points.append((hr, pace, grad, cum_gain))
        prev_alt = alt

    if cum_gain < 20:   # less than 20m total gain → not meaningful
        return None

    # Split into quartiles by cumulative gain
    q_size = cum_gain / 4
    quartiles = [[], [], [], []]
    for hr, pace, grad, cg in points:
        q = min(3, int(cg / q_size))
        quartiles[q].append((hr, pace, grad))

    def avg(data, idx):
        vals = [r[idx] for r in data if r[idx] is not None]
        return sum(vals) / len(vals) if vals else None

    result = {
        "workout_id":   workout_id,
        "total_gain_m": round(cum_gain, 1),
        "quartiles":    [],
    }

    for i, q in enumerate(quartiles):
        if not q:
            continue
        a_hr   = avg(q, 0)
        a_pace = avg(q, 1)
        a_grad = avg(q, 2)
        a_gap  = None
        if a_pace and a_grad is not None:
            a_gap = round(a_pace * gap_multiplier(a_grad), 3)

        result["quartiles"].append({
            "quartile":    i + 1,
            "count":       len(q),
            "avg_hr":      round(a_hr,   1) if a_hr   else None,
            "avg_pace":    round(a_pace, 3) if a_pace else None,
            "avg_gap":     a_gap,
            "avg_gradient": round(a_grad, 2) if a_grad is not None else None,
        })

    return result


# ---------------------------------------------------------------------------
# Grade cost model: HR per 1% grade increase (linear fit)
# ---------------------------------------------------------------------------

def get_grade_cost_model(days: int = 365, sport: str = "running", conn=None) -> Optional[dict]:
    """
    Fit a linear model: HR ~ α + β × gradient_pct  (at matched pace bands).

    To isolate gradient effect from pace effect, we group points into pace
    bands (1 min/km wide) and within each band compute gradient vs HR.

    Returns:
        slope_bpm_per_pct : float  (HR cost per 1% gradient)
        intercept         : float
        r_squared         : float
        minetti_expected  : float  (theoretical HR cost from Minetti model)
        pace_bands        : list of {pace_band, slope} (per-pace-band slopes)
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT wm.heart_rate, wm.pace, wm.gradient_pct
        FROM workout_metrics wm
        JOIN workouts w ON w.workout_id = wm.workout_id
        WHERE w.user_id = 1
          AND w.sport = %s
          AND w.workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
          AND wm.heart_rate IS NOT NULL AND wm.heart_rate > 40
          AND wm.pace IS NOT NULL AND wm.pace > 0 AND wm.pace < 20
          AND wm.gradient_pct IS NOT NULL
          AND wm.gradient_pct BETWEEN -20 AND 20
    """, (sport, days))
    rows = cur.fetchall()

    if close:
        conn.close()

    if len(rows) < 100:
        return None

    # Simple linear regression: y=HR, x=gradient_pct
    xs = [r[2] for r in rows]
    ys = [r[0] for r in rows]
    n  = len(xs)

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xy  = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_xx  = sum((x - mean_x) ** 2 for x in xs)

    if ss_xx == 0:
        return None

    slope     = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # R²
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Minetti theoretical: at typical running pace (~3 m/s = 5:33/km),
    # estimate HR cost per 1% grade from metabolic cost ratio × typical HR (~150 bpm)
    typical_hr = mean_y
    cost_flat  = _minetti_cost_from_module(0.0)
    cost_1pct  = _minetti_cost_from_module(0.01)
    minetti_expected = (cost_1pct / cost_flat - 1.0) * typical_hr

    return {
        "slope_bpm_per_pct":  round(slope, 3),
        "intercept":          round(intercept, 1),
        "r_squared":          round(r2, 4),
        "n_points":           n,
        "minetti_expected":   round(minetti_expected, 3),
        "mean_hr":            round(mean_y, 1),
    }


def _minetti_cost_from_module(g: float) -> float:
    return (155.4 * g**5 - 30.4 * g**4 - 43.3 * g**3 + 46.3 * g**2 + 19.5 * g + 3.6)


# ---------------------------------------------------------------------------
# Optimal gradient finder
# ---------------------------------------------------------------------------

def get_optimal_gradient(days: int = 365, sport: str = "running", conn=None) -> Optional[dict]:
    """
    At which gradient (in 2% buckets) is your speed:HR ratio highest?
    speed_per_hr = (1000 / pace_s) / heart_rate   (m/s per bpm)

    Returns list of {gradient_pct, speed_per_hr, count} and the optimal band.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT wm.heart_rate, wm.pace, wm.gradient_pct
        FROM workout_metrics wm
        JOIN workouts w ON w.workout_id = wm.workout_id
        WHERE w.user_id = 1
          AND w.sport = %s
          AND w.workout_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
          AND wm.heart_rate IS NOT NULL AND wm.heart_rate > 40
          AND wm.pace IS NOT NULL AND wm.pace > 0 AND wm.pace < 20
          AND wm.gradient_pct IS NOT NULL
          AND wm.gradient_pct BETWEEN -20 AND 20
    """, (sport, days))
    rows = cur.fetchall()

    if close:
        conn.close()

    if not rows:
        return None

    buckets: dict[int, list[float]] = {}
    for hr, pace, grad in rows:
        speed_ms = 1000.0 / (pace * 60.0)
        efficiency = speed_ms / hr
        b = round(grad / 2) * 2   # 2% buckets
        if b not in buckets:
            buckets[b] = []
        buckets[b].append(efficiency)

    bands = [
        {
            "gradient_pct":  b,
            "speed_per_hr":  round(sum(v) / len(v), 7),
            "count":         len(v),
        }
        for b, v in sorted(buckets.items())
        if len(v) >= 20
    ]

    if not bands:
        return None

    optimal = max(bands, key=lambda x: x["speed_per_hr"])

    return {
        "bands":           bands,
        "optimal_gradient": optimal["gradient_pct"],
        "optimal_efficiency": optimal["speed_per_hr"],
    }


# ---------------------------------------------------------------------------
# Combined summary for Streamlit / notebooks
# ---------------------------------------------------------------------------

def get_terrain_summary(days: int = 365, conn=None) -> dict:
    """
    Returns all terrain response analytics as a single dict.
    Used by the Streamlit page and notebooks.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    curve   = get_hr_gradient_curve(days=days, conn=conn)
    model   = get_grade_cost_model(days=days,  conn=conn)
    optimal = get_optimal_gradient(days=days,  conn=conn)

    if close:
        conn.close()

    return {
        "hr_gradient_curve": curve,
        "grade_cost_model":  model,
        "optimal_gradient":  optimal,
    }
