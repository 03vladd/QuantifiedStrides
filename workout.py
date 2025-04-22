from datetime import datetime, timedelta
import garminconnect
import pyodbc
import logging
import sys
import config

# Set up logging
logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("workout")


def connect_to_garmin():
    """Connect to Garmin API and return client"""
    try:
        client = garminconnect.Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
        client.login()
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Garmin: {e}")
        sys.exit(1)


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
    try:
        cursor.execute(
            "SELECT WorkoutID FROM Workouts WHERE UserID = ? AND StartTime = ?",
            (user_id, start_time)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error checking for existing workout: {e}")
        return None


def is_indoor_workout(sport_type, workout_name=""):
    """Determine if a workout is indoor based on sport type and name"""
    if not sport_type and not workout_name:
        return False

    # Convert inputs to lowercase strings for comparison
    sport_str = str(sport_type).lower() if sport_type else ""
    name_str = str(workout_name).lower() if workout_name else ""

    # Check both sport type and workout name against indoor keywords
    for keyword in config.INDOOR_KEYWORDS:
        keyword = keyword.lower()
        if keyword in sport_str or keyword in name_str:
            return True

    return False


def process_activity(activity):
    """Process a single activity from Garmin"""
    if not activity:
        logger.warning("Empty activity data provided")
        return None

    try:
        user_id = config.DEFAULT_USER_ID

        # Extract basic activity info
        activity_id = activity.get("activityId")

        # Get sport type - try different possible keys
        sport = None
        if "activityType" in activity:
            activity_type = activity.get("activityType", {})
            if isinstance(activity_type, dict):
                sport = activity_type.get("typeKey", "Unknown")

        if not sport:
            sport = activity.get("activityType", "Unknown")

        # Get workout name (activityName)
        workout_type = activity.get("activityName", "Unknown")

        # Location name
        location = activity.get("locationName", "Unknown")

        # Determine if this is an indoor workout
        is_indoor = is_indoor_workout(sport, workout_type)

        # Start time: parse the "startTimeLocal" field ("YYYY-MM-DDTHH:MM:SS")
        start_time_str = activity.get("startTimeLocal", None)
        start_time_dt = None

        if start_time_str:
            # Try different date formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S"
            ]

            for fmt in formats:
                try:
                    start_time_dt = datetime.strptime(start_time_str, fmt)
                    break
                except ValueError:
                    continue

        if not start_time_dt:
            logger.error(f"Could not parse start time: {start_time_str}")
            start_time_dt = datetime.now()  # Fallback

        # Extract the date portion for the new WorkoutDate column
        workout_date = start_time_dt.date()

        # Duration in seconds (for deriving EndTime)
        duration_seconds = float(activity.get("duration", 0.0))

        # EndTime: if Garmin provided duration, we add to StartTime
        end_time_dt = start_time_dt + timedelta(seconds=duration_seconds)

        # Build the processed data dictionary
        processed_data = {
            "user_id": user_id,
            "sport": sport,
            "start_time": start_time_dt,
            "end_time": end_time_dt,
            "workout_type": workout_type,
            "calories_burned": int(activity.get("calories", 0)),
            "avg_heart_rate": int(activity.get("averageHR", 0)),
            "max_heart_rate": int(activity.get("maxHR", 0)),
            "vo2max": activity.get("vO2MaxValue"),
            "lactate_threshold": activity.get("lactateThresholdBpm"),
            "time_in_zone_1": float(activity.get("hrTimeInZone_1", 0.0)),
            "time_in_zone_2": float(activity.get("hrTimeInZone_2", 0.0)),
            "time_in_zone_3": float(activity.get("hrTimeInZone_3", 0.0)),
            "time_in_zone_4": float(activity.get("hrTimeInZone_4", 0.0)),
            "time_in_zone_5": float(activity.get("hrTimeInZone_5", 0.0)),
            "training_volume": float(activity.get("distance", 0.0)),
            "avg_vertical_osc": activity.get("avgVerticalOscillation"),
            "avg_ground_contact": activity.get("avgGroundContactTime"),
            "avg_stride_length": activity.get("avgStrideLength"),
            "avg_vertical_ratio": activity.get("avgVerticalRatio"),
            "avg_running_cadence": activity.get("averageRunningCadenceInStepsPerMinute"),
            "max_running_cadence": activity.get("maxRunningCadenceInStepsPerMinute"),
            "location": location,
            "workout_date": workout_date,
            "is_indoor": is_indoor,
            "activity_id": activity_id  # Store Garmin activityId for detailed metrics
        }

        return processed_data
    except Exception as e:
        logger.error(f"Error processing activity: {e}")
        return None


