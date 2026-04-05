"""One-time migration: set all user FKs to ON DELETE CASCADE."""
import psycopg2

conn = psycopg2.connect(host="localhost", dbname="quantifiedstrides", user="quantified", password="2026")
conn.autocommit = True
cur = conn.cursor()

statements = [
    # workouts children
    "ALTER TABLE environment_data DROP CONSTRAINT IF EXISTS environment_data_workout_id_fkey",
    "ALTER TABLE environment_data ADD CONSTRAINT environment_data_workout_id_fkey FOREIGN KEY (workout_id) REFERENCES workouts(workout_id) ON DELETE CASCADE",

    # users children — drop first
    "ALTER TABLE workouts           DROP CONSTRAINT IF EXISTS workouts_user_id_fkey",
    "ALTER TABLE sleep_sessions     DROP CONSTRAINT IF EXISTS sleep_sessions_user_id_fkey",
    "ALTER TABLE daily_readiness    DROP CONSTRAINT IF EXISTS daily_readiness_user_id_fkey",
    "ALTER TABLE daily_subjective   DROP CONSTRAINT IF EXISTS daily_subjective_user_id_fkey",
    "ALTER TABLE strength_sessions  DROP CONSTRAINT IF EXISTS strength_sessions_user_id_fkey",
    "ALTER TABLE workout_reflection DROP CONSTRAINT IF EXISTS workout_reflection_user_id_fkey",
    "ALTER TABLE user_profile       DROP CONSTRAINT IF EXISTS user_profile_user_id_fkey",
    "ALTER TABLE narrative_cache    DROP CONSTRAINT IF EXISTS narrative_cache_user_id_fkey",
    "ALTER TABLE injuries           DROP CONSTRAINT IF EXISTS injuries_user_id_fkey",
    "ALTER TABLE nutrition_log      DROP CONSTRAINT IF EXISTS nutrition_log_user_id_fkey",

    # re-add with CASCADE
    "ALTER TABLE workouts           ADD CONSTRAINT workouts_user_id_fkey           FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE sleep_sessions     ADD CONSTRAINT sleep_sessions_user_id_fkey     FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE daily_readiness    ADD CONSTRAINT daily_readiness_user_id_fkey    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE daily_subjective   ADD CONSTRAINT daily_subjective_user_id_fkey   FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE strength_sessions  ADD CONSTRAINT strength_sessions_user_id_fkey  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE workout_reflection ADD CONSTRAINT workout_reflection_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE user_profile       ADD CONSTRAINT user_profile_user_id_fkey       FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE narrative_cache    ADD CONSTRAINT narrative_cache_user_id_fkey    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE injuries           ADD CONSTRAINT injuries_user_id_fkey           FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
    "ALTER TABLE nutrition_log      ADD CONSTRAINT nutrition_log_user_id_fkey      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE",
]

for s in statements:
    cur.execute(s)
    print(f"OK: {s[:60]}")

conn.close()
print("Migration complete.")
