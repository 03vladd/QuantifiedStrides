"""
Fetches exercises from the wger public API, maps muscles/equipment to our
vocabulary, then uses the Claude API to label movement patterns and training
attributes before inserting into the exercises table.

Usage:
    python3 import_wger.py                # import all English exercises
    python3 import_wger.py --dry-run      # print labels without inserting
    python3 import_wger.py --limit 20     # test with first N exercises
    python3 import_wger.py --batch 10     # Claude calls per batch (default 5)
"""

import argparse
import json
import re
import time

import anthropic
import requests

from config import ANTHROPIC_API_KEY
from db import get_connection


WGER_BASE = "https://wger.de/api/v2"

# ---------------------------------------------------------------------------
# wger → our vocabulary mappings
# ---------------------------------------------------------------------------

# Uses both name_en and Latin name (lowercased) for robustness
MUSCLE_NAME_MAP = {
    "shoulders": "front_delt",         # Anterior deltoid / name_en
    "anterior deltoid": "front_delt",
    "biceps": "biceps",
    "biceps brachii": "biceps",
    "brachialis": "biceps",            # closest in our vocab
    "hamstrings": "hamstrings",
    "biceps femoris": "hamstrings",
    "calves": "calves",
    "gastrocnemius": "calves",
    "soleus": "calves",
    "glutes": "glutes",
    "gluteus maximus": "glutes",
    "lats": "lats",
    "latissimus dorsi": "lats",
    "obliques": "obliques",
    "obliquus externus abdominis": "obliques",
    "chest": "chest",
    "pectoralis major": "chest",
    "serratus anterior": "chest",      # closest front-of-torso muscle in vocab
    "quads": "quads",
    "quadriceps femoris": "quads",
    "abs": "abs",
    "rectus abdominis": "abs",
    "trapezius": "traps",
    "triceps": "triceps",
    "triceps brachii": "triceps",
}

EQUIPMENT_NAME_MAP = {
    "barbell": "barbell",
    "bench": "bench",
    "dumbbell": "dumbbell",
    "gym mat": "mat",
    "incline bench": "bench",
    "kettlebell": "kettlebell",
    "pull-up bar": "pull-up bar",
    "resistance band": "band",
    "sz-bar": "ez-bar",
    "swiss ball": "swiss ball",
    # anything containing "none" or "bodyweight" → treat as bodyweight
}

# Name-fragment → equipment for exercises wger has no equipment entry for
NAME_EQUIPMENT_HINTS = [
    ("cable",       "cable machine"),
    ("barbell",     "barbell"),
    ("dumbbell",    "dumbbell"),
    ("kettlebell",  "kettlebell"),
    ("band",        "band"),
    ("ring",        "rings"),
    ("trx",         "trx"),
    ("machine",     "machine"),
]

SYSTEM_PROMPT = """Label exercises for an athlete performance database.
Return ONLY a JSON array — one object per exercise, same order as input. No markdown.

Each object has these fields:
- movement_pattern: push_h|push_v|pull_h|pull_v|hinge|squat|carry|rotation|plyo|isolation|stability
- quality_focus: power|strength|hypertrophy|endurance|stability
- skill_level: beginner|intermediate|advanced
- bilateral: true|false
- contraction_type: explosive|controlled|isometric|mixed
- systemic_fatigue: 1-5
- cns_load: 1-5
- joint_stress: [shoulder,elbow,wrist,knee,hip,lower_back,ankle] — 7 integers 1-5
- sport_carryover: [xc_mtb,trail_run,climbing,ski,snowboard] — 5 integers 1-5
- goal_carryover: [power,strength,hypertrophy,endurance,stability] — 5 integers 1-5

primary_muscles, secondary_muscles, equipment are already given — omit from output.
Athlete: XC MTB, trail running, bouldering, skiing. Goals: power + strength + athletic performance."""

_JS_JOINT_KEYS   = ["shoulder", "elbow", "wrist", "knee", "hip", "lower_back", "ankle"]
_JS_SPORT_KEYS   = ["xc_mtb", "trail_run", "climbing", "ski", "snowboard"]
_JS_GOAL_KEYS    = ["power", "strength", "hypertrophy", "endurance", "stability"]

_VALID_QUALITY_FOCUS     = {"power", "strength", "hypertrophy", "endurance", "stability"}
_VALID_MOVEMENT_PATTERN  = {"push_h", "push_v", "pull_h", "pull_v", "hinge", "squat",
                             "carry", "rotation", "plyo", "isolation", "stability"}
_VALID_CONTRACTION_TYPE  = {"explosive", "controlled", "isometric", "mixed"}
_VALID_SKILL_LEVEL       = {"beginner", "intermediate", "advanced"}