def insert_workout(cursor, data):
    """Insert workout data into the database"""
    if not data:
        logger.error("No workout data provided for insertion")
        return None

    try:
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

        cursor.execute(sql_insert, params)

        # Get the ID of the inserted workout
        cursor.execute("SELECT @@IDENTITY")
        workout_id = cursor.fetchone()[0]

        return workout_id
    except Exception as e:
        logger.error(f"Error inserting workout: {e}")
        return None


def get_detailed_metrics(client, activity_id):
    """Get essential detailed metrics for an activity"""
    try:
        # Get activity details with metrics
        details = {}
        try:
            details = client.get_activity_details(activity_id)
        except Exception as e:
            logger.warning(f"Could not get activity details: {e}")

        # Get HR data if available
        hr_data = {}
        try:
            hr_data = client.get_activity_hr_in_timezones(activity_id)
        except Exception as e:
            logger.warning(f"Could not get HR zones: {e}")

        return {
            "details": details,
            "hr_data": hr_data
        }
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {"details": {}, "hr_data": {}}


def extract_workout_metrics(details):
    """Extract key metrics from activity details"""
    metrics_points = []

    try:
        # Look for metrics in the details
        metrics_list = []
        if isinstance(details, dict):
            if "metrics" in details:
                metrics_list = details.get("metrics", [])
            elif "activityMetrics" in details:
                metrics_list = details.get("activityMetrics", [])

        # Process each metric
        for metric in metrics_list:
            if not isinstance(metric, dict):
                continue

            metric_type = metric.get("metricType", "")
            metric_values = metric.get("metrics", [])

            for value in metric_values:
                if not isinstance(value, dict) or "startTimeGMT" not in value:
                    continue

                # Parse timestamp
                time_str = value.get("startTimeGMT", "")
                timestamp = None

                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        timestamp = datetime.strptime(time_str, fmt)
                        break
                    except ValueError:
                        continue

                if not timestamp:
                    continue

                # Find or create point with this timestamp
                point = None
                for p in metrics_points:
                    if p["timestamp"] == timestamp:
                        point = p
                        break

                if not point:
                    point = {
                        "timestamp": timestamp,
                        "heart_rate": None,
                        "pace": None,
                        "cadence": None,
                        "vertical_oscillation": None,
                        "vertical_ratio": None,
                        "ground_contact_time": None,
                        "power": None
                    }
                    metrics_points.append(point)

                # Update the point with metric value
                if "value" in value:
                    if metric_type == "HEART_RATE":
                        point["heart_rate"] = value.get("value")
                    elif metric_type == "SPEED":
                        point["pace"] = value.get("value")
                    elif metric_type == "CADENCE":
                        point["cadence"] = value.get("value")
                    elif metric_type == "VERTICAL_OSCILLATION":
                        point["vertical_oscillation"] = value.get("value")
                    elif metric_type == "GROUND_CONTACT_TIME":
                        point["ground_contact_time"] = value.get("value")
                    elif metric_type == "VERTICAL_RATIO":
                        point["vertical_ratio"] = value.get("value")
                    elif metric_type == "POWER":
                        point["power"] = value.get("value")

        return metrics_points
    except Exception as e:
        logger.error(f"Error extracting metrics: {e}")
        return []


def extract_heart_rate_zones(hr_data):
    """Extract heart rate zones from HR data"""
    hr_zones = []

    if not hr_data:
        return hr_zones

    try:
        # Find zones in the data
        zones = []
        if isinstance(hr_data, list):
            zones = hr_data
        elif isinstance(hr_data, dict):
            for key in ['zones', 'timeInZones', 'heartRateZones']:
                if key in hr_data and isinstance(hr_data[key], list):
                    zones = hr_data[key]
                    break

            if not zones and 'allZones' in hr_data and isinstance(hr_data['allZones'], dict):
                zones = hr_data['allZones'].get('zones', [])

        # Process each zone
        for zone in zones:
            if not isinstance(zone, dict):
                continue

            zone_number = zone.get("zoneNumber", zone.get("zone"))
            seconds_in_zone = zone.get("secsInZone", zone.get("timeInZone", zone.get("seconds")))
            zone_low_boundary = zone.get("zoneLowBoundary", zone.get("min", zone.get("lower")))

            if zone_number is None or seconds_in_zone is None:
                continue

            hr_zones.append({
                "zone_number": zone_number,
                "seconds_in_zone": seconds_in_zone,
                "zone_low_boundary": zone_low_boundary
            })

        return hr_zones
    except Exception as e:
        logger.error(f"Error extracting HR zones: {e}")
        return []


