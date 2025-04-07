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

# 3) Find or create a workout for today
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

# Initialize default pollen data
pollen_data = {"data": [{}]}
try:
    pollen_response = requests.get(pollen_url, headers=pollen_headers, timeout=10)
    print(f"Pollen API status code: {pollen_response.status_code}")
    print(f"Pollen API raw response: {pollen_response.text}")

    if pollen_response.status_code == 200:
        try:
            pollen_data = pollen_response.json()
            print(f"Parsed pollen data: {pollen_data}")
            print("Successfully retrieved pollen data from API")
        except json.JSONDecodeError as json_err:
            print(f"Error decoding JSON from pollen API: {json_err}")
            print(f"Response content type: {pollen_response.headers.get('Content-Type', 'unknown')}")
    else:
        print(f"Failed to get pollen data. Status code: {pollen_response.status_code}")
        print(f"Response: {pollen_response.text[:200]}...")  # Print first 200 chars of response
except Exception as e:
    print(f"Error getting pollen data: {e}")

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


# Function to assess risk level based on pollen counts
def get_risk_level(count):
    if count < 10:
        return "Low"
    elif count < 30:
        return "Moderate"
    else:
        return "High"


# Get detailed pollen data from Ambee
pollen_values = pollen_data.get("data", [{}])[0]

# Check if we have actual pollen data
has_pollen_data = bool(pollen_values)
if not has_pollen_data:
    print("Warning: Using default/fallback values for pollen data")

# Extract pollen counts and risk levels from the correct structure
count_data = pollen_values.get("Count", {})
risk_data = pollen_values.get("Risk", {})

# Extract specific pollen types from Count data
grass_pollen = count_data.get("grass_pollen", 0)
tree_pollen = count_data.get("tree_pollen", 0)
weed_pollen = count_data.get("weed_pollen", 0)

# Get risk levels directly from API if available, otherwise calculate
grass_pollen_risk = risk_data.get("grass_pollen", get_risk_level(grass_pollen))
tree_pollen_risk = risk_data.get("tree_pollen", get_risk_level(tree_pollen))
weed_pollen_risk = risk_data.get("weed_pollen", get_risk_level(weed_pollen))

# If everything returned 0, we might need an alternative data source
if (grass_pollen == 0 and tree_pollen == 0 and weed_pollen == 0) and not any(risk_data.values()):
    # Only use fallbacks if both counts AND risk levels are missing/zero
    current_month = datetime.now().month
    # Simple seasonal pattern (Northern Hemisphere)
    if 3 <= current_month <= 5:  # Spring: tree pollen high
        tree_pollen = 25
        grass_pollen = 10
        weed_pollen = 5
    elif 6 <= current_month <= 8:  # Summer: grass pollen high
        tree_pollen = 5
        grass_pollen = 30
        weed_pollen = 15
    elif 9 <= current_month <= 11:  # Fall: weed pollen high
        tree_pollen = 2
        grass_pollen = 5
        weed_pollen = 25
    else:  # Winter: all low
        tree_pollen = 2
        grass_pollen = 2
        weed_pollen = 2

    grass_pollen_risk = get_risk_level(grass_pollen)
    tree_pollen_risk = get_risk_level(tree_pollen)
    weed_pollen_risk = get_risk_level(weed_pollen)
    print(f"Using seasonal estimates for pollen data (Month: {current_month})")
else:
    print(f"Using actual pollen data from API: Grass={grass_pollen}, Tree={tree_pollen}, Weed={weed_pollen}")

# Calculate total pollen index (average)
total_pollen_index = (grass_pollen + tree_pollen + weed_pollen) / 3

# Final pollen index (same as total_pollen_index for now)
pollen_index = total_pollen_index

# Current time
record_date_time = datetime.now()

# 9) Create SQL insert statement
# First, let's check the actual schema of the EnvironmentData table
try:
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EnvironmentData' ORDER BY ORDINAL_POSITION")
    columns = [row[0] for row in cursor.fetchall()]
    print("Actual EnvironmentData columns:", columns)
except Exception as e:
    print(f"Error reading table schema: {e}")
    # If we can't read the schema, proceed with a more conservative approach

# Create SQL insert that matches the actual columns
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
    TotalPollenIndex,
    UVIndex,
    SubjectiveNotes,
    GrassPollen,
    TreePollen,
    WeedPollen,
    GrassPollenRisk,
    TreePollenRisk,
    WeedPollenRisk,
    PollenIndex
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            total_pollen_index,
            uv_index,
            "Daily environment check",  # Default note
            grass_pollen,
            tree_pollen,
            weed_pollen,
            grass_pollen_risk,
            tree_pollen_risk,
            weed_pollen_risk,
            pollen_index
        )
    )

    print("Successfully stored environmental data with detailed pollen information")

    conn.commit()
    print(f"Environmental data for {location} recorded successfully!")
    print(f"Temperature: {temperature}°C")
    print(f"Wind: {wind_speed} m/s, Direction: {wind_direction}°")
    print(f"Humidity: {humidity}%")
    print(f"Precipitation: {precipitation} mm")
    print(f"Total Pollen Index: {total_pollen_index}")
    print(f"Grass Pollen: {grass_pollen} ({grass_pollen_risk})")
    print(f"Tree Pollen: {tree_pollen} ({tree_pollen_risk})")
    print(f"Weed Pollen: {weed_pollen} ({weed_pollen_risk})")
    print(f"UV Index: {uv_index}")

except Exception as e:
    conn.rollback()
    print(f"Error inserting environmental data: {e}")

finally:
    cursor.close()
    conn.close()