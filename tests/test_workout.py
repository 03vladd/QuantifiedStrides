"""Tests for workout data parsing and DB insertion logic."""

import pytest
import psycopg2
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Helpers — replicate field extraction logic from workout.py
# ---------------------------------------------------------------------------

def parse_start_time(start_time_str):
    """Mirror the two-format parsing in workout.py."""
    if not start_time_str:
        return None
    try:
        return datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")


def extract_workout_fields(activity: dict) -> dict:
    """Mirror the field extraction in workout.py so we can unit-test it."""
    start_time_str = activity.get("startTimeLocal")
    start_time_dt  = parse_start_time(start_time_str) if start_time_str else None
    duration_secs  = float(activity.get("duration", 0.0))
    end_time_dt    = (start_time_dt + timedelta(seconds=duration_secs)) if start_time_dt else None

    return {
        "sport":            activity.get("activityType", {}).get("typeKey", "Unknown"),
        "workout_type":     activity.get("activityName", "Unknown"),
        "start_time":       start_time_dt,
        "end_time":         end_time_dt,
        "workout_date":     start_time_dt.date() if start_time_dt else None,
        "calories_burned":  activity.get("calories", 0),
        "avg_heart_rate":   activity.get("averageHR", 0),
        "max_heart_rate":   activity.get("maxHR", 0),
        "vo2max":           activity.get("vO2MaxValue"),
        "lactate_threshold":activity.get("lactateThresholdBpm"),
        "time_in_zone_1":   activity.get("hrTimeInZone_1", 0.0),
        "time_in_zone_2":   activity.get("hrTimeInZone_2", 0.0),
        "time_in_zone_3":   activity.get("hrTimeInZone_3", 0.0),
        "time_in_zone_4":   activity.get("hrTimeInZone_4", 0.0),
        "time_in_zone_5":   activity.get("hrTimeInZone_5", 0.0),
        "training_volume":  activity.get("distance", 0.0),
        "avg_vertical_osc": activity.get("avgVerticalOscillation"),
        "avg_ground_contact": activity.get("avgGroundContactTime"),
        "avg_stride_length":  activity.get("avgStrideLength"),
        "avg_vertical_ratio": activity.get("avgVerticalRatio"),
        "avg_running_cadence": activity.get("averageRunningCadenceInStepsPerMinute"),
        "max_running_cadence": activity.get("maxRunningCadenceInStepsPerMinute"),
        "location":         activity.get("locationName", "Unknown"),
        "start_latitude":   activity.get("startLatitude"),
        "start_longitude":  activity.get("startLongitude"),
    }


# ---------------------------------------------------------------------------
# Tests — start_time parsing
# ---------------------------------------------------------------------------

class TestStartTimeParsing:
    def test_iso_format_with_T(self):
        dt = parse_start_time("2026-03-13T07:30:00")
        assert dt == datetime(2026, 3, 13, 7, 30, 0)

    def test_space_separated_format(self):
        dt = parse_start_time("2026-03-13 07:30:00")
        assert dt == datetime(2026, 3, 13, 7, 30, 0)

    def test_none_returns_none(self):
        assert parse_start_time(None) is None

    def test_empty_string_returns_none(self):
        assert parse_start_time("") is None


# ---------------------------------------------------------------------------
# Tests — field extraction
# ---------------------------------------------------------------------------

