"""
Connectivity smoke-test — verifies all four external dependencies are reachable
without writing any data to the database.

Run with:  python test_connections.py
"""

import sys
import requests
import pyodbc
import garminconnect
from config import GARMIN_EMAIL, GARMIN_PASSWORD, OPENWEATHER_API_KEY, AMBEE_API_KEY

PASS = "[PASS]"
FAIL = "[FAIL]"

LAT, LON = 46.7667, 23.6000


def test_sql_server():
    print("\n--- SQL Server ---")
    try:
        conn = pyodbc.connect(
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=localhost;"
            "Database=QuantifiedStridesDB;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"{PASS} Connected. Tables found: {', '.join(tables)}")
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


def test_ambee():
    print("\n--- Ambee Pollen ---")
    try:
        url = f"https://api.ambeedata.com/latest/pollen/by-lat-lng?lat={LAT}&lng={LON}"
        headers = {"x-api-key": AMBEE_API_KEY, "Content-type": "application/json"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        entry = data.get("data", [{}])[0]
        grass = entry.get("grass_pollen", "n/a")
        tree = entry.get("tree_pollen", "n/a")
        weed = entry.get("weed_pollen", "n/a")
        print(f"{PASS} Grass: {grass}, Tree: {tree}, Weed: {weed}")
        return True
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


if __name__ == "__main__":
    print("====== QuantifiedStrides connection tests ======")

    sql_ok = test_sql_server()
    garmin_ok, _ = test_garmin()
    weather_ok = test_openweathermap()
    ambee_ok = test_ambee()

    print("\n====== Summary ======")
    results = {
        "SQL Server":     sql_ok,
        "Garmin Connect": garmin_ok,
        "OpenWeatherMap": weather_ok,
        "Ambee Pollen":   ambee_ok,
    }
    all_passed = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status} {name}")
        if not ok:
            all_passed = False

    print()
    sys.exit(0 if all_passed else 1)
