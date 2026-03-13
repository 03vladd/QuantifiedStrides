"""
Morning readiness check-in + post-workout reflection CLI.

Usage:
    python3 checkin.py            # morning check-in (default)
    python3 checkin.py --post     # post-workout reflection
    python3 checkin.py --date 13.03
"""

import argparse
import sys
from datetime import date, datetime

from db import get_connection


# ---------------------------------------------------------------------------
# Helpers
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


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def ask_int(prompt, lo=1, hi=10, default=None):
    while True:
        raw = ask(prompt, default)
        if raw is None:
            continue
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            print(f"  Enter a number between {lo} and {hi}.")
        except ValueError:
            print(f"  Enter a whole number ({lo}-{hi}).")


def ask_yn(prompt, default="n"):
    while True:
        raw = (ask(prompt + " (y/n)", default) or default).lower()
        if raw in ("y", "n"):
            return raw == "y"
        print("  Enter y or n.")


# ---------------------------------------------------------------------------
# Morning check-in
# ---------------------------------------------------------------------------

def run_morning_checkin(entry_date):
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute(
        "SELECT readiness_id FROM daily_readiness WHERE user_id = 1 AND entry_date = %s",
        (entry_date,)
    )
    if cur.fetchone():
        print(f"Morning check-in for {entry_date.strftime('%d.%m.%Y')} already logged.")
        cur.close()
        conn.close()
        return

    print(f"\nMorning check-in — {entry_date.strftime('%d.%m.%Y')}")
    print("Rate 1 (terrible) to 10 (perfect)\n")

    overall     = ask_int("Overall feel")
    legs        = ask_int("Legs feel")
    upper       = ask_int("Upper body feel")
    joints      = ask_int("Joint / injury feel")
    injury_note = None
    if joints <= 6:
        injury_note = ask("  What's bothering you?") or None

    print()
    time_raw = ask("Time available today  (1) short  (2) medium  (3) long", "2")
    time_map = {"1": "short", "2": "medium", "3": "long",
                "short": "short", "medium": "medium", "long": "long"}
    time_available = time_map.get(time_raw, "medium")

    going_out = ask_yn("Going out tonight?")

    cur.execute("""
        INSERT INTO daily_readiness
            (user_id, entry_date, overall_feel, legs_feel, upper_body_feel,
             joint_feel, injury_note, time_available, going_out_tonight)
        VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, entry_date) DO UPDATE SET
            overall_feel      = EXCLUDED.overall_feel,
            legs_feel         = EXCLUDED.legs_feel,
            upper_body_feel   = EXCLUDED.upper_body_feel,
            joint_feel        = EXCLUDED.joint_feel,
            injury_note       = EXCLUDED.injury_note,
            time_available    = EXCLUDED.time_available,
            going_out_tonight = EXCLUDED.going_out_tonight
    """, (entry_date, overall, legs, upper, joints, injury_note, time_available, going_out))

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nCheck-in saved.")


# ---------------------------------------------------------------------------
# Post-workout reflection
# ---------------------------------------------------------------------------

def run_post_workout(entry_date):
    conn = get_connection()
    cur  = conn.cursor()

    print(f"\nPost-workout reflection — {entry_date.strftime('%d.%m.%Y')}")
    print("Rate 1 (terrible) to 10 (perfect)\n")

    rpe     = ask_int("Session RPE (how hard was it)")
    quality = ask_int("Session quality (how well did it go)")
    notes   = ask("Notes (Enter to skip)", "") or None

    cur.execute("""
        INSERT INTO workout_reflection
            (user_id, entry_date, session_rpe, session_quality, notes)
        VALUES (1, %s, %s, %s, %s)
        ON CONFLICT (user_id, entry_date) DO UPDATE SET
            session_rpe     = EXCLUDED.session_rpe,
            session_quality = EXCLUDED.session_quality,
            notes           = EXCLUDED.notes
    """, (entry_date, rpe, quality, notes))

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nReflection saved.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true", help="Post-workout reflection mode")
    parser.add_argument("--date", help="Date (DD.MM or DD.MM.YYYY), defaults to today")
    args = parser.parse_args()

    if args.date:
        entry_date = parse_date(args.date)
        if not entry_date:
            print("Invalid date. Use DD.MM or DD.MM.YYYY.")
            sys.exit(1)
    else:
        entry_date = date.today()

    if args.post:
        run_post_workout(entry_date)
    else:
        run_morning_checkin(entry_date)


if __name__ == "__main__":
    main()
