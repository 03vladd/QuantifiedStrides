from datetime import datetime, timedelta
import pyodbc
import requests
import json
import os
import logging
import sys
import config

# Set up logging
logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("environment")


def connect_to_database():
    """Connect to the database and return connection and cursor"""
    try:
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def check_has_is_indoor_column(cursor):
    """Check if the Workouts table has the IsIndoor column"""
    try:
        # A database-agnostic way to check for a column
        cursor.execute("""
            SELECT * 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Workouts' AND COLUMN_NAME = 'IsIndoor'
        """)
        return cursor.fetchone() is not None
    except Exception as e:
        logger.warning(f"Could not verify IsIndoor column: {e}")
        return False


def find_todays_workout(cursor, today):
    """Find a workout for today and check if it's indoor"""
    has_is_indoor = check_has_is_indoor_column(cursor)

    try:
        if has_is_indoor:
            # If IsIndoor column exists
            cursor.execute("""
                SELECT WorkoutID, Location, IsIndoor 
                FROM Workouts 
                WHERE WorkoutDate = ? 
                ORDER BY StartTime DESC
            """, (today,))
        else:
            # Fallback if IsIndoor doesn't exist
            logger.warning("IsIndoor column not found, using fallback query")
            cursor.execute("""
                SELECT WorkoutID, Location, 0 
                FROM Workouts 
                WHERE WorkoutDate = ? 
                ORDER BY StartTime DESC
            """, (today,))

        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error finding today's workout: {e}")
        return None


def check_existing_environment_data(cursor, workout_id):
    """Check if environment data already exists for this workout"""
    cursor.execute(
        "SELECT EnvID FROM EnvironmentData WHERE WorkoutID = ?",
        (workout_id,)
    )
    return cursor.fetchone()


def delete_existing_environment_data(cursor, workout_id):
    """Delete existing environment data for this workout"""
    cursor.execute(
        "DELETE FROM EnvironmentData WHERE WorkoutID = ?",
        (workout_id,)
    )
    return cursor.rowcount


