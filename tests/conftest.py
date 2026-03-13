"""
Shared pytest fixtures for QuantifiedStrides test suite.
"""

import os
import pytest
import psycopg2
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env_vars():
    """Ensure required env vars are set for all tests."""
    env = {
        "GARMIN_EMAIL": "test@example.com",
        "GARMIN_PASSWORD": "testpassword",
        "OPENWEATHER_API_KEY": "test_api_key",
        "DB_HOST": "localhost",
        "DB_NAME": "quantifiedstrides",
        "DB_USER": "quantified",
        "DB_PASSWORD": "2026",
    }
    with patch.dict(os.environ, env):
        yield


# ---------------------------------------------------------------------------
# Database — transactional isolation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_conn():
    """Single real DB connection for the test session."""
    conn = psycopg2.connect(
        host="localhost", dbname="quantifiedstrides",
        user="quantified", password="2026",
    )
    yield conn
    conn.close()


@pytest.fixture
def db(db_conn):
    """
    Per-test DB cursor inside a savepoint.
    All changes are rolled back after each test — no test data leaks.
    """
    db_conn.autocommit = False
    cur = db_conn.cursor()
    yield db_conn, cur
    db_conn.rollback()
    cur.close()


# ---------------------------------------------------------------------------
# Mock Garmin client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_garmin_activity():
    return {
        "activityType": {"typeKey": "running"},
        "activityName": "Morning Run",
        "startTimeLocal": "2026-03-13T07:30:00",
        "duration": 3600.0,
        "calories": 450,
        "averageHR": 155,
        "maxHR": 180,
        "vO2MaxValue": 52.0,
        "lactateThresholdBpm": 168,
        "hrTimeInZone_1": 300,
        "hrTimeInZone_2": 600,
        "hrTimeInZone_3": 1200,
        "hrTimeInZone_4": 900,
        "hrTimeInZone_5": 600,
        "distance": 10500.0,
        "avgVerticalOscillation": 8.2,
        "avgGroundContactTime": 245.0,
        "avgStrideLength": 1.15,
        "avgVerticalRatio": 7.1,
        "averageRunningCadenceInStepsPerMinute": 172.0,
        "maxRunningCadenceInStepsPerMinute": 185.0,
        "locationName": "Cluj-Napoca",
        "startLatitude": 46.7667,
        "startLongitude": 23.6000,
    }


@pytest.fixture
def mock_garmin_sleep():
    return {
        "dailySleepDTO": {
            "deepSleepSeconds": 3600,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 600,
            "avgSleepStress": 12.5,
            "sleepScoreFeedback": "POSITIVE_RECOVERING",
            "sleepScoreInsight": "POSITIVE_LATE_BED_TIME",
            "sleepScores": {
                "overall": {"value": 85, "qualifierKey": "GOOD"}
            },
        },
        "avgOvernightHrv": 78.0,
        "restingHeartRate": 52,
        "hrvStatus": "BALANCED",
        "bodyBatteryChange": 35,
        "sleepScore": 85,
    }


@pytest.fixture
def mock_garmin_client(mock_garmin_activity, mock_garmin_sleep):
    client = MagicMock()
    client.get_activities.return_value = [mock_garmin_activity]
    client.get_activities_by_date.return_value = [mock_garmin_activity]
    client.get_sleep_data.return_value = mock_garmin_sleep
    return client


# ---------------------------------------------------------------------------
# Mock weather / pollen API responses
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_weather_response():
    return {
        "name": "Cluj-Napoca",
        "main": {"temp": 12.5, "humidity": 65},
        "wind": {"speed": 3.2, "deg": 220},
        "rain": {"1h": 0.0},
    }


@pytest.fixture
def mock_uv_response():
    return {"current": {"uvi": 3.5}}


@pytest.fixture
def mock_pollen_response():
    return {
        "current": {
            "grass_pollen": 12.0,
            "birch_pollen": 5.0,
            "ragweed_pollen": 2.0,
        }
    }