def _expand_arrays(fields):
    """Expand compact array JSONB fields and sanitize Claude's output."""
    for key, keys in [("joint_stress", _JS_JOINT_KEYS),
                      ("sport_carryover", _JS_SPORT_KEYS),
                      ("goal_carryover", _JS_GOAL_KEYS)]:
        val = fields.get(key, [])
        if isinstance(val, list):
            fields[key] = dict(zip(keys, val))

    # Remap invalid quality_focus values → nearest valid
    if fields.get("quality_focus") not in _VALID_QUALITY_FOCUS:
        fields["quality_focus"] = "hypertrophy"

    # Clamp numeric fields to schema range 1-5
    for key in ("systemic_fatigue", "cns_load"):
        fields[key] = max(1, min(5, int(fields.get(key) or 1)))

    # Fallback for other constrained fields
    if fields.get("movement_pattern") not in _VALID_MOVEMENT_PATTERN:
        fields["movement_pattern"] = "isolation"
    if fields.get("contraction_type") not in _VALID_CONTRACTION_TYPE:
        fields["contraction_type"] = "controlled"
    if fields.get("skill_level") not in _VALID_SKILL_LEVEL:
        fields["skill_level"] = "beginner"

    return fields


# ---------------------------------------------------------------------------
# wger fetch
# ---------------------------------------------------------------------------

def _strip_html(text):
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _map_muscles(muscle_list):
    result = []
    for m in muscle_list:
        key = m.get("name_en", "").lower() or m.get("name", "").lower()
        mapped = MUSCLE_NAME_MAP.get(key) or MUSCLE_NAME_MAP.get(m.get("name", "").lower())
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def _map_equipment(equipment_list, exercise_name=""):
    result = []
    for e in equipment_list:
        name = e.get("name", "").lower()
        if "none" in name or "bodyweight" in name:
            continue
        mapped = EQUIPMENT_NAME_MAP.get(name)
        if mapped and mapped not in result:
            result.append(mapped)
    if not result:
        # Infer from exercise name when wger has no equipment entry
        name_lower = exercise_name.lower()
        for fragment, eq in NAME_EQUIPMENT_HINTS:
            if fragment in name_lower:
                result.append(eq)
                break
    return result or ["bodyweight"]


# Equipment considered "free" / athletic — anything else is a machine
_KEEP_EQUIPMENT = {
    "barbell", "dumbbell", "kettlebell", "bodyweight", "band",
    "pull-up bar", "bench", "ez-bar", "swiss ball", "mat",
    "cable machine", "rings", "trx",
}

# Name fragments that signal machine isolations or cardio fluff
_SKIP_NAME_FRAGMENTS = [
    "hackenschmitt", "hackenschmid", "on machine", "on the machine",
    "machine ", " machine", "leg press", "chest press machine",
    "pec deck", "smith machine", "hack squat machine",
]

def _is_filler(name, category, equipment):
    """Return True for exercises we don't want: cardio entries, pure machine lifts."""
    if category == "Cardio":
        return True
    name_l = name.lower()
    if any(frag in name_l for frag in _SKIP_NAME_FRAGMENTS):
        return True
    # If ALL mapped equipment is outside our keep-set, skip
    if equipment and all(e not in _KEEP_EQUIPMENT for e in equipment):
        return True
    return False


def fetch_wger_exercises(limit=None):
    """Paginate through /exerciseinfo/ and return all English exercises."""
    exercises = []
    url = f"{WGER_BASE}/exerciseinfo/?format=json&language=2&limit=100"

    while url:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for ex in data["results"]:
            # Find English translation
            en = next((t for t in ex.get("translations", []) if t.get("language") == 2), None)
            if not en or not en.get("name", "").strip():
                continue

            name = en["name"].strip()
            if not name.isascii():
                continue
            description = _strip_html(en.get("description", ""))[:150]

            primary   = _map_muscles(ex.get("muscles", []))
            secondary = _map_muscles(ex.get("muscles_secondary", []))
            equipment = _map_equipment(ex.get("equipment", []), name)
            category  = ex.get("category", {}).get("name", "")

            if _is_filler(name, category, equipment):
                continue

            exercises.append({
                "name":        name,
                "category":    category,
                "primary":     primary,
                "secondary":   secondary,
                "equipment":   equipment,
                "description": description,
            })

            if limit and len(exercises) >= limit:
                return exercises

        url = data.get("next")
        if url:
            time.sleep(0.15)  # be polite to the public API

    return exercises


# ---------------------------------------------------------------------------
# Claude labeling
# ---------------------------------------------------------------------------

def label_batch(client, batch):
    """Send a batch of exercises to Claude; return list of label dicts."""
    lines = []
    for i, ex in enumerate(batch, 1):
        parts = [f'{i}. "{ex["name"]}" [{ex["category"]}] equip:{",".join(ex["equipment"])}']
        if ex["primary"]:
            parts.append(f'pri:{",".join(ex["primary"])}')
        if ex["secondary"]:
            parts.append(f'sec:{",".join(ex["secondary"])}')
        if ex["description"]:
            parts.append(ex["description"][:150])
        lines.append(" | ".join(parts))

    prompt = f"Label these {len(batch)} exercises:\n\n" + "\n".join(lines)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    labels = json.loads(raw.strip())
    return [_expand_arrays(f) for f in labels]


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------

def insert_exercise(cur, ex, fields):
    cur.execute("""
        INSERT INTO exercises (
            name, source,
            movement_pattern, quality_focus,
            primary_muscles, secondary_muscles,
            equipment, skill_level, bilateral, contraction_type,
            systemic_fatigue, cns_load,
            joint_stress, sport_carryover, goal_carryover
        ) VALUES (
            %s, 'wger',
            %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (name) DO NOTHING
        RETURNING exercise_id
    """, (
        ex["name"],
        fields["movement_pattern"],
        fields["quality_focus"],
        ex["primary"],
        ex["secondary"],
        ex["equipment"],
        fields["skill_level"],
        fields["bilateral"],
        fields["contraction_type"],
        fields["systemic_fatigue"],
        fields["cns_load"],
        json.dumps(fields["joint_stress"]),
        json.dumps(fields["sport_carryover"]),
        json.dumps(fields["goal_carryover"]),
    ))
    return cur.fetchone()  # None if skipped (ON CONFLICT DO NOTHING)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit",   type=int, default=None, help="Max exercises to fetch")
    parser.add_argument("--batch",   type=int, default=20,   help="Exercises per Claude call")
    args = parser.parse_args()

    print("Fetching exercises from wger API...")
    all_exercises = fetch_wger_exercises(limit=args.limit)
    print(f"Fetched {len(all_exercises)} English exercises from wger.\n")

    # Skip names that already exist (custom or previous wger import)
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT name FROM exercises")
    existing = {row[0] for row in cur.fetchall()}

    to_label = [ex for ex in all_exercises if ex["name"] not in existing]
    print(f"Already in DB: {len(existing)}  |  New to label: {len(to_label)}\n")

    if not to_label:
        print("Nothing to do.")
        cur.close()
        conn.close()
        return

    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    results  = []   # [(ex, fields), ...]
    failed   = []   # exercise names that errored

    def _label_with_retry(batch, depth=0):
        """Label a batch; if count mismatch, split and retry halves (max 2 levels)."""
        try:
            labels = label_batch(client, batch)
            if len(labels) != len(batch):
                raise ValueError(f"count mismatch: expected {len(batch)}, got {len(labels)}")
            return [(ex, f) for ex, f in zip(batch, labels)], []
        except Exception as e:
            if depth < 2 and len(batch) > 1:
                mid = len(batch) // 2
                ok1, fail1 = _label_with_retry(batch[:mid], depth + 1)
                ok2, fail2 = _label_with_retry(batch[mid:], depth + 1)
                return ok1 + ok2, fail1 + fail2
            return [], [ex["name"] for ex in batch]

    if args.dry_run:
        # Dry run: label first batch only and print
        sample = to_label[:args.batch]
        ok, _ = _label_with_retry(sample)
        print(f"\n-- DRY RUN — nothing inserted --")
        for ex, fields in ok[:5]:
            print(f"\n{ex['name']}  [{ex['category']}]")
            print(f"  muscles:  {ex['primary']}  /  {ex['secondary']}")
            print(f"  equipment: {ex['equipment']}")
            print(f"  → {fields['movement_pattern']}  {fields['quality_focus']}  "
                  f"CNS={fields['cns_load']}  fatigue={fields['systemic_fatigue']}  "
                  f"bilateral={fields['bilateral']}")
        cur.close()
        conn.close()
        return

    # Label + insert + commit per batch so kills don't lose progress
    inserted = skipped = 0
    total_batches = (len(to_label) + args.batch - 1) // args.batch
    for i in range(0, len(to_label), args.batch):
        batch = to_label[i : i + args.batch]
        batch_num = i // args.batch + 1
        names = ", ".join(ex["name"] for ex in batch[:3])
        suffix = f" +{len(batch)-3} more" if len(batch) > 3 else ""
        print(f"[{batch_num}/{total_batches}] {names}{suffix} ...", end=" ", flush=True)
        ok, fail = _label_with_retry(batch)
        failed.extend(fail)

        batch_inserted = batch_skipped = 0
        for ex, fields in ok:
            try:
                row = insert_exercise(cur, ex, fields)
                if row:
                    batch_inserted += 1
                else:
                    batch_skipped += 1
            except Exception as e:
                print(f"\n  DB error for '{ex['name']}': {e}")
                conn.rollback()
        conn.commit()
        inserted += batch_inserted
        skipped  += batch_skipped
        print(f"✓ {len(ok)} labeled  {batch_inserted} inserted  {batch_skipped} skipped" +
              (f"  {len(fail)} failed" if fail else ""))
        time.sleep(0.3)

    print(f"\nDone — {inserted} inserted, {skipped} skipped (name conflict), {len(failed)} label failures.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
