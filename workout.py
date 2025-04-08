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
        "is_indoor": is_indoor,
        "activity_id": activity.get("activityId", None)  # Store Garmin activityId for detailed metrics
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

    # Get the ID of the inserted workout
    cursor.execute("SELECT @@IDENTITY")
    workout_id = cursor.fetchone()[0]

    return workout_id


def get_detailed_workout_metrics(client, activity_id):
    """Get detailed metrics for an activity"""
    logger.info(f"Fetching detailed metrics for activity ID: {activity_id}")

    try:
        # Get activity details with metrics
        details = client.get_activity_details(activity_id)

        # Get split data if available
        try:
            splits = client.get_activity_splits(activity_id)
        except Exception as e:
            logger.warning(f"Could not get splits for activity {activity_id}: {e}")
            splits = []

        # Get HR data if available
        try:
            hr_data = client.get_activity_hr_in_timezones(activity_id)
        except Exception as e:
            logger.warning(f"Could not get HR zones for activity {activity_id}: {e}")
            hr_data = {}

        # Combine all the data
        return {
            "details": details,
            "splits": splits,
            "hr_data": hr_data
        }
    except Exception as e:
        logger.error(f"Error fetching detailed metrics for activity {activity_id}: {e}")
        return {}


def process_metric_points(detailed_metrics):
    """Process and extract time-series data points from detailed metrics"""
    processed_points = []

    # Process activity details
    details = detailed_metrics.get("details", {})
    metrics = details.get("metrics", [])

    # Find metrics with time-series data
    for metric in metrics:
        metric_type = metric.get("metricType", "")
        metric_values = metric.get("metrics", [])

        if not metric_values:
            continue

        # Process each metric point
        for i, value in enumerate(metric_values):
            # Make sure we have a timestamp
            if "startTimeGMT" not in value:
                continue

            # Parse timestamp
            try:
                timestamp = datetime.strptime(value["startTimeGMT"], "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    timestamp = datetime.strptime(value["startTimeGMT"], "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    logger.error(f"Could not parse timestamp: {value['startTimeGMT']}")
                    continue

            # If this is the first metric type, create a new point
            if i >= len(processed_points):
                processed_points.append({
                    "timestamp": timestamp
                })

            # Add the metric value to the point
            if metric_type == "HEART_RATE":
                processed_points[i]["heart_rate"] = value.get("value")
            elif metric_type == "SPEED":
                processed_points[i]["pace"] = value.get("value")
            elif metric_type == "CADENCE":
                processed_points[i]["cadence"] = value.get("value")
            elif metric_type == "VERTICAL_OSCILLATION":
                processed_points[i]["vertical_oscillation"] = value.get("value")
            elif metric_type == "GROUND_CONTACT_TIME":
                processed_points[i]["ground_contact_time"] = value.get("value")
            elif metric_type == "VERTICAL_RATIO":
                processed_points[i]["vertical_ratio"] = value.get("value")
            elif metric_type == "STRIDE_LENGTH":
                processed_points[i]["stride_length"] = value.get("value")
            elif metric_type == "POWER":
                processed_points[i]["power"] = value.get("value")
            elif metric_type == "ALTITUDE":
                processed_points[i]["altitude"] = value.get("value")
            elif metric_type == "TEMPERATURE":
                processed_points[i]["temperature"] = value.get("value")

    return processed_points


def insert_workout_metrics(cursor, workout_id, metric_points):
    """Insert detailed workout metrics into the database"""
    if not metric_points:
        logger.warning(f"No metric points to insert for workout ID: {workout_id}")
        return 0

    # Prepare batch insert
    values = []
    for point in metric_points:
        # We always need a timestamp
        if "timestamp" not in point:
            continue

        # Extract values with defaults for missing metrics
        timestamp = point.get("timestamp")
        heart_rate = point.get("heart_rate")
        pace = point.get("pace")
        cadence = point.get("cadence")
        vertical_oscillation = point.get("vertical_oscillation")
        ground_contact_time = point.get("ground_contact_time")
        vertical_ratio = point.get("vertical_ratio")
        stride_length = point.get("stride_length")
        power = point.get("power")
        altitude = point.get("altitude")
        temperature = point.get("temperature")

        values.append((
            workout_id, timestamp, heart_rate, pace, cadence,
            vertical_oscillation, vertical_ratio, ground_contact_time,
            power, altitude, temperature, stride_length
        ))

    # Use batch insert for better performance
    try:
        # Using transactions for better performance
        rows_inserted = 0
        batch_size = 1000  # Insert in batches of 1000

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO WorkoutMetrics (
                    WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence, 
                    VerticalOscillation, VerticalRatio, GroundContactTime,
                    Power, Altitude, Temperature, StrideLength
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)
            logger.info(f"Inserted batch of {len(batch)} metrics (total: {rows_inserted})")

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting workout metrics: {e}")
        return 0


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
        metrics_inserted = 0

        for activity in activities:
            # Process the activity
            processed_data = process_activity(activity)

            # Check if it already exists
            existing = check_existing_workout(cursor, processed_data["user_id"], processed_data["start_time"])

            if existing:
                workout_id = existing[0]
                logger.info(
                    f"Workout at {processed_data['start_time']} already exists (ID: {workout_id}). Checking for detailed metrics...")

                # Check if workout metrics already exist
                cursor.execute("SELECT COUNT(*) FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
                metrics_count = cursor.fetchone()[0]

                if metrics_count > 0:
                    logger.info(f"Workout ID {workout_id} already has {metrics_count} metric points. Skipping...")
                    continue
            else:
                # Insert the workout
                workout_id = insert_workout(cursor, processed_data)
                if workout_id:
                    activities_inserted += 1
                    logger.info(
                        f"Inserted workout: {processed_data['workout_type']} on {processed_data['workout_date']} (ID: {workout_id})")
                else:
                    logger.error("Failed to insert workout")
                    continue

            # Get and process detailed metrics
            activity_id = processed_data.get("activity_id")
            if activity_id:
                detailed_metrics = get_detailed_workout_metrics(client, activity_id)
                metric_points = process_metric_points(detailed_metrics)

                if metric_points:
                    rows = insert_workout_metrics(cursor, workout_id, metric_points)
                    metrics_inserted += rows
                    logger.info(f"Inserted {rows} detailed metric points for workout ID {workout_id}")
                else:
                    logger.warning(f"No detailed metrics found for activity ID {activity_id}")

        # Commit and close
        conn.commit()
        cursor.close()
        conn.close()

        print(
            f"All activities inserted successfully! ({activities_inserted} new activities, {metrics_inserted} metric points)")
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