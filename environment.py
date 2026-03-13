from datetime import datetime

import requests

from config import OPENWEATHER_API_KEY
from db import get_connection

conn = get_connection()
cursor = conn.cursor()
print("Cursor connected")

today = datetime.now().date()
print(f"Collecting environmental data for: {today}")

# Skip if environment data for today already exists
cursor.execute(
    "SELECT env_id FROM environment_data WHERE record_datetime::date = %s",
    (today,)
)
if cursor.fetchone():
    print(f"Environment data for {today} already recorded. Skipping.")
    cursor.close()
    conn.close()
    raise SystemExit(0)

# Link to today's workout if one exists — NULL on rest days (no placeholder created)
cursor.execute(
    "SELECT workout_id, start_latitude, start_longitude, location FROM workouts WHERE workout_date = %s AND user_id = 1",
    (today,)
)
row = cursor.fetchone()
workout_id = row[0] if row else None
workout_lat = row[1] if row else None
workout_lon = row[2] if row else None
workout_location_name = row[3] if row else None

if workout_id:
    print(f"Linking environment data to workout ID: {workout_id}")
else:
    print("No workout today — recording environment data as standalone (rest day).")

# Determine coordinates:
# 1. Use workout GPS if available (outdoor activity with start coordinates)
# 2. Fall back to IP geolocation (reflects actual current location)
if workout_lat and workout_lon:
    lat, lon = workout_lat, workout_lon
    print(f"Using workout GPS coordinates: {lat}, {lon}")
else:
    try:
        geo = requests.get("https://ipinfo.io/json", timeout=5).json()
        lat, lon = map(float, geo["loc"].split(","))
        workout_location_name = geo.get("city", workout_location_name)
        print(f"Using IP geolocation: {workout_location_name} ({lat}, {lon})")
    except Exception as e:
        print(f"Warning: IP geolocation failed ({e}). Coordinates unavailable.")
        lat = lon = None

if lat is None or lon is None:
    print("No coordinates available — cannot collect environment data.")
    cursor.close()
    conn.close()
    raise SystemExit(1)

# Current weather
weather_url = (
    f"https://api.openweathermap.org/data/2.5/weather"
    f"?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_API_KEY}"
)
weather_data = requests.get(weather_url).json()

# UV index
uv_url = (
    f"https://api.openweathermap.org/data/2.5/onecall"
    f"?lat={lat}&lon={lon}&exclude=minutely,hourly,daily,alerts&appid={OPENWEATHER_API_KEY}"
)
uv_data = requests.get(uv_url).json()

# Pollen (Open-Meteo Air Quality — no API key required)
try:
    pollen_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&current=grass_pollen,birch_pollen,ragweed_pollen"
    )
    pollen_data = requests.get(pollen_url, timeout=10).json().get("current", {})
    grass_pollen = pollen_data.get("grass_pollen")
    tree_pollen = pollen_data.get("birch_pollen")
    weed_pollen = pollen_data.get("ragweed_pollen")
except Exception as e:
    print(f"Warning: Open-Meteo pollen unavailable ({e}). Storing NULL.")
    grass_pollen = tree_pollen = weed_pollen = None

location = weather_data.get("name") or workout_location_name or "Unknown"
temperature = weather_data.get("main", {}).get("temp")
wind_speed = weather_data.get("wind", {}).get("speed")
wind_direction = weather_data.get("wind", {}).get("deg")
humidity = weather_data.get("main", {}).get("humidity")
precipitation = weather_data.get("rain", {}).get("1h", 0) if "rain" in weather_data else 0
uv_index = uv_data.get("current", {}).get("uvi", 0)
record_datetime = datetime.now()

sql_insert = """
INSERT INTO environment_data (
    workout_id,
    record_datetime,
    location,
    temperature,
    wind_speed,
    wind_direction,
    humidity,
    precipitation,
    grass_pollen,
    tree_pollen,
    weed_pollen,
    uv_index,
    subjective_notes
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

try:
    cursor.execute(sql_insert, (
        workout_id,
        record_datetime,
        location,
        temperature,
        wind_speed,
        wind_direction,
        humidity,
        precipitation,
        grass_pollen,
        tree_pollen,
        weed_pollen,
        uv_index,
        "Daily environment check",
    ))
    conn.commit()
    print(f"Environmental data for {location} recorded successfully!")
    print(f"Temperature: {temperature}°C, Wind: {wind_speed} m/s at {wind_direction}°")
    print(f"Humidity: {humidity}%, Precipitation: {precipitation} mm")
    print(f"Pollen — grass: {grass_pollen}, tree: {tree_pollen}, weed: {weed_pollen} grains/m³")
    print(f"UV Index: {uv_index}")
except Exception as e:
    conn.rollback()
    print(f"Error inserting environmental data: {e}")
finally:
    cursor.close()
    conn.close()
