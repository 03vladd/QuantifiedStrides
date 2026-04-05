"""
Training load metrics: TRIMP, ATL, CTL, TSB.

ATL (Acute Training Load)    = 7-day EWA  of daily load  → fatigue
CTL (Chronic Training Load)  = 42-day EWA of daily load  → fitness
TSB (Training Stress Balance)= CTL - ATL                 → form / freshness

TSB interpretation:
  > +10   : very fresh — race / peak performance window
   +5..+10: fresh — good day to push hard
  -5..+5  : neutral
 -15..-5  : productive fatigue — building fitness, train as planned
  < -15   : overreached — back off, risk of injury / illness

Usage:
    from training_load import get_metrics
    m = get_metrics(cur, today)
    print(m["ctl"], m["atl"], m["tsb"])
"""

from datetime import timedelta


# ---------------------------------------------------------------------------
# TRIMP zone weights  (Edwards / 5-zone model)
# ---------------------------------------------------------------------------
_ZONE_WEIGHTS = [1.0, 1.5, 2.0, 3.0, 4.0]   # zones 1-5


def _trimp_for_date(cur, d, user_id=1):
    """
    Sum HR-zone-weighted training load across all Garmin workouts on date d.
    time_in_hr_zone_* is stored in seconds.
    Falls back to strength_sessions set-count estimate if no Garmin entry.
    """
    cur.execute("""
        SELECT time_in_hr_zone_1, time_in_hr_zone_2, time_in_hr_zone_3,
               time_in_hr_zone_4, time_in_hr_zone_5
        FROM workouts
        WHERE user_id = %s AND workout_date = %s
    """, (user_id, d,))

    rows = cur.fetchall()
    trimp = 0.0
    for row in rows:
        for i, seconds in enumerate(row):
            if seconds:
                trimp += (seconds / 60.0) * _ZONE_WEIGHTS[i]

    if trimp == 0:
        # Garmin didn't record it — estimate from strength_sessions set counts
        cur.execute("""
            SELECT COUNT(st.set_id)
            FROM strength_sessions ss
            JOIN strength_exercises se ON se.session_id = ss.session_id
            JOIN strength_sets st ON st.exercise_id = se.exercise_id
            WHERE ss.user_id = %s AND ss.session_date = %s
        """, (user_id, d,))
        row = cur.fetchone()
        sets = row[0] if row else 0
        trimp = sets * 2.5   # rough: ~2.5 TRIMP per set ≈ 40 TRIMP for 16-set session

    return trimp


def get_metrics(cur, today, lookback=120, user_id=1):
    """
    Compute CTL, ATL, TSB as of `today` using `lookback` days of history.

    Returns a dict:
        ctl          : chronic training load (fitness)
        atl          : acute training load (fatigue)
        tsb          : training stress balance (form)
        today_load   : raw TRIMP for today
        ramp_rate    : CTL change over last 7 days (fitness ramp)
    """
    k_ctl = 1 / 42
    k_atl = 1 / 7
    ctl = 0.0
    atl = 0.0

    d = today - timedelta(days=lookback)
    while d <= today:
        load = _trimp_for_date(cur, d, user_id)
        ctl  = ctl * (1 - k_ctl) + load * k_ctl
        atl  = atl * (1 - k_atl) + load * k_atl
        d   += timedelta(days=1)

    # Ramp rate: CTL today vs CTL 7 days ago
    ctl_7ago = 0.0
    atl_7ago = 0.0
    d = today - timedelta(days=lookback)
    while d <= today - timedelta(days=7):
        load    = _trimp_for_date(cur, d, user_id)
        ctl_7ago = ctl_7ago * (1 - k_ctl) + load * k_ctl
        atl_7ago = atl_7ago * (1 - k_atl) + load * k_atl
        d += timedelta(days=1)

    today_load = _trimp_for_date(cur, today, user_id)

    return {
        "ctl":        round(ctl, 1),
        "atl":        round(atl, 1),
        "tsb":        round(ctl - atl, 1),
        "today_load": round(today_load, 1),
        "ramp_rate":  round(ctl - ctl_7ago, 1),
    }


def get_history(cur, today, days=90, user_id=1):
    """Return list of dicts with date/load/ctl/atl/tsb for the past `days` days."""
    k_ctl = 1 / 42
    k_atl = 1 / 7
    start = today - timedelta(days=days + 60)   # extra warmup for CTL
    ctl = atl = 0.0
    history = []
    d = start
    while d <= today:
        load = _trimp_for_date(cur, d, user_id)
        ctl  = ctl * (1 - k_ctl) + load * k_ctl
        atl  = atl * (1 - k_atl) + load * k_atl
        if d >= today - timedelta(days=days):
            history.append({"date": d, "load": round(load, 1),
                             "ctl": round(ctl, 1), "atl": round(atl, 1),
                             "tsb": round(ctl - atl, 1)})
        d += timedelta(days=1)
    return history


def get_hrv_history(cur, today, days=30, user_id=1):
    """Return list of dicts with date/hrv/baseline/rhr/sleep_score."""
    start = today - timedelta(days=days + 10)
    cur.execute("""
        SELECT sleep_date, overnight_hrv, rhr, sleep_score
        FROM sleep_sessions
        WHERE user_id = %s AND sleep_date BETWEEN %s AND %s
          AND overnight_hrv IS NOT NULL
        ORDER BY sleep_date
    """, (user_id, start, today))
    rows = cur.fetchall()
    result = []
    for i, (d, hrv, rhr, score) in enumerate(rows):
        if d < today - timedelta(days=days):
            continue
        baseline_vals = [r[1] for r in rows[:i] if r[0] < d][-7:]
        baseline = round(sum(baseline_vals) / len(baseline_vals), 1) if baseline_vals else hrv
        result.append({"date": d, "hrv": hrv, "baseline": baseline,
                        "rhr": rhr, "sleep_score": score})
    return result


def tsb_intensity_hint(tsb):
    """
    Translate TSB into a training intensity recommendation.
    Returns (label, modifier) where modifier is 'push' | 'normal' | 'back_off' | 'rest'.
    """
    if tsb > 10:
        return "very fresh",  "push"
    if tsb > 5:
        return "fresh",       "push"
    if tsb >= -5:
        return "neutral",     "normal"
    if tsb >= -15:
        return "productive fatigue", "normal"
    return "overreached", "back_off"
