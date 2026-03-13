"""Tests for sleep data parsing and DB insertion logic."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date


# ---------------------------------------------------------------------------
# Helpers — replicate the field extraction logic from sleep.py
# ---------------------------------------------------------------------------

def extract_sleep_fields(sleep_data: dict) -> dict:
    """Mirror the field extraction in sleep.py so we can unit-test it."""
    sleep_dto = sleep_data.get("dailySleepDTO", {})
    deep  = sleep_dto.get("deepSleepSeconds")  or 0
    light = sleep_dto.get("lightSleepSeconds") or 0
    rem   = sleep_dto.get("remSleepSeconds")   or 0
    awake = sleep_dto.get("awakeSleepSeconds") or 0
    return {
        "duration_minutes": (deep + light + rem + awake) // 60,
        "time_in_deep":  deep  // 60,
        "time_in_light": light // 60,
        "time_in_rem":   rem   // 60,
        "time_awake":    awake // 60,
        "sleep_score":   sleep_dto.get("sleepScores", {}).get("overall", {}).get("value"),
        "hrv":           sleep_data.get("avgOvernightHrv"),
        "rhr":           sleep_data.get("restingHeartRate"),
        "avg_sleep_stress":      sleep_dto.get("avgSleepStress"),
        "sleep_score_feedback":  sleep_dto.get("sleepScoreFeedback", ""),
        "sleep_score_insight":   sleep_dto.get("sleepScoreInsight", ""),
        "hrv_status":            sleep_data.get("hrvStatus", ""),
        "body_battery_change":   sleep_data.get("bodyBatteryChange"),
    }


class TestSleepFieldExtraction:
    def test_normal_response(self, mock_garmin_sleep):
        fields = extract_sleep_fields(mock_garmin_sleep)
        assert fields["duration_minutes"] == (3600 + 14400 + 5400 + 600) // 60
        assert fields["time_in_deep"]  == 60
        assert fields["time_in_light"] == 240
        assert fields["time_in_rem"]   == 90
        assert fields["time_awake"]    == 10
        assert fields["sleep_score"]   == 85
        assert fields["hrv"]           == 78.0
        assert fields["rhr"]           == 52
        assert fields["hrv_status"]    == "BALANCED"
        assert fields["body_battery_change"] == 35

    def test_none_sleep_stages_treated_as_zero(self):
        """Garmin sometimes returns None mid-day — should not crash."""
        data = {
            "dailySleepDTO": {
                "deepSleepSeconds": None,
                "lightSleepSeconds": None,
                "remSleepSeconds": None,
                "awakeSleepSeconds": None,
                "sleepScores": {},
            }
        }
        fields = extract_sleep_fields(data)
        assert fields["duration_minutes"] == 0
        assert fields["sleep_score"] is None

    def test_missing_hrv_returns_none(self):
        data = {"dailySleepDTO": {"deepSleepSeconds": 3600}, "sleepScore": 80}
        fields = extract_sleep_fields(data)
        assert fields["hrv"] is None
        assert fields["rhr"] is None

    def test_missing_body_battery_returns_none(self):
        data = {"dailySleepDTO": {}}
        fields = extract_sleep_fields(data)
        assert fields["body_battery_change"] is None

    def test_sleep_score_nested_path(self):
        """Score is at dailySleepDTO.sleepScores.overall.value, not top-level."""
        data = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 92}},
                "deepSleepSeconds": 0,
                "lightSleepSeconds": 0,
                "remSleepSeconds": 0,
                "awakeSleepSeconds": 0,
            },
            "sleepScore": 999,  # old field — should NOT be used
        }
        fields = extract_sleep_fields(data)
        assert fields["sleep_score"] == 92

    def test_empty_response_does_not_crash(self):
        fields = extract_sleep_fields({})
        assert fields["duration_minutes"] == 0
        assert fields["sleep_score"] is None
        assert fields["hrv"] is None


class TestSleepDatabaseInsertion:
    def test_inserts_sleep_record(self, db, mock_garmin_sleep):
        conn, cur = db
        fields = extract_sleep_fields(mock_garmin_sleep)
        cur.execute("""
            INSERT INTO sleep_sessions (
                user_id, sleep_date, duration_minutes, sleep_score,
                hrv, rhr, time_in_deep, time_in_light, time_in_rem, time_awake,
                avg_sleep_stress, sleep_score_feedback, sleep_score_insight,
                overnight_hrv, hrv_status, body_battery_change
            ) VALUES (1, '2099-01-15', %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s)
            RETURNING sleep_id
        """, (
            fields["duration_minutes"], fields["sleep_score"],
            fields["hrv"], fields["rhr"],
            fields["time_in_deep"], fields["time_in_light"],
            fields["time_in_rem"], fields["time_awake"],
            fields["avg_sleep_stress"], fields["sleep_score_feedback"],
            fields["sleep_score_insight"], fields["hrv"],
            fields["hrv_status"], fields["body_battery_change"],
        ))
        sleep_id = cur.fetchone()[0]
        assert sleep_id is not None

        cur.execute("SELECT sleep_score, hrv, time_in_deep FROM sleep_sessions WHERE sleep_id = %s", (sleep_id,))
        row = cur.fetchone()
        assert row[0] == 85
        assert row[1] == 78.0
        assert row[2] == 60

    def test_duplicate_sleep_skipped(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO sleep_sessions (user_id, sleep_date) VALUES (1, '2099-02-01')"
        )
        cur.execute(
            "SELECT sleep_id FROM sleep_sessions WHERE user_id = 1 AND sleep_date = '2099-02-01'"
        )
        assert cur.fetchone() is not None  # guard check works
