from datetime import datetime, timedelta
import os
import garminconnect
import pyodbc
import json
import logging
import sys
import config

# Set up logging
logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("workout")


def connect_to_garmin():
    """Connect to Garmin API and return client"""
    client = garminconnect.Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
    client.login()
    return client


def connect_to_database():
    """Connect to the database and return connection and cursor"""
    try:
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def check_existing_workout(cursor, user_id, start_time):
    """Check if a workout already exists with the same start time"""
    cursor.execute(
        "SELECT WorkoutID FROM Workouts WHERE UserID = ? AND StartTime = ?",
        (user_id, start_time)
    )
    return cursor.fetchone()


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


def is_indoor_workout(sport_type):
    """Determine if a workout is indoor based on sport type"""
    return any(keyword in sport_type.lower() for keyword in config.INDOOR_KEYWORDS)


def process_activity(activity):
    """Process a single activity from Garmin"""
    user_id = config.DEFAULT_USER_ID

    sport = activity.get("activityType", {}).get("typeKey", "Unknown")  # e.g. "run", "cycling"
    workout_type = activity.get("activityName", "Unknown")  # or "activityName"

    # Determine if this is an indoor workout
    is_indoor = is_indoor_workout(sport)

    # Start time: parse the "startTimeLocal" field ("YYYY-MM-DDTHH:MM:SS")
    start_time_str = activity.get("startTimeLocal", None)
    if start_time_str:
        # Try parsing with 'T', then fallback to space-based.
        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.error(f"Could not parse start time: {start_time_str}")
                start_time_dt = datetime.now()
    else:
        start_time_dt = datetime.now()  # or some fallback

    # Extract the date portion for the new WorkoutDate column
    workout_date = start_time_dt.date()

    # Duration in seconds (for deriving EndTime)
    duration_seconds = activity.get("duration", 0.0)

    # EndTime: if Garmin provided duration, we add to StartTime
    end_time_dt = start_time_dt + timedelta(seconds=float(duration_seconds))

    # Extract all other metrics
    processed_data = {
        "user_id": user_id,
        "sport": sport,
        "start_time": start_time_dt,
        "end_time": end_time_dt,
        "workout_type": workout_type,
        "calories_burned": activity.get("calories", 0),
        "avg_heart_rate": activity.get("averageHR", 0),
        "max_heart_rate": activity.get("maxHR", 0),
        "vo2max": activity.get("vO2MaxValue", None),
        "lactate_threshold": activity.get("lactateThresholdBpm", None),
        "time_in_zone_1": activity.get("hrTimeInZone_1", 0.0),
        "time_in_zone_2": activity.get("hrTimeInZone_2", 0.0),
        "time_in_zone_3": activity.get("hrTimeInZone_3", 0.0),
        "time_in_zone_4": activity.get("hrTimeInZone_4", 0.0),
        "time_in_zone_5": activity.get("hrTimeInZone_5", 0.0),
        "training_volume": activity.get("distance", 0.0),
        "avg_vertical_osc": activity.get("avgVerticalOscillation", None),
        "avg_ground_contact": activity.get("avgGroundContactTime", None),
        "avg_stride_length": activity.get("avgStrideLength", None),
        "avg_vertical_ratio": activity.get("avgVerticalRatio", None),
        "avg_running_cadence": activity.get("averageRunningCadenceInStepsPerMinute", None),
        "max_running_cadence": activity.get("maxRunningCadenceInStepsPerMinute", None),
        "location": activity.get("locationName", "Unknown"),
        "workout_date": workout_date,
        "is_indoor": is_indoor
    }

    return processed_data


