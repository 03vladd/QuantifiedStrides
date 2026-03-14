"""
Labels and imports exercises into the exercises table using Claude API.

Usage:
    python3 import_exercises.py              # label all exercises from strength_exercises
    python3 import_exercises.py --dry-run    # print labels without inserting
"""

import argparse
import json
import sys
import time

import anthropic

from config import ANTHROPIC_API_KEY
from db import get_connection


MUSCLE_VOCABULARY = [
    "chest", "front_delt", "side_delt", "rear_delt",
    "biceps", "triceps", "forearms",
    "upper_back", "lats", "rhomboids", "traps",
    "abs", "obliques", "lower_back", "glutes",
    "quads", "hamstrings", "hip_flexors", "hip_abductors", "hip_adductors",
    "calves", "tibialis", "peroneals",
]

SCHEMA_DESCRIPTION = """
You are labeling exercises for an athlete performance database. Return ONLY valid JSON.

Schema fields to fill:
- movement_pattern: one of [push_h, push_v, pull_h, pull_v, hinge, squat, carry, rotation, plyo, isolation, stability]
- quality_focus: one of [power, strength, hypertrophy, endurance, stability]
- primary_muscles: array from vocabulary
- secondary_muscles: array from vocabulary
- equipment: array of strings (e.g. ["barbell"], ["dumbbell"], ["bodyweight"], ["kettlebell"], ["band", "pull-up bar"])
- skill_level: one of [beginner, intermediate, advanced]
- bilateral: true or false
- contraction_type: one of [explosive, controlled, isometric, mixed]
- systemic_fatigue: 1-5 (1=minimal e.g. face pulls, 5=very high e.g. heavy deadlift)
- cns_load: 1-5 (1=minimal e.g. isolation curl, 5=max e.g. heavy squat or plyometrics)
- joint_stress: object with keys [shoulder, elbow, wrist, knee, hip, lower_back, ankle] each 1-5
- sport_carryover: object with keys [xc_mtb, trail_run, climbing, ski, snowboard] each 1-5
- goal_carryover: object with keys [power, strength, hypertrophy, endurance, stability] each 1-5

Muscle vocabulary (use only these):
chest, front_delt, side_delt, rear_delt, biceps, triceps, forearms,
upper_back, lats, rhomboids, traps, abs, obliques, lower_back, glutes,
quads, hamstrings, hip_flexors, hip_abductors, hip_adductors,
calves, tibialis, peroneals

Context: This athlete is a mountain sports athlete (XC MTB, trail running, bouldering, skiing).
Training goals mix power, strength, and athletic performance — not pure bodybuilding.
"""


def label_exercise(client, name):
    prompt = f"""Label this exercise: "{name}"

Return ONLY a JSON object with these exact fields. No explanation, no markdown, just JSON:
{{
  "movement_pattern": "...",
  "quality_focus": "...",
  "primary_muscles": [...],
  "secondary_muscles": [...],
  "equipment": [...],
  "skill_level": "...",
  "bilateral": true/false,
  "contraction_type": "...",
  "systemic_fatigue": N,
  "cns_load": N,
  "joint_stress": {{"shoulder": N, "elbow": N, "wrist": N, "knee": N, "hip": N, "lower_back": N, "ankle": N}},
  "sport_carryover": {{"xc_mtb": N, "trail_run": N, "climbing": N, "ski": N, "snowboard": N}},
  "goal_carryover": {{"power": N, "strength": N, "hypertrophy": N, "endurance": N, "stability": N}}
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SCHEMA_DESCRIPTION,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def insert_exercise(cur, name, fields):
    cur.execute("""
        INSERT INTO exercises (
            name, source,
            movement_pattern, quality_focus,
            primary_muscles, secondary_muscles,
            equipment, skill_level, bilateral, contraction_type,
            systemic_fatigue, cns_load,
            joint_stress, sport_carryover, goal_carryover
        ) VALUES (
            %s, 'custom',
            %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (name) DO UPDATE SET
            movement_pattern  = EXCLUDED.movement_pattern,
            quality_focus     = EXCLUDED.quality_focus,
            primary_muscles   = EXCLUDED.primary_muscles,
            secondary_muscles = EXCLUDED.secondary_muscles,
            equipment         = EXCLUDED.equipment,
            skill_level       = EXCLUDED.skill_level,
            bilateral         = EXCLUDED.bilateral,
            contraction_type  = EXCLUDED.contraction_type,
            systemic_fatigue  = EXCLUDED.systemic_fatigue,
            cns_load          = EXCLUDED.cns_load,
            joint_stress      = EXCLUDED.joint_stress,
            sport_carryover   = EXCLUDED.sport_carryover,
            goal_carryover    = EXCLUDED.goal_carryover
        RETURNING exercise_id
    """, (
        name,
        fields["movement_pattern"],
        fields["quality_focus"],
        fields["primary_muscles"],
        fields["secondary_muscles"],
        fields["equipment"],
        fields["skill_level"],
        fields["bilateral"],
        fields["contraction_type"],
        fields["systemic_fatigue"],
        fields["cns_load"],
        json.dumps(fields["joint_stress"]),
        json.dumps(fields["sport_carryover"]),
        json.dumps(fields["goal_carryover"]),
    ))
    return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print labels without inserting")
    args = parser.parse_args()

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT DISTINCT name FROM strength_exercises ORDER BY name")
    exercises = [row[0] for row in cur.fetchall()]
    print(f"Found {len(exercises)} exercises to label.\n")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    results = []
    failed  = []

    for i, name in enumerate(exercises, 1):
        print(f"[{i}/{len(exercises)}] {name} ... ", end="", flush=True)
        try:
            fields = label_exercise(client, name)
            results.append((name, fields))
            print(f"✓  ({fields['movement_pattern']}, {fields['quality_focus']}, CNS {fields['cns_load']})")
        except Exception as e:
            print(f"✗  ERROR: {e}")
            failed.append(name)
        time.sleep(0.3)  # avoid rate limiting

    print(f"\n{len(results)} labeled, {len(failed)} failed.")

    if failed:
        print("Failed exercises:")
        for name in failed:
            print(f"  - {name}")

    if args.dry_run:
        print("\n-- DRY RUN — nothing inserted --")
        for name, fields in results:
            print(f"\n{name}:")
            print(json.dumps(fields, indent=2))
        cur.close()
        conn.close()
        return

    print("\nInserting into DB...")
    inserted = 0
    for name, fields in results:
        try:
            exercise_id = insert_exercise(cur, name, fields)
            inserted += 1
        except Exception as e:
            print(f"  DB error for '{name}': {e}")
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done — {inserted} exercises inserted/updated.")


if __name__ == "__main__":
    main()
