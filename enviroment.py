from datetime import datetime, timedelta
import pyodbc
import requests
import json

# API Configuration
OPENWEATHER_API_KEY = "819ff67a3fe8e6af5f825bb2688729d9"
AMBEE_API_KEY = "18659f688d4744d922beeb2bb44df415532241b138fe8ca07cae8b387009cd2b"

# 1) Database connection
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=QuantifiedStridesDB;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
print("Cursor connected")

# 2) Get today's date for workout matching
today = datetime.now().date()
print(f"Collecting environmental data for: {today}")

# 3) ALWAYS create a workout for today if one doesn't exist
workout_id = None  # Initialize to None

try:
    # First check if a workout for today already exists
    cursor.execute("SELECT WorkoutID FROM Workouts WHERE WorkoutDate = ?", (today,))
    row = cursor.fetchone()

    if row:
        workout_id = row[0]
        print(f"Found workout from today with ID: {workout_id}")
    else:
        # ALWAYS create a new workout if none exists for today
        print("No workouts found for today. Creating a placeholder workout...")
        placeholder_sql = """
        INSERT INTO Workouts (
            UserID, Sport, StartTime, EndTime, WorkoutType, 
            CaloriesBurned, AvgHeartRate, MaxHeartRate, 
            TrainingVolume, Location, WorkoutDate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        current_time = datetime.now()
        cursor.execute(
            placeholder_sql,
            (
                1,  # UserID
                "other",  # Sport
                current_time,  # StartTime
                current_time,  # EndTime
                "Environmental Data Collection",  # WorkoutType
                0,  # CaloriesBurned
                0,  # AvgHeartRate
                0,  # MaxHeartRate
                0,  # TrainingVolume
                "Cluj-Napoca",  # Location
                today  # WorkoutDate
            )
        )
        conn.commit()

        # Get the ID of the placeholder workout we just created
        cursor.execute("SELECT SCOPE_IDENTITY()")
        workout_id = cursor.fetchone()[0]
        print(f"Created placeholder workout with ID: {workout_id}")

    # Verify that we have a valid workout ID before proceeding
    if workout_id is None:
        raise ValueError("Failed to get or create a valid workout ID")

except Exception as e:
    print(f"Error managing workout ID: {e}")
    conn.close()
    raise

# 4) Get current location coordinates (Cluj-Napoca)
DEFAULT_LAT = 46.7667
DEFAULT_LON = 23.6000

# 5) Get current weather data from OpenWeatherMap
weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={DEFAULT_LAT}&lon={DEFAULT_LON}&units=metric&appid={OPENWEATHER_API_KEY}"
weather_response = requests.get(weather_url)
weather_data = weather_response.json()

# 6) Get UV Index from OpenWeatherMap One Call API
uv_url = f"https://api.openweathermap.org/data/2.5/onecall?lat={DEFAULT_LAT}&lon={DEFAULT_LON}&exclude=minutely,hourly,daily,alerts&appid={OPENWEATHER_API_KEY}"
uv_response = requests.get(uv_url)
uv_data = uv_response.json()

# 7) Get pollen data from Ambee API
pollen_url = f"https://api.ambeedata.com/latest/pollen/by-lat-lng?lat={DEFAULT_LAT}&lng={DEFAULT_LON}"
pollen_headers = {
    "x-api-key": AMBEE_API_KEY,
    "Content-type": "application/json"
}
pollen_response = requests.get(pollen_url, headers=pollen_headers)
pollen_data = pollen_response.json()

# 8) Extract the needed data
# Location from weather data
location = weather_data.get("name", "Cluj-Napoca")

# Temperature in Celsius
temperature = weather_data.get("main", {}).get("temp")

# Wind data
wind_speed = weather_data.get("wind", {}).get("speed")
wind_direction = weather_data.get("wind", {}).get("deg")

# Humidity percentage
humidity = weather_data.get("main", {}).get("humidity")

# Precipitation (rain in last hour if available)
precipitation = weather_data.get("rain", {}).get("1h", 0) if "rain" in weather_data else 0

# Get UV index from one call API
uv_index = uv_data.get("current", {}).get("uvi", 0)

# Get pollen data - calculate average from the three main types
pollen_values = pollen_data.get("data", [{}])[0]
pollen_index = (
                       pollen_values.get("grass_pollen", 0) +
                       pollen_values.get("tree_pollen", 0) +
                       pollen_values.get("weed_pollen", 0)
               ) / 3  # Simple average of the three main pollen types

# Current time
record_date_time = datetime.now()

# 9) Create SQL insert statement
sql_insert = """
INSERT INTO EnvironmentData (
    WorkoutID,
    RecordDateTime,
    Location,
    Temperature,
    WindSpeed,
    WindDirection,
    Humidity,
    Precipitation,
    PollenIndex,
    UVIndex,
    SubjectiveNotes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# 10) Execute insert with current values - ONLY if we have a valid workout_id
try:
    # Extra verification before insert
    if workout_id is None:
        raise ValueError("Cannot insert environment data without a valid WorkoutID")

    cursor.execute(
        sql_insert,
        (
            workout_id,  # Using the workout ID from today
            record_date_time,
            location,
            temperature,
            wind_speed,
            wind_direction,
            humidity,
            precipitation,
            pollen_index,
            uv_index,
            "Daily environment check"  # Default note
        )
    )

    conn.commit()
    print(f"Environmental data for {location} recorded successfully!")
    print(f"Temperature: {temperature}°C")
    print(f"Wind: {wind_speed} m/s, Direction: {wind_direction}°")
    print(f"Humidity: {humidity}%")
    print(f"Precipitation: {precipitation} mm")
    print(f"Pollen Index: {pollen_index}")
    print(f"UV Index: {uv_index}")

except Exception as e:
    conn.rollback()
    print(f"Error inserting environmental data: {e}")

finally:
    cursor.close()
    conn.close()