class TestWorkoutFieldExtraction:
    def test_normal_running_activity(self, mock_garmin_activity):
        fields = extract_workout_fields(mock_garmin_activity)
        assert fields["sport"] == "running"
        assert fields["workout_type"] == "Morning Run"
        assert fields["start_time"] == datetime(2026, 3, 13, 7, 30, 0)
        assert fields["end_time"] == datetime(2026, 3, 13, 8, 30, 0)
        assert fields["workout_date"].isoformat() == "2026-03-13"
        assert fields["calories_burned"] == 450
        assert fields["avg_heart_rate"] == 155
        assert fields["max_heart_rate"] == 180
        assert fields["vo2max"] == 52.0
        assert fields["lactate_threshold"] == 168
        assert fields["training_volume"] == 10500.0
        assert fields["start_latitude"] == 46.7667
        assert fields["start_longitude"] == 23.6000

    def test_end_time_calculated_from_duration(self, mock_garmin_activity):
        fields = extract_workout_fields(mock_garmin_activity)
        expected_end = datetime(2026, 3, 13, 7, 30, 0) + timedelta(seconds=3600.0)
        assert fields["end_time"] == expected_end

    def test_running_biomechanics_fields(self, mock_garmin_activity):
        fields = extract_workout_fields(mock_garmin_activity)
        assert fields["avg_vertical_osc"] == 8.2
        assert fields["avg_ground_contact"] == 245.0
        assert fields["avg_stride_length"] == 1.15
        assert fields["avg_vertical_ratio"] == 7.1
        assert fields["avg_running_cadence"] == 172.0
        assert fields["max_running_cadence"] == 185.0

    def test_missing_optional_fields_are_none(self):
        activity = {
            "activityType": {"typeKey": "strength_training"},
            "activityName": "Gym",
            "startTimeLocal": "2026-03-13T10:00:00",
            "duration": 3600.0,
        }
        fields = extract_workout_fields(activity)
        assert fields["vo2max"] is None
        assert fields["lactate_threshold"] is None
        assert fields["avg_vertical_osc"] is None
        assert fields["avg_running_cadence"] is None
        assert fields["start_latitude"] is None
        assert fields["start_longitude"] is None

    def test_missing_activity_type_defaults_to_unknown(self):
        activity = {"startTimeLocal": "2026-03-13T10:00:00", "duration": 0.0}
        fields = extract_workout_fields(activity)
        assert fields["sport"] == "Unknown"
        assert fields["workout_type"] == "Unknown"

    def test_hr_zones_default_to_zero(self):
        activity = {"startTimeLocal": "2026-03-13T10:00:00", "duration": 0.0}
        fields = extract_workout_fields(activity)
        for zone in range(1, 6):
            assert fields[f"time_in_zone_{zone}"] == 0.0

    def test_distance_defaults_to_zero(self):
        activity = {"startTimeLocal": "2026-03-13T10:00:00", "duration": 0.0}
        fields = extract_workout_fields(activity)
        assert fields["training_volume"] == 0.0


# ---------------------------------------------------------------------------
# Tests — DB insertion
# ---------------------------------------------------------------------------

class TestWorkoutDatabaseInsertion:
    def _insert(self, cur, fields):
        cur.execute("""
            INSERT INTO workouts (
                user_id, sport, start_time, end_time, workout_type,
                calories_burned, avg_heart_rate, max_heart_rate,
                vo2max_estimate, lactate_threshold_bpm,
                time_in_hr_zone_1, time_in_hr_zone_2, time_in_hr_zone_3,
                time_in_hr_zone_4, time_in_hr_zone_5,
                training_volume, avg_vertical_oscillation,
                avg_ground_contact_time, avg_stride_length, avg_vertical_ratio,
                avg_running_cadence, max_running_cadence,
                location, start_latitude, start_longitude, workout_date
            ) VALUES (
                1, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            ) RETURNING workout_id
        """, (
            fields["sport"], fields["start_time"], fields["end_time"],
            fields["workout_type"], fields["calories_burned"],
            fields["avg_heart_rate"], fields["max_heart_rate"],
            fields["vo2max"], fields["lactate_threshold"],
            fields["time_in_zone_1"], fields["time_in_zone_2"],
            fields["time_in_zone_3"], fields["time_in_zone_4"],
            fields["time_in_zone_5"], fields["training_volume"],
            fields["avg_vertical_osc"], fields["avg_ground_contact"],
            fields["avg_stride_length"], fields["avg_vertical_ratio"],
            fields["avg_running_cadence"], fields["max_running_cadence"],
            fields["location"], fields["start_latitude"],
            fields["start_longitude"], fields["workout_date"],
        ))
        return cur.fetchone()[0]

    def test_inserts_workout_and_returns_id(self, db, mock_garmin_activity):
        conn, cur = db
        fields = extract_workout_fields(mock_garmin_activity)
        workout_id = self._insert(cur, fields)
        assert workout_id is not None

        cur.execute(
            "SELECT sport, calories_burned, avg_heart_rate FROM workouts WHERE workout_id = %s",
            (workout_id,)
        )
        row = cur.fetchone()
        assert row[0] == "running"
        assert row[1] == 450
        assert row[2] == 155

    def test_duplicate_start_time_raises_unique_violation(self, db, mock_garmin_activity):
        conn, cur = db
        fields = extract_workout_fields(mock_garmin_activity)
        self._insert(cur, fields)
        with pytest.raises(psycopg2.errors.UniqueViolation):
            self._insert(cur, fields)

    def test_null_optional_columns_accepted(self, db):
        conn, cur = db
        cur.execute("""
            INSERT INTO workouts (user_id, sport, start_time, workout_date)
            VALUES (1, 'strength_training', '2026-01-20 09:00:00', '2026-01-20')
            RETURNING workout_id
        """)
        workout_id = cur.fetchone()[0]
        cur.execute(
            "SELECT vo2max_estimate, avg_running_cadence FROM workouts WHERE workout_id = %s",
            (workout_id,)
        )
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] is None
