"""Tests for environment data parsing and coordinate selection logic."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers — replicate coordinate selection logic from environment.py
# ---------------------------------------------------------------------------

def select_coordinates(workout_row, ip_geo_response=None):
    """
    Mirror the coordinate selection logic in environment.py.

    workout_row: (workout_id, start_latitude, start_longitude, location) or None
    ip_geo_response: dict with 'loc' key (e.g. {"loc": "46.77,23.60", "city": "Cluj"})
                     or None to simulate IP geolocation failure

    Returns (lat, lon, location_name, workout_id)
    """
    workout_id = workout_row[0] if workout_row else None
    workout_lat = workout_row[1] if workout_row else None
    workout_lon = workout_row[2] if workout_row else None
    workout_location_name = workout_row[3] if workout_row else None

    if workout_lat and workout_lon:
        return workout_lat, workout_lon, workout_location_name, workout_id

    # IP fallback
    if ip_geo_response is not None:
        try:
            lat, lon = map(float, ip_geo_response["loc"].split(","))
            city = ip_geo_response.get("city", workout_location_name)
            return lat, lon, city, workout_id
        except Exception:
            pass

    return None, None, workout_location_name, workout_id


def extract_weather_fields(weather_data: dict, uv_data: dict) -> dict:
    """Mirror weather/UV extraction from environment.py."""
    return {
        "location":    weather_data.get("name", "Unknown"),
        "temperature": weather_data.get("main", {}).get("temp"),
        "wind_speed":  weather_data.get("wind", {}).get("speed"),
        "wind_direction": weather_data.get("wind", {}).get("deg"),
        "humidity":    weather_data.get("main", {}).get("humidity"),
        "precipitation": weather_data.get("rain", {}).get("1h", 0)
                         if "rain" in weather_data else 0,
        "uv_index":    uv_data.get("current", {}).get("uvi", 0),
    }


def extract_pollen_fields(pollen_current: dict) -> dict:
    """Mirror pollen extraction from environment.py."""
    return {
        "grass_pollen": pollen_current.get("grass_pollen"),
        "tree_pollen":  pollen_current.get("birch_pollen"),
        "weed_pollen":  pollen_current.get("ragweed_pollen"),
    }


# ---------------------------------------------------------------------------
# Coordinate selection tests
# ---------------------------------------------------------------------------

class TestCoordinateSelection:
    def test_uses_workout_gps_when_available(self):
        row = (42, 46.7667, 23.6000, "Cluj-Napoca")
        lat, lon, loc, wid = select_coordinates(row)
        assert lat == 46.7667
        assert lon == 23.6000
        assert loc == "Cluj-Napoca"
        assert wid == 42

    def test_falls_back_to_ip_when_no_gps(self):
        row = (42, None, None, "Cluj-Napoca")
        ip_resp = {"loc": "46.77,23.60", "city": "Cluj"}
        lat, lon, loc, wid = select_coordinates(row, ip_resp)
        assert lat == pytest.approx(46.77)
        assert lon == pytest.approx(23.60)
        assert loc == "Cluj"

    def test_rest_day_no_workout_row_falls_back_to_ip(self):
        ip_resp = {"loc": "44.43,26.10", "city": "Bucharest"}
        lat, lon, loc, wid = select_coordinates(None, ip_resp)
        assert lat == pytest.approx(44.43)
        assert lon == pytest.approx(26.10)
        assert wid is None

    def test_ip_failure_returns_none_coordinates(self):
        row = (42, None, None, "Cluj-Napoca")
        lat, lon, loc, wid = select_coordinates(row, None)
        assert lat is None
        assert lon is None

    def test_workout_id_none_on_rest_day(self):
        ip_resp = {"loc": "46.77,23.60", "city": "Cluj"}
        _, _, _, wid = select_coordinates(None, ip_resp)
        assert wid is None

    def test_workout_id_preserved_from_row(self):
        row = (99, 46.7667, 23.6000, "Cluj-Napoca")
        _, _, _, wid = select_coordinates(row)
        assert wid == 99

    def test_zero_coordinates_treated_as_falsy_uses_ip(self):
        """GPS coords of 0,0 (Gulf of Guinea) should not be used — treat as missing."""
        row = (5, 0.0, 0.0, "Unknown")
        ip_resp = {"loc": "46.77,23.60", "city": "Cluj"}
        lat, lon, _, _ = select_coordinates(row, ip_resp)
        # 0.0 is falsy so IP fallback fires
        assert lat == pytest.approx(46.77)


# ---------------------------------------------------------------------------
# Weather / UV extraction tests
# ---------------------------------------------------------------------------

class TestWeatherFieldExtraction:
    def test_normal_response(self, mock_weather_response, mock_uv_response):
        fields = extract_weather_fields(mock_weather_response, mock_uv_response)
        assert fields["location"] == "Cluj-Napoca"
        assert fields["temperature"] == 12.5
        assert fields["wind_speed"] == 3.2
        assert fields["wind_direction"] == 220
        assert fields["humidity"] == 65
        assert fields["uv_index"] == 3.5

    def test_no_rain_key_defaults_precipitation_to_zero(self, mock_uv_response):
        weather = {"name": "Cluj", "main": {"temp": 10.0, "humidity": 50}, "wind": {"speed": 1.0, "deg": 90}}
        fields = extract_weather_fields(weather, mock_uv_response)
        assert fields["precipitation"] == 0

    def test_rain_present_extracts_1h(self, mock_uv_response):
        weather = {
            "name": "Cluj", "main": {"temp": 8.0, "humidity": 80},
            "wind": {"speed": 2.0, "deg": 180}, "rain": {"1h": 2.5}
        }
        fields = extract_weather_fields(weather, mock_uv_response)
        assert fields["precipitation"] == 2.5

    def test_missing_uv_defaults_to_zero(self, mock_weather_response):
        fields = extract_weather_fields(mock_weather_response, {})
        assert fields["uv_index"] == 0

    def test_empty_weather_response_does_not_crash(self):
        fields = extract_weather_fields({}, {})
        assert fields["temperature"] is None
        assert fields["wind_speed"] is None
        assert fields["location"] == "Unknown"


# ---------------------------------------------------------------------------
# Pollen extraction tests
# ---------------------------------------------------------------------------

class TestPollenFieldExtraction:
    def test_normal_response(self, mock_pollen_response):
        fields = extract_pollen_fields(mock_pollen_response["current"])
        assert fields["grass_pollen"] == 12.0
        assert fields["tree_pollen"] == 5.0
        assert fields["weed_pollen"] == 2.0

    def test_empty_pollen_response_returns_none(self):
        fields = extract_pollen_fields({})
        assert fields["grass_pollen"] is None
        assert fields["tree_pollen"] is None
        assert fields["weed_pollen"] is None


# ---------------------------------------------------------------------------
# DB insertion tests
# ---------------------------------------------------------------------------

class TestEnvironmentDatabaseInsertion:
    def test_inserts_with_null_workout_id(self, db):
        conn, cur = db
        cur.execute("""
            INSERT INTO environment_data (
                workout_id, record_datetime, location,
                temperature, wind_speed, wind_direction, humidity,
                precipitation, grass_pollen, tree_pollen, weed_pollen, uv_index
            ) VALUES (NULL, NOW(), 'Cluj-Napoca', 12.5, 3.2, 220, 65, 0.0, 12.0, 5.0, 2.0, 3.5)
            RETURNING env_id
        """)
        env_id = cur.fetchone()[0]
        assert env_id is not None

        cur.execute("SELECT workout_id, temperature FROM environment_data WHERE env_id = %s", (env_id,))
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] == 12.5

    def test_inserts_with_valid_workout_id(self, db):
        conn, cur = db
        cur.execute(
            "INSERT INTO workouts (user_id, sport, start_time, workout_date) "
            "VALUES (1, 'running', '2026-01-05 08:00:00', '2026-01-05') RETURNING workout_id"
        )
        wid = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO environment_data (workout_id, record_datetime, location)
            VALUES (%s, NOW(), 'Cluj') RETURNING env_id
        """, (wid,))
        env_id = cur.fetchone()[0]
        assert env_id is not None

        cur.execute("SELECT workout_id FROM environment_data WHERE env_id = %s", (env_id,))
        assert cur.fetchone()[0] == wid

    def test_pollen_columns_accept_null(self, db):
        conn, cur = db
        cur.execute("""
            INSERT INTO environment_data (
                workout_id, record_datetime, location,
                grass_pollen, tree_pollen, weed_pollen
            ) VALUES (NULL, NOW(), 'Unknown', NULL, NULL, NULL)
            RETURNING env_id
        """)
        env_id = cur.fetchone()[0]
        cur.execute(
            "SELECT grass_pollen, tree_pollen, weed_pollen FROM environment_data WHERE env_id = %s",
            (env_id,)
        )
        row = cur.fetchone()
        assert all(v is None for v in row)