def insert_workout_metrics(cursor, workout_id, metric_points):
    """Insert workout metrics into the database"""
    if not metric_points:
        return 0

    try:
        values = []
        for point in metric_points:
            values.append((
                workout_id,
                point.get("timestamp"),
                point.get("heart_rate"),
                point.get("pace"),
                point.get("cadence"),
                point.get("vertical_oscillation"),
                point.get("vertical_ratio"),
                point.get("ground_contact_time"),
                point.get("power")
            ))

        # Insert in batches
        rows_inserted = 0
        batch_size = 1000

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO WorkoutMetrics (
                    WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence,
                    VerticalOscillation, VerticalRatio, GroundContactTime, Power
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting metrics: {e}")
        return 0


def insert_heart_rate_zones(cursor, workout_id, hr_zones):
    """Insert heart rate zone data into the database"""
    if not hr_zones:
        return 0

    try:
        values = []
        for zone in hr_zones:
            values.append((
                workout_id,
                zone.get("zone_number"),
                zone.get("seconds_in_zone"),
                zone.get("zone_low_boundary")
            ))

        cursor.executemany("""
            INSERT INTO WorkoutHeartRateZones (
                WorkoutID, ZoneNumber, SecondsInZone, ZoneLowBoundary
            )
            VALUES (?, ?, ?, ?)
        """, values)

        return len(values)
    except Exception as e:
        logger.error(f"Error inserting HR zones: {e}")
        return 0


def main():
    """Main function to collect and store workout data from Garmin Connect"""
    try:
        # Connect to Garmin
        logger.info("Connecting to Garmin Connect API...")
        client = connect_to_garmin()

        # Get recent activities
        logger.info("Fetching recent activities from Garmin...")
        activities = client.get_activities(0, 10)  # Fetch last 10 activities

        if not activities:
            logger.info("No recent activities found.")
            return 0

        # Connect to database
        logger.info("Connecting to database...")
        conn, cursor = connect_to_database()
        print("Cursor connected")

        # Create WorkoutHeartRateZones table if it doesn't exist
        try:
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'WorkoutHeartRateZones')
                CREATE TABLE WorkoutHeartRateZones (
                    HRZoneID INT PRIMARY KEY IDENTITY(1,1),
                    WorkoutID INT NOT NULL,
                    ZoneNumber INT NOT NULL,
                    SecondsInZone FLOAT,
                    ZoneLowBoundary INT,
                    FOREIGN KEY (WorkoutID) REFERENCES Workouts(WorkoutID)
                )
            """)
        except Exception as e:
            logger.warning(f"Error checking/creating HR zones table: {e}")

        # Track insertion statistics
        activities_inserted = 0
        metrics_inserted = 0
        hr_zones_inserted = 0

        # Process each activity
        for activity in activities:
            try:
                # Get activity ID
                activity_id = activity.get("activityId")
                if not activity_id:
                    logger.warning("Activity missing activityId, skipping")
                    continue

                # Process the activity data
                processed_data = process_activity(activity)
                if not processed_data:
                    logger.warning(f"Failed to process activity with ID: {activity_id}")
                    continue

                # Check if workout already exists in database
                existing = check_existing_workout(cursor, processed_data["user_id"], processed_data["start_time"])

                if existing:
                    workout_id = existing[0]
                    logger.info(f"Workout at {processed_data['start_time']} already exists (ID: {workout_id}).")

                    # Check if metrics already exist
                    cursor.execute("SELECT COUNT(*) FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
                    metrics_count = cursor.fetchone()[0]

                    if metrics_count > 0:
                        logger.info(f"Workout ID {workout_id} already has metrics. Skipping...")
                        continue

                    logger.info(f"Adding detailed metrics to existing workout ID: {workout_id}")
                else:
                    # Insert the new workout
                    workout_id = insert_workout(cursor, processed_data)
                    if workout_id:
                        activities_inserted += 1
                        logger.info(f"Inserted workout: {processed_data['workout_type']} (ID: {workout_id})")
                    else:
                        logger.error(f"Failed to insert workout for activity ID: {activity_id}")
                        continue

                # Get detailed metrics for the workout
                detailed_metrics = get_detailed_metrics(client, activity_id)

                # Process and insert workout metrics
                metric_points = extract_workout_metrics(detailed_metrics.get("details", {}))
                if metric_points:
                    rows = insert_workout_metrics(cursor, workout_id, metric_points)
                    metrics_inserted += rows
                    logger.info(f"Inserted {rows} metric points for workout ID {workout_id}")

                # Process and insert heart rate zones
                hr_zones = extract_heart_rate_zones(detailed_metrics.get("hr_data", {}))
                if hr_zones:
                    rows = insert_heart_rate_zones(cursor, workout_id, hr_zones)
                    hr_zones_inserted += rows
                    logger.info(f"Inserted {rows} heart rate zones for workout ID {workout_id}")

                # Commit after each activity is fully processed
                conn.commit()

            except Exception as e:
                logger.error(f"Error processing activity: {e}")
                conn.rollback()
                continue

        # Close connections
        cursor.close()
        conn.close()

        # Print summary
        print(
            f"All activities inserted successfully! ({activities_inserted} new activities, "
            f"{metrics_inserted} metric points, {hr_zones_inserted} heart rate zones)"
        )
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