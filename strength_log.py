"""
CLI for logging a strength session.

Usage:
    python3 strength_log.py
    python3 strength_log.py --date 12.03
"""

import argparse
import sys
from datetime import date, datetime

from db import get_connection

BAR_WEIGHT_KG = 20.0

INSERT_SESSION = """
INSERT INTO strength_sessions (user_id, session_date, session_type, raw_notes)
VALUES (%s, %s, %s, %s)
ON CONFLICT (user_id, session_date) DO UPDATE SET
    session_type = EXCLUDED.session_type,
    raw_notes    = EXCLUDED.raw_notes
RETURNING session_id;
"""
DELETE_EXERCISES = "DELETE FROM strength_exercises WHERE session_id = %s;"
INSERT_EXERCISE  = """
INSERT INTO strength_exercises (session_id, exercise_order, name, notes)
VALUES (%s, %s, %s, %s) RETURNING exercise_id;
"""
INSERT_SET = """
INSERT INTO strength_sets (
    exercise_id, set_number, reps,
    duration_seconds, weight_kg, is_bodyweight, band_color,
    per_hand, per_side, plus_bar, weight_includes_bar, total_weight_kg
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

BAND_COLORS = ["yellow", "blue", "green", "red", "black"]
BACK = "__BACK__"


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    if val.lower() == "b":
        return BACK
    return val if val else default


def ask_yn(prompt, default="n"):
    val = ask(prompt + " (y/n)", default)
    if val is BACK:
        return BACK
    return (val or default).lower() == "y"


def ask_int(prompt, default=None):
    while True:
        raw = ask(prompt, default)
        if raw is BACK:
            return BACK
        if raw is None or raw == "":
            continue
        try:
            return int(raw)
        except ValueError:
            print("  Enter a whole number.")


def ask_float(prompt, default=None):
    while True:
        raw = ask(prompt, default)
        if raw is BACK:
            return BACK
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except ValueError:
            print("  Enter a number (e.g. 80 or 12.5).")


def collect_exercise(order):
    print(f"\n  -- Exercise {order} -- (type 'b' at any prompt to go back one step)")

    # Each step is a function(state) -> state or BACK
    # State is a dict that accumulates answers
    def step_name(s):
        val = ask("  Name") or ""
        if val is BACK: return BACK
        val = val.strip()
        if not val: return None  # blank = done
        return {**s, "name": val}

    def step_notes(s):
        val = ask("  Notes (Enter to skip)", "") or None
        if val is BACK: return BACK
        return {**s, "notes": val}

    def step_per_hand(s):
        val = ask_yn("  Per hand (/mana)?")
        if val is BACK: return BACK
        return {**s, "per_hand": val}

    def step_per_side(s):
        val = ask_yn("  Per side (/picior)?")
        if val is BACK: return BACK
        return {**s, "per_side": val}

    def step_weight(s):
        val = ask("  Weight: (1) kg  (2) bodyweight  (3) band", "1")
        if val is BACK: return BACK
        if val == "2":
            return {**s, "weight_type": val, "is_bw": True,
                    "band_color": None, "weight_kg": None, "plus_bar": False, "incl_bar": False}
        if val == "3":
            color = ask("  Band color")
            if color is BACK: return BACK
            return {**s, "weight_type": val, "is_bw": False,
                    "band_color": color.lower(), "weight_kg": None, "plus_bar": False, "incl_bar": False}
        # kg
        w = ask_float("  Weight (kg)")
        if w is BACK: return BACK
        bar = ask("  Bar: (1) none  (2) +bara (+20kg)  (3) cu tot cu bara", "1")
        if bar is BACK: return BACK
        return {**s, "weight_type": val, "is_bw": False,
                "band_color": None, "weight_kg": w, "plus_bar": bar == "2", "incl_bar": bar == "3"}

    def step_sets_count(s):
        val = ask_int("  Number of sets")
        if val is BACK: return BACK
        return {**s, "sets_count": val}

    def step_timed(s):
        val = ask_yn("  Time-based (e.g. 30sec)?")
        if val is BACK: return BACK
        return {**s, "is_timed": val}

    def step_reps_or_duration(s):
        n = s["sets_count"]
        if s["is_timed"]:
            same = ask_yn("  Same duration for all sets?", "y")
            if same is BACK: return BACK
            if same:
                val = ask_int("  Duration per set (seconds)")
                if val is BACK: return BACK
                return {**s, "durations": [val] * n, "reps_list": [None] * n}
            else:
                durations = []
                for i in range(n):
                    val = ask_int(f"  Duration set {i+1} (seconds)")
                    if val is BACK: return BACK
                    durations.append(val)
                return {**s, "durations": durations, "reps_list": [None] * n}
        else:
            same = ask_yn("  Same reps for all sets?", "y")
            if same is BACK: return BACK
            if same:
                val = ask_int("  Reps per set")
                if val is BACK: return BACK
                return {**s, "reps_list": [val] * n, "durations": [None] * n}
            else:
                reps_list = []
                for i in range(n):
                    val = ask_int(f"  Reps set {i+1}")
                    if val is BACK: return BACK
                    reps_list.append(val)
                return {**s, "reps_list": reps_list, "durations": [None] * n}

    def ask_set_weight(label):
        """Ask full weight type + detail for a single set. Returns a weight dict or BACK."""
        wt = ask(f"  {label} weight: (1) kg  (2) bodyweight  (3) band", "1")
        if wt is BACK: return BACK
        if wt == "2":
            return {"is_bw": True, "band_color": None, "weight_kg": None, "plus_bar": False, "incl_bar": False}
        if wt == "3":
            color = ask(f"  {label} band color")
            if color is BACK: return BACK
            return {"is_bw": False, "band_color": color.lower(), "weight_kg": None, "plus_bar": False, "incl_bar": False}
        w = ask_float(f"  {label} weight (kg)")
        if w is BACK: return BACK
        bar = ask("  Bar: (1) none  (2) +bara  (3) cu tot cu bara", "1")
        if bar is BACK: return BACK
        return {"is_bw": False, "band_color": None, "weight_kg": w, "plus_bar": bar == "2", "incl_bar": bar == "3"}

    def step_weight_per_set(s):
        default = {"is_bw": s["is_bw"], "band_color": s["band_color"],
                   "weight_kg": s["weight_kg"], "plus_bar": s["plus_bar"], "incl_bar": s["incl_bar"]}
        same = ask_yn("  Same weight for all sets?", "y")
        if same is BACK: return BACK
        if same:
            return {**s, "set_weights": [default] * s["sets_count"]}
        set_weights = []
        for i in range(s["sets_count"]):
            w = ask_set_weight(f"Set {i+1}")
            if w is BACK: return BACK
            set_weights.append(w)
        return {**s, "set_weights": set_weights}

    steps = [step_name, step_notes, step_per_hand, step_per_side,
             step_weight, step_sets_count, step_timed,
             step_reps_or_duration, step_weight_per_set]

    state   = {}
    history = []  # stack of states before each user-facing step
    i = 0
    while i < len(steps):
        before = state
        result = steps[i](state)
        if result is None:
            return None  # blank name = user is done
        if result is BACK:
            if history:
                state = history.pop()
                i = max(0, i - 1)
                # keep going back past steps that didn't change state
                while i > 0 and history and history[-1] == state:
                    state = history.pop()
                    i -= 1
                print("  (going back)")
            # else already at first step, just re-ask it
        else:
            if result != before:  # only record steps that actually changed state
                history.append(before)
            state = result
            i += 1

    # Build sets from state
    s = state
    def compute_total(sw):
        w = sw["weight_kg"]
        if sw["is_bw"] or w is None: return None
        if sw["plus_bar"]: return w + BAR_WEIGHT_KG
        if sw["incl_bar"]: return w
        if s["per_hand"]: return w * 2
        return w

    def adjusted_weight(sw):
        w = sw["weight_kg"]
        return (w - BAR_WEIGHT_KG) if (sw["incl_bar"] and w is not None) else w

    sets = []
    for i in range(s["sets_count"]):
        sw = s["set_weights"][i]
        sets.append({
            "set_number": i + 1,
            "reps": s["reps_list"][i],
            "duration_seconds": s["durations"][i],
            "weight_kg": adjusted_weight(sw),
            "is_bodyweight": sw["is_bw"],
            "band_color": sw["band_color"],
            "per_hand": s["per_hand"],
            "per_side": s["per_side"],
            "plus_bar": sw["plus_bar"],
            "weight_includes_bar": s["incl_bar"],
            "total_weight_kg": compute_total(sw),
        })

    ex = {"exercise_order": order, "name": s["name"], "notes": s["notes"], "sets": sets}

    # Mini-summary + confirm before accepting
    while True:
        print(f"\n  Preview — {ex['name']}:")
        all_sets = ex["sets"]
        s0 = all_sets[0]
        all_reps = [str(s.get("reps") or (str(s.get("duration_seconds")) + "sec")) for s in all_sets]
        reps_str = all_reps[0] if len(set(all_reps)) == 1 else ", ".join(all_reps)
        if s0.get("is_bodyweight"):
            w_str = "BW"
        elif s0.get("band_color"):
            w_str = f"band({s0['band_color']})"
        else:
            all_w = [str(s.get("total_weight_kg", "?")) + "kg" for s in all_sets]
            w_str = all_w[0] if len(set(all_w)) == 1 else ", ".join(all_w)
        mods = []
        if s0.get("per_hand"): mods.append("/mana")
        if s0.get("per_side"): mods.append("/picior")
        print(f"  {len(all_sets)}x{reps_str}x{w_str}{'  ' + ' '.join(mods) if mods else ''}")

        ok = ask("  OK? (y) yes  (r) redo", "y")
        if ok == "r":
            return collect_exercise(order)
        break

    return ex


def print_summary(session_date, session_type, exercises):
    print(f"\n========== {session_type.upper()} — {session_date.strftime('%d.%m.%Y')} ==========")
    for ex in exercises:
        s0     = ex["sets"][0] if ex["sets"] else {}
        n_sets = len(ex["sets"])

        # Reps — show each set if they vary
        all_sets = ex["sets"]
        if s0.get("duration_seconds"):
            all_dur = [str(s["duration_seconds"]) + "sec" for s in all_sets]
            reps_str = all_dur[0] if len(set(all_dur)) == 1 else ", ".join(all_dur)
        else:
            all_reps = [str(s.get("reps", "?")) for s in all_sets]
            reps_str = all_reps[0] if len(set(all_reps)) == 1 else ", ".join(all_reps)

        # Weight — show each set if they vary
        if s0.get("is_bodyweight"):
            w_str = "BW"
        elif s0.get("band_color"):
            w_str = f"band({s0['band_color']})"
        else:
            all_w = [str(s.get("total_weight_kg", "?")) + "kg" for s in all_sets]
            w_str = all_w[0] if len(set(all_w)) == 1 else ", ".join(all_w)

        mods = []
        if s0.get("per_hand"): mods.append("/mana")
        if s0.get("per_side"): mods.append("/picior")
        mod_str  = "  " + " ".join(mods) if mods else ""
        note_str = f"  ({ex['notes']})" if ex["notes"] else ""

        print(f"  {ex['exercise_order']}. {ex['name']}{note_str}")
        print(f"     {n_sets}x{reps_str}x{w_str}{mod_str}")
    print("=" * 44)


def save(session_date, session_type, exercises):
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute(INSERT_SESSION, (1, session_date, session_type, None))
    session_id = cur.fetchone()[0]
    cur.execute(DELETE_EXERCISES, (session_id,))

    for ex in exercises:
        cur.execute(INSERT_EXERCISE, (
            session_id, ex["exercise_order"], ex["name"], ex["notes"],
        ))
        exercise_id = cur.fetchone()[0]
        for s in ex["sets"]:
            cur.execute(INSERT_SET, (
                exercise_id, s["set_number"], s["reps"],
                s["duration_seconds"], s["weight_kg"],
                s["is_bodyweight"], s["band_color"],
                s["per_hand"], s["per_side"],
                s["plus_bar"], s["weight_includes_bar"],
                s["total_weight_kg"],
            ))

    conn.commit()
    cur.close()
    conn.close()
    return session_id


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
    parser.add_argument("--date", help="Session date (DD.MM or DD.MM.YYYY)")
    args = parser.parse_args()

    if args.date:
        session_date = parse_date(args.date)
        if not session_date:
            print("Invalid date. Use DD.MM or DD.MM.YYYY.")
            sys.exit(1)
    else:
        default_str = date.today().strftime("%d.%m")
        while True:
            session_date = parse_date(ask("Session date", default_str))
            if session_date:
                break
            print("  Invalid date. Use DD.MM or DD.MM.YYYY.")

    while True:
        raw = ask("Session type: (u) upper  (l) lower", "u")
        if raw in ("u", "upper"):
            session_type = "upper"
            break
        elif raw in ("l", "lower"):
            session_type = "lower"
            break
        print("  Enter 'u' for upper or 'l' for lower.")

    print(f"\nLogging {session_type} session for {session_date.strftime('%d.%m.%Y')}")
    print("Enter exercises one by one. Leave name blank when done.\n")

    exercises = []
    while True:
        ex = collect_exercise(len(exercises) + 1)
        if ex is None:
            break
        exercises.append(ex)

    if not exercises:
        print("No exercises entered. Exiting.")
        sys.exit(0)

    while True:
        print_summary(session_date, session_type, exercises)
        action = ask("\nAction: (s) save  (e) edit exercise  (d) delete exercise  (c) cancel", "s")

        if action == "s":
            break
        elif action == "c":
            print("Cancelled.")
            sys.exit(0)
        elif action == "d":
            idx = ask_int(f"  Delete which exercise number? (1-{len(exercises)})")
            if idx and 1 <= idx <= len(exercises):
                removed = exercises.pop(idx - 1)
                for i, ex in enumerate(exercises):
                    ex["exercise_order"] = i + 1
                print(f"  Removed: {removed['name']}")
        elif action == "e":
            idx = ask_int(f"  Edit which exercise number? (1-{len(exercises)})")
            if idx and 1 <= idx <= len(exercises):
                print(f"  Re-entering exercise {idx} (was: {exercises[idx-1]['name']})")
                new_ex = collect_exercise(idx)
                if new_ex:
                    exercises[idx - 1] = new_ex

    session_id = save(session_date, session_type, exercises)
    print(f"Saved — session_id={session_id} ({session_type}) for {session_date.strftime('%d.%m.%Y')}.")


if __name__ == "__main__":
    main()
