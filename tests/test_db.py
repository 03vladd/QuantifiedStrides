"""Tests for db.py — connection and schema validation."""

import pytest
import psycopg2


class TestDatabaseConnection:
    def test_connects_successfully(self, db):
        conn, cur = db
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    def test_required_tables_exist(self, db):
        conn, cur = db
        tables = [
            "users", "workouts", "sleep_sessions", "environment_data",
            "daily_subjective", "workout_metrics", "strength_sessions",
            "strength_exercises", "strength_sets",
        ]
        for table in tables:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = %s)", (table,)
            )
            assert cur.fetchone()[0], f"Table '{table}' does not exist"

    def test_workouts_columns(self, db):
        conn, cur = db
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'workouts'"
        )
        cols = {row[0] for row in cur.fetchall()}
        required = {
            "workout_id", "user_id", "sport", "start_time", "end_time",
            "calories_burned", "avg_heart_rate", "training_volume",
            "start_latitude", "start_longitude", "workout_date",
        }
        assert required <= cols

    def test_sleep_sessions_columns(self, db):
        conn, cur = db
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'sleep_sessions'"
        )
        cols = {row[0] for row in cur.fetchall()}
        required = {
            "sleep_id", "user_id", "sleep_date", "duration_minutes",
            "sleep_score", "hrv", "rhr", "time_in_deep", "time_in_light",
            "time_in_rem", "time_awake", "overnight_hrv", "hrv_status",
            "body_battery_change",
        }
        assert required <= cols

    def test_strength_sets_columns(self, db):
        conn, cur = db
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'strength_sets'"
        )
        cols = {row[0] for row in cur.fetchall()}
        required = {
            "set_id", "exercise_id", "set_number", "reps",
            "duration_seconds", "weight_kg", "is_bodyweight", "band_color",
            "per_hand", "per_side", "plus_bar", "weight_includes_bar",
            "total_weight_kg",
        }
        assert required <= cols

    def test_unique_constraint_workouts(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO workouts (user_id, start_time, workout_date) "
            "VALUES (1, '2026-01-01 08:00:00', '2026-01-01')"
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO workouts (user_id, start_time, workout_date) "
                "VALUES (1, '2026-01-01 08:00:00', '2026-01-01')"
            )

    def test_unique_constraint_sleep(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO sleep_sessions (user_id, sleep_date) "
            "VALUES (1, '2026-01-01')"
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO sleep_sessions (user_id, sleep_date) "
                "VALUES (1, '2026-01-01')"
            )

    def test_unique_constraint_daily_subjective(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO daily_subjective (user_id, entry_date) "
            "VALUES (1, '2026-01-01')"
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO daily_subjective (user_id, entry_date) "
                "VALUES (1, '2026-01-01')"
            )

    def test_environment_data_nullable_workout_id(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO environment_data (workout_id, record_datetime, location) "
            "VALUES (NULL, NOW(), 'Test')"
        )
        cur.execute("SELECT workout_id FROM environment_data WHERE location = 'Test'")
        assert cur.fetchone()[0] is None