def create_placeholder_workout(cursor, today):
    """Create a placeholder workout if none exists for today"""
    logger.info("No workouts found for today. Creating a placeholder workout...")

    # Check if IsIndoor column exists
    has_is_indoor = check_has_is_indoor_column(cursor)

    current_time = datetime.now()

    if has_is_indoor:
        placeholder_sql = """
        INSERT INTO Workouts (
            UserID, Sport, StartTime, EndTime, WorkoutType, 
            CaloriesBurned, AvgHeartRate, MaxHeartRate, 
            TrainingVolume, Location, WorkoutDate, IsIndoor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        cursor.execute(
            placeholder_sql,
            (
                config.DEFAULT_USER_ID,
                "other",
                current_time,
                current_time,
                "Environmental Data Collection",
                0,
                0,
                0,
                0,
                config.DEFAULT_LOCATION["name"],
                today,
                0  # IsIndoor (False)
            )
        )
    else:
        placeholder_sql = """
        INSERT INTO Workouts (
            UserID, Sport, StartTime, EndTime, WorkoutType, 
            CaloriesBurned, AvgHeartRate, MaxHeartRate, 
            TrainingVolume, Location, WorkoutDate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        cursor.execute(
            placeholder_sql,
            (
                config.DEFAULT_USER_ID,
                "other",
                current_time,
                current_time,
                "Environmental Data Collection",
                0,
                0,
                0,
                0,
                config.DEFAULT_LOCATION["name"],
                today
            )
        )

    # Get the ID of the placeholder workout
    try:
        cursor.execute("SELECT @@IDENTITY")  # More compatible than SCOPE_IDENTITY()
        workout_id = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error getting workout ID: {e}")
        # Try an alternative approach
        cursor.execute("SELECT MAX(WorkoutID) FROM Workouts WHERE WorkoutDate = ?", (today,))
        workout_id = cursor.fetchone()[0]

    logger.info(f"Created placeholder workout with ID: {workout_id}")
    return workout_id


def get_weather_data(lat, lon, api_key):
    """Get current weather data from OpenWeatherMap"""
    try:
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
        response = requests.get(weather_url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get weather data: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return {}


def get_uv_data(lat, lon, api_key):
    """Get UV index from OpenWeatherMap One Call API"""
    try:
        uv_url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,daily,alerts&appid={api_key}"
        response = requests.get(uv_url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get UV data: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching UV data: {e}")
        return {}


def get_pollen_data(lat, lon, api_key):
    """Get pollen data from Ambee API"""
    pollen_url = f"https://api.ambeedata.com/latest/pollen/by-lat-lng?lat={lat}&lng={lon}"
    headers = {
        "x-api-key": api_key,
        "Content-type": "application/json"
    }

    try:
        response = requests.get(pollen_url, headers=headers, timeout=10)
        logger.info(f"Pollen API status code: {response.status_code}")

        if response.status_code == 200:
            try:
                pollen_data = response.json()
                logger.info("Successfully retrieved pollen data from API")
                return pollen_data
            except json.JSONDecodeError as json_err:
                logger.error(f"Error decoding JSON from pollen API: {json_err}")
        else:
            logger.error(f"Failed to get pollen data. Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error getting pollen data: {e}")

    # Return default structure if failed
    return {"data": [{}]}


def get_risk_level(count):
    """Assess risk level based on pollen counts"""
    if count < 10:
        return "Low"
    elif count < 30:
        return "Moderate"
    else:
        return "High"


def process_pollen_data(pollen_data, current_month):
    """Process and validate pollen data"""
    pollen_values = pollen_data.get("data", [{}])[0]

    # Check if we have actual pollen data
    has_pollen_data = bool(pollen_values)
    if not has_pollen_data:
        logger.warning("Warning: Using default/fallback values for pollen data")

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
        logger.info(f"Using seasonal estimates for pollen data (Month: {current_month})")
    else:
        logger.info(f"Using actual pollen data from API: Grass={grass_pollen}, Tree={tree_pollen}, Weed={weed_pollen}")

    # Calculate total pollen index (average)
    total_pollen_index = (grass_pollen + tree_pollen + weed_pollen) / 3

    return {
        "grass_pollen": grass_pollen,
        "tree_pollen": tree_pollen,
        "weed_pollen": weed_pollen,
        "grass_pollen_risk": grass_pollen_risk,
        "tree_pollen_risk": tree_pollen_risk,
        "weed_pollen_risk": weed_pollen_risk,
        "total_pollen_index": total_pollen_index,
        "pollen_index": total_pollen_index  # Same as total for now
    }


def insert_environment_data(cursor, data):
    """Insert environment data into the database"""
    sql_insert = """
    INSERT INTO EnvironmentData (
        WorkoutID, RecordDateTime, Location, Temperature, 
        WindSpeed, WindDirection, Humidity, Precipitation, 
        TotalPollenIndex, UVIndex, SubjectiveNotes,
        GrassPollen, TreePollen, WeedPollen, 
        GrassPollenRisk, TreePollenRisk, WeedPollenRisk, PollenIndex
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    cursor.execute(
        sql_insert,
        (
            data["workout_id"],
            data["record_date_time"],
            data["location"],
            data["temperature"],
            data["wind_speed"],
            data["wind_direction"],
            data["humidity"],
            data["precipitation"],
            data["total_pollen_index"],
            data["uv_index"],
            data["subjective_notes"],
            data["grass_pollen"],
            data["tree_pollen"],
            data["weed_pollen"],
            data["grass_pollen_risk"],
            data["tree_pollen_risk"],
            data["weed_pollen_risk"],
            data["pollen_index"]
        )
    )
    return cursor.rowcount


def main():
    try:
        # Connect to database
        conn, cursor = connect_to_database()
        print("Cursor connected")

        # Get today's date
        today = datetime.now().date()
        current_month = datetime.now().month
        logger.info(f"Collecting environmental data for: {today}")

        # Find workout for today
        workout_row = find_todays_workout(cursor, today)

        if workout_row:
            workout_id = workout_row[0]
            location = workout_row[1]
            is_indoor = workout_row[2]
            logger.info(f"Found workout from today with ID: {workout_id}")

            # Check if this is an indoor workout
            if is_indoor:
                logger.info("Workout is indoor - collecting minimal environmental data")
                # For indoor workouts, we'll still record basic data but skip API calls
        else:
            # Create a placeholder workout
            workout_id = create_placeholder_workout(cursor, today)
            location = config.DEFAULT_LOCATION["name"]
            is_indoor = False

        # Check if environment data already exists for this workout
        existing_data = check_existing_environment_data(cursor, workout_id)

        if existing_data:
            logger.info(f"Environment data for workout ID {workout_id} already exists. Deleting existing record.")
            deleted = delete_existing_environment_data(cursor, workout_id)
            logger.info(f"Deleted {deleted} existing record(s).")

        # Initialize data structure
        environment_data = {
            "workout_id": workout_id,
            "record_date_time": datetime.now(),
            "location": location,
            "temperature": None,
            "wind_speed": None,
            "wind_direction": None,
            "humidity": None,
            "precipitation": None,
            "total_pollen_index": None,
            "uv_index": None,
            "subjective_notes": "Daily environment check",
            "grass_pollen": None,
            "tree_pollen": None,
            "weed_pollen": None,
            "grass_pollen_risk": None,
            "tree_pollen_risk": None,
            "weed_pollen_risk": None,
            "pollen_index": None
        }

        # If indoor workout, collect minimal data
        if is_indoor:
            # For indoor workouts, set default values
            environment_data["temperature"] = 21.0  # Typical indoor temperature
            environment_data["humidity"] = 40.0  # Typical indoor humidity
            environment_data["subjective_notes"] = "Indoor workout - minimal environmental data"

            # Indoor workouts don't need weather, pollen, etc.
            environment_data["wind_speed"] = 0.0
            environment_data["wind_direction"] = 0
            environment_data["precipitation"] = 0.0
            environment_data["uv_index"] = 0.0
            environment_data["total_pollen_index"] = 0.0
            environment_data["grass_pollen"] = 0
            environment_data["tree_pollen"] = 0
            environment_data["weed_pollen"] = 0
            environment_data["grass_pollen_risk"] = "Low"
            environment_data["tree_pollen_risk"] = "Low"
            environment_data["weed_pollen_risk"] = "Low"
            environment_data["pollen_index"] = 0.0
        else:
            # For outdoor workouts, get full environmental data
            # Get coordinates based on location (simplified for now)
            lat, lon = config.DEFAULT_LOCATION["lat"], config.DEFAULT_LOCATION["lon"]

            # Get weather data
            weather_data = get_weather_data(lat, lon, config.OPENWEATHER_API_KEY)

            # Extract location from weather data or use default
            environment_data["location"] = weather_data.get("name", location)

            # Temperature in Celsius
            environment_data["temperature"] = weather_data.get("main", {}).get("temp")

            # Wind data
            environment_data["wind_speed"] = weather_data.get("wind", {}).get("speed")
            environment_data["wind_direction"] = weather_data.get("wind", {}).get("deg")

            # Humidity percentage
            environment_data["humidity"] = weather_data.get("main", {}).get("humidity")

            # Precipitation (rain in last hour if available)
            environment_data["precipitation"] = weather_data.get("rain", {}).get("1h",
                                                                                 0) if "rain" in weather_data else 0

            # Get UV index
            uv_data = get_uv_data(lat, lon, config.OPENWEATHER_API_KEY)
            environment_data["uv_index"] = uv_data.get("current", {}).get("uvi", 0)

            # Get pollen data
            pollen_data = get_pollen_data(lat, lon, config.AMBEE_API_KEY)
            pollen_results = process_pollen_data(pollen_data, current_month)

            # Update environment data with pollen information
            environment_data.update(pollen_results)

        # Insert the data
        inserted = insert_environment_data(cursor, environment_data)

        if inserted:
            logger.info(f"Successfully stored environmental data with detailed pollen information")
            conn.commit()

            # Print a summary of the data
            print(f"Environmental data for {environment_data['location']} recorded successfully!")
            print(f"Temperature: {environment_data['temperature']}°C")
            print(f"Wind: {environment_data['wind_speed']} m/s, Direction: {environment_data['wind_direction']}°")
            print(f"Humidity: {environment_data['humidity']}%")
            print(f"Precipitation: {environment_data['precipitation']} mm")

            if not is_indoor:
                print(f"Total Pollen Index: {environment_data['total_pollen_index']}")
                print(f"Grass Pollen: {environment_data['grass_pollen']} ({environment_data['grass_pollen_risk']})")
                print(f"Tree Pollen: {environment_data['tree_pollen']} ({environment_data['tree_pollen_risk']})")
                print(f"Weed Pollen: {environment_data['weed_pollen']} ({environment_data['weed_pollen_risk']})")
                print(f"UV Index: {environment_data['uv_index']}")
        else:
            logger.error("Failed to insert environmental data")
            conn.rollback()

        # Close connections
        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        logger.error(f"Error in environment data collection: {e}")
        if 'conn' in locals() and conn:
            try:
                conn.rollback()
            except:
                pass
            try:
                conn.close()
            except:
                pass
        return 1


if __name__ == "__main__":
    exit(main())