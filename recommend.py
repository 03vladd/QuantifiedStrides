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
    """
    blocks = {}
    yesterday_type = yesterday.get("session_type")

    # Hard block: lower body gym yesterday → no running
    if yesterday_type == "lower":
        blocks["run"] = "Lower body gym yesterday — legs need recovery"
        blocks["trail_run"] = "Lower body gym yesterday — legs need recovery"

    # Hard block: upper body gym yesterday → no climbing
    if yesterday_type == "upper":
        blocks["climb"] = "Upper body gym yesterday — joints and ligaments need recovery"

    # Readiness gates
    if readiness:
        if readiness["legs"] and readiness["legs"] <= 4:
            blocks["run"]       = "Legs feel too poor for running"
            blocks["trail_run"] = "Legs feel too poor for running"
            blocks["bike"]      = blocks.get("bike", "Legs feel poor — easy Z2 only if biking")

        if readiness["upper"] and readiness["upper"] <= 4:
            blocks["climb"] = "Upper body feel too poor for climbing"

        if readiness["joints"] and readiness["joints"] <= 4:
            blocks["run"]       = f"Joint/injury feel too low ({readiness['joints']}/10)"
            blocks["trail_run"] = f"Joint/injury feel too low ({readiness['joints']}/10)"
            blocks["climb"]     = f"Joint/injury feel too low ({readiness['joints']}/10)"

        if readiness["overall"] and readiness["overall"] <= 3:
            blocks["intensity"] = "Overall feel very low — rest or easy Z2 only"

    # Weather gates
    if weather:
        if weather["rain"] and weather["rain"] > 0.5:
            blocks["trail_run"]   = "Rain — technical trail too risky"
            blocks["xc_mtb"]      = "Rain — muddy and slippery on MTB"
            blocks["intensity"]   = blocks.get("intensity", "Rain — avoid threshold outdoor sessions")

        if weather["temp"] and weather["temp"] > 30:
            blocks["intensity"] = blocks.get("intensity", "Extreme heat — no high intensity outdoors")

    return blocks


def build_recommendation(readiness, yesterday, sleep, weather, load, consecutive_days):
    """
    Core decision logic. Returns a recommendation dict.
    """
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

    # Build the option list based on blocks + time
    # Current phase: base building, post-injury
    # Priority: bike > road run > climbing

    # After lower gym day
    if yesterday_type == "lower":
        avoid.append("Running (lower body recovery)")
        if time_available == "short":
            primary = "Easy Z2 Stationary Bike (20-30 min)"
            intensity = "Z2"
            duration = "20-30 min"
            why = "Lower body trained yesterday. Short window — easy spin at home, legs moving without stress."
        else:
            primary = "Easy Z2 Stationary Bike (45-60 min)"
            intensity = "Z2"
            duration = "45-60 min"
            why = "Lower body trained yesterday. Bike keeps the aerobic stimulus without any impact on recovering legs."

    # After upper gym day
    elif yesterday_type == "upper":
        avoid.append("Climbing (upper body/joint recovery)")
        if time_available == "short":
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

    # Rest day yesterday — full menu based on time + readiness
    else:
        if time_available == "short":
            primary = "Easy Z2 Stationary Bike (30 min)"
            intensity = "Z2"
            duration = "30 min"
            why = "Short window — stationary bike is the lowest friction option. Still moves the aerobic needle."

        elif time_available == "medium":
            if "climb" not in blocks and readiness and readiness["upper"] and readiness["upper"] >= 7:
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
            if "run" not in blocks and "trail_run" not in blocks:
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
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_recommendation(rec, readiness, sleep, yesterday, load, today, weather):
    width = 52
    print("\n" + "=" * width)
    print(f"  TRAINING RECOMMENDATION — {today.strftime('%d.%m.%Y')}")
    print("=" * width)

    print(f"\n  TODAY: {rec['primary']}")
    if rec["intensity"]:
        print(f"  Intensity : {rec['intensity']}")
    if rec["duration"]:
        print(f"  Duration  : {rec['duration']}")

    print(f"\n  Why: {rec['why']}")

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

    # Sleep summary
    if sleep and sleep["duration"]:
        hrv_str = f"  HRV: {sleep['hrv']:.1f}" if sleep["hrv"] else ""
        bb_str  = f"  Battery: +{sleep['body_battery']}" if sleep["body_battery"] else ""
        score_str = f"  score {sleep['score']:.0f}" if sleep["score"] else ""
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

    cur.close()
    conn.close()

    if not readiness:
        print("\nNo morning check-in found for today.")
        print("Run:  python3 checkin.py\n")
        sys.exit(0)

    rec = build_recommendation(readiness, yesterday_session, sleep, weather, load, consecutive)
    print_recommendation(rec, readiness, sleep, yesterday_session, load, today, weather)


if __name__ == "__main__":
    main()