def insert_workout(cursor, data):
    """Insert workout data into the database"""
    # Check if IsIndoor column exists
    has_is_indoor = check_has_is_indoor_column(cursor)
    if not has_is_indoor:
        logger.warning("IsIndoor column not found in Workouts table. Skipping this field.")

    # Construct SQL dynamically based on available columns
    if has_is_indoor:
        sql_insert = """
        INSERT INTO Workouts (
            UserID, Sport, StartTime, EndTime, WorkoutType, 
            CaloriesBurned, AvgHeartRate, MaxHeartRate, 
            VO2MaxEstimate, LactateThresholdBpm, 
            TimeInHRZone1, TimeInHRZone2, TimeInHRZone3, TimeInHRZone4, TimeInHRZone5, 
            TrainingVolume, AvgVerticalOscillation, AvgGroundContactTime, 
            AvgStrideLength, AvgVerticalRatio, AverageRunningCadence, 
            MaxRunningCadence, Location, WorkoutDate, IsIndoor
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        params = (
            data["user_id"],
            data["sport"],
            data["start_time"],
            data["end_time"],
            data["workout_type"],
            data["calories_burned"],
            data["avg_heart_rate"],
            data["max_heart_rate"],
            data["vo2max"],
            data["lactate_threshold"],
            data["time_in_zone_1"],
            data["time_in_zone_2"],
            data["time_in_zone_3"],
            data["time_in_zone_4"],
            data["time_in_zone_5"],
            data["training_volume"],
            data["avg_vertical_osc"],
            data["avg_ground_contact"],
            data["avg_stride_length"],
            data["avg_vertical_ratio"],
            data["avg_running_cadence"],
            data["max_running_cadence"],
            data["location"],
            data["workout_date"],
            data["is_indoor"]
        )
    else:
        sql_insert = """
        INSERT INTO Workouts (
            UserID, Sport, StartTime, EndTime, WorkoutType, 
            CaloriesBurned, AvgHeartRate, MaxHeartRate, 
            VO2MaxEstimate, LactateThresholdBpm, 
            TimeInHRZone1, TimeInHRZone2, TimeInHRZone3, TimeInHRZone4, TimeInHRZone5, 
            TrainingVolume, AvgVerticalOscillation, AvgGroundContactTime, 
            AvgStrideLength, AvgVerticalRatio, AverageRunningCadence, 
            MaxRunningCadence, Location, WorkoutDate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        params = (
            data["user_id"],
            data["sport"],
            data["start_time"],
            data["end_time"],
            data["workout_type"],
            data["calories_burned"],
            data["avg_heart_rate"],
            data["max_heart_rate"],
            data["vo2max"],
            data["lactate_threshold"],
            data["time_in_zone_1"],
            data["time_in_zone_2"],
            data["time_in_zone_3"],
            data["time_in_zone_4"],
            data["time_in_zone_5"],
            data["training_volume"],
            data["avg_vertical_osc"],
            data["avg_ground_contact"],
            data["avg_stride_length"],
            data["avg_vertical_ratio"],
            data["avg_running_cadence"],
            data["max_running_cadence"],
            data["location"],
            data["workout_date"]
        )

    cursor.execute(sql_insert, params)
    return cursor.rowcount


def main():
    try:
        # Connect to Garmin
        client = connect_to_garmin()

        # Get recent activities
        activities = client.get_activities(0, 1)  # from index 0, 1 activity

        if not activities:
            logger.info("No recent activities found.")
            return 0

        # Connect to database
        conn, cursor = connect_to_database()
        print("Cursor connected")

        # Begin transaction
        activities_inserted = 0

        for activity in activities:
            # Process the activity
            processed_data = process_activity(activity)

            # Check if it already exists
            existing = check_existing_workout(cursor, processed_data["user_id"], processed_data["start_time"])

            if existing:
                logger.info(
                    f"Workout at {processed_data['start_time']} already exists (ID: {existing[0]}). Skipping...")
                continue

            # Insert the workout
            inserted = insert_workout(cursor, processed_data)
            if inserted:
                activities_inserted += 1
                logger.info(f"Inserted workout: {processed_data['workout_type']} on {processed_data['workout_date']}")

        # Commit and close
        conn.commit()
        cursor.close()
        conn.close()

        print(f"All activities inserted successfully! ({activities_inserted} new activities)")
        return 0

    except Exception as e:
        logger.error(f"Error in workout data collection: {e}")
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