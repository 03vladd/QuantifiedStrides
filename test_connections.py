"""
Connectivity smoke-test — verifies all four external dependencies are reachable
without writing any data to the database.

Run with:  python test_connections.py
"""

import sys
import psycopg2
import requests
import garminconnect
from config import (
    GARMIN_EMAIL, GARMIN_PASSWORD,
    OPENWEATHER_API_KEY,
    DB_HOST, DB_NAME, DB_USER, DB_PASSWORD,
)

PASS = "[PASS]"
FAIL = "[FAIL]"

LAT, LON = 46.7667, 23.6000


def test_postgresql():
    print("\n--- PostgreSQL ---")
    try:
        conn = psycopg2.connect(
            host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"{PASS} Connected. Tables found: {', '.join(sorted(tables))}")
        return True
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


def test_garmin():
    print("\n--- Garmin Connect ---")
    try:
        client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        client.login()
        profile = client.get_full_name()
        activities = client.get_activities(0, 1)
        latest = activities[0].get("activityName", "unknown") if activities else "no activities"
        print(f"{PASS} Logged in as: {profile}")
        print(f"      Latest activity: {latest}")
        return True, client
    except Exception as e:
        print(f"{FAIL} {e}")
        return False, None


def test_openweathermap():
    print("\n--- OpenWeatherMap ---")
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={LAT}&lon={LON}&units=metric&appid={OPENWEATHER_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        print(f"{PASS} {data.get('name')}: {temp}°C, {desc}")
        return True
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


def test_open_meteo():
    print("\n--- Open-Meteo Pollen ---")
    try:
        url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality"
            f"?latitude={LAT}&longitude={LON}&current=grass_pollen,birch_pollen,ragweed_pollen"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        current = r.json().get("current", {})
        grass = current.get("grass_pollen", "n/a")
        tree = current.get("birch_pollen", "n/a")
        weed = current.get("ragweed_pollen", "n/a")
        print(f"{PASS} Grass: {grass}, Tree (birch): {tree}, Weed (ragweed): {weed} grains/m³")
        return True
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


if __name__ == "__main__":
    print("====== QuantifiedStrides connection tests ======")

    sql_ok = test_postgresql()
    garmin_ok, _ = test_garmin()
    weather_ok = test_openweathermap()
    pollen_ok = test_open_meteo()

    print("\n====== Summary ======")
    results = {
        "PostgreSQL":        sql_ok,
        "Garmin Connect":    garmin_ok,
        "OpenWeatherMap":    weather_ok,
        "Open-Meteo Pollen": pollen_ok,
    }
    all_passed = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status} {name}")
        if not ok:
            all_passed = False

    print()
    sys.exit(0 if all_passed else 1)
