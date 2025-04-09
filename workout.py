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


def check_table_structure(cursor):
    """Check if necessary tables exist and create them if they don't"""
    # Check for WorkoutRoutePoints table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'WorkoutRoutePoints')
        CREATE TABLE WorkoutRoutePoints (
            RoutePointID INT PRIMARY KEY IDENTITY(1,1),
            WorkoutID INT NOT NULL,
            Timestamp DATETIME NOT NULL,
            Latitude FLOAT,
            Longitude FLOAT,
            Altitude FLOAT,
            Speed FLOAT,
            CumulativeAscent FLOAT,
            CumulativeDescent FLOAT,
            DistanceFromPreviousPoint FLOAT,
            DistanceInMeters FLOAT,
            FOREIGN KEY (WorkoutID) REFERENCES Workouts(WorkoutID)
        )
    """)

    # Check for WorkoutHeartRateZones table
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

    # Check WorkoutMetrics table for required columns
    required_columns = [
        ("LapIndex", "INT"),
        ("MessageIndex", "INT"),
        ("Distance", "FLOAT"),
        ("Duration", "FLOAT"),
        ("StartLatitude", "FLOAT"),
        ("StartLongitude", "FLOAT"),
        ("EndLatitude", "FLOAT"),
        ("EndLongitude", "FLOAT"),
        ("ElevationGain", "FLOAT"),
        ("ElevationLoss", "FLOAT")
    ]

    for column_name, data_type in required_columns:
        cursor.execute(f"""
            IF NOT EXISTS (SELECT * FROM sys.columns 
                          WHERE object_id = OBJECT_ID('WorkoutMetrics') AND name = '{column_name}')
            ALTER TABLE WorkoutMetrics 
            ADD {column_name} {data_type} NULL
        """)

    logger.info("Database structure verified and updated if needed")


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


def get_detailed_workout_metrics(client, activity_id):
    """Get detailed metrics for an activity"""
    logger.info(f"Fetching detailed metrics for activity ID: {activity_id}")

    try:
        # Get activity details with metrics (includes laps and splits)
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

        # Get GPS route data if available
        try:
            gps_data = client.get_activity_route(activity_id)
        except Exception as e:
            logger.warning(f"Could not get GPS route for activity {activity_id}: {e}")
            gps_data = []

        # Combine all the data
        return {
            "details": details,
            "splits": splits,
            "hr_data": hr_data,
            "gps_data": gps_data
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
        for value in metric_values:
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

            # Check if we already have a point for this timestamp
            point_exists = False
            for point in processed_points:
                if point["timestamp"] == timestamp:
                    point_exists = True
                    # Add this metric to existing point
                    if metric_type == "HEART_RATE" and "value" in value:
                        point["heart_rate"] = value["value"]
                    elif metric_type == "SPEED" and "value" in value:
                        point["pace"] = value["value"]
                    elif metric_type == "CADENCE" and "value" in value:
                        point["cadence"] = value["value"]
                    elif metric_type == "VERTICAL_OSCILLATION" and "value" in value:
                        point["vertical_oscillation"] = value["value"]
                    elif metric_type == "GROUND_CONTACT_TIME" and "value" in value:
                        point["ground_contact_time"] = value["value"]
                    elif metric_type == "VERTICAL_RATIO" and "value" in value:
                        point["vertical_ratio"] = value["value"]
                    elif metric_type == "STRIDE_LENGTH" and "value" in value:
                        point["stride_length"] = value["value"]
                    elif metric_type == "POWER" and "value" in value:
                        point["power"] = value["value"]
                    break

            # If point doesn't exist, create a new one
            if not point_exists:
                new_point = {
                    "timestamp": timestamp,
                    "heart_rate": None,
                    "pace": None,
                    "cadence": None,
                    "vertical_oscillation": None,
                    "vertical_ratio": None,
                    "ground_contact_time": None,
                    "stride_length": None,
                    "power": None,
                    "message_index": None,
                    "lap_index": None,
                    "distance": None,
                    "duration": None,
                    "start_latitude": None,
                    "start_longitude": None,
                    "end_latitude": None,
                    "end_longitude": None,
                    "elevation_gain": None,
                    "elevation_loss": None
                }

                # Add the specific metric value
                if metric_type == "HEART_RATE" and "value" in value:
                    new_point["heart_rate"] = value["value"]
                elif metric_type == "SPEED" and "value" in value:
                    new_point["pace"] = value["value"]
                elif metric_type == "CADENCE" and "value" in value:
                    new_point["cadence"] = value["value"]
                elif metric_type == "VERTICAL_OSCILLATION" and "value" in value:
                    new_point["vertical_oscillation"] = value["value"]
                elif metric_type == "GROUND_CONTACT_TIME" and "value" in value:
                    new_point["ground_contact_time"] = value["value"]
                elif metric_type == "VERTICAL_RATIO" and "value" in value:
                    new_point["vertical_ratio"] = value["value"]
                elif metric_type == "STRIDE_LENGTH" and "value" in value:
                    new_point["stride_length"] = value["value"]
                elif metric_type == "POWER" and "value" in value:
                    new_point["power"] = value["value"]

                processed_points.append(new_point)

    # Process lap metrics
    # Some of these metrics might be in the splits data
    splits = detailed_metrics.get("splits", [])
    for i, split in enumerate(splits):
        # Skip if missing timestamp
        if "startTimeGMT" not in split:
            continue

        # Parse timestamp
        try:
            timestamp = datetime.strptime(split["startTimeGMT"], "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            try:
                timestamp = datetime.strptime(split["startTimeGMT"], "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                logger.error(f"Could not parse timestamp for split: {split.get('startTimeGMT')}")
                continue

        # Convert dynamic metrics to our format
        new_point = {
            "timestamp": timestamp,
            "heart_rate": split.get("averageHR"),
            "pace": split.get("averageSpeed"),
            "cadence": split.get("averageRunCadence"),
            "vertical_oscillation": split.get("verticalOscillation"),
            "vertical_ratio": split.get("verticalRatio"),
            "ground_contact_time": split.get("groundContactTime"),
            "stride_length": split.get("strideLength"),
            "power": split.get("averagePower"),
            "message_index": split.get("messageIndex"),
            "lap_index": split.get("lapIndex"),
            "distance": split.get("distance"),
            "duration": split.get("duration"),
            "start_latitude": split.get("startLatitude"),
            "start_longitude": split.get("startLongitude"),
            "end_latitude": split.get("endLatitude"),
            "end_longitude": split.get("endLongitude"),
            "elevation_gain": split.get("elevationGain"),
            "elevation_loss": split.get("elevationLoss")
        }

        # Check if metrics already exist for this timestamp
        duplicate = False
        for point in processed_points:
            if point["timestamp"] == timestamp:
                # Update existing point with any missing values
                for key, value in new_point.items():
                    if value is not None and key != "timestamp":
                        if point[key] is None:
                            point[key] = value
                duplicate = True
                break

        if not duplicate:
            processed_points.append(new_point)

    return processed_points


def process_route_points(gps_data):
    """Process GPS route points from the activity"""
    route_points = []

    if not gps_data:
        return route_points

    for point in gps_data:
        if "lat" not in point or "lon" not in point or "time" not in point:
            continue

        # Convert timestamp from milliseconds if needed
        try:
            timestamp = datetime.fromtimestamp(point["time"] / 1000.0)
        except (ValueError, TypeError, OverflowError):
            logger.error(f"Invalid timestamp in route point: {point.get('time')}")
            continue

        route_points.append({
            "timestamp": timestamp,
            "latitude": point.get("lat"),
            "longitude": point.get("lon"),
            "altitude": point.get("altitude"),
            "speed": point.get("speed"),
            "cumulative_ascent": point.get("cumulativeAscent"),
            "cumulative_descent": point.get("cumulativeDescent"),
            "distance_from_previous": point.get("distanceFromPreviousPoint"),
            "distance_in_meters": point.get("distanceInMeters")
        })

    return route_points


def process_heart_rate_zones(hr_data):
    """Process heart rate zone data from the activity"""
    hr_zones = []

    if not hr_data:
        return hr_zones

    zones = hr_data.get("zones", [])

    for zone in zones:
        hr_zones.append({
            "zone_number": zone.get("zoneNumber"),
            "seconds_in_zone": zone.get("secsInZone"),
            "zone_low_boundary": zone.get("zoneLowBoundary")
        })

    return hr_zones


def insert_workout_metrics(cursor, workout_id, metric_points):
    """Insert detailed workout metrics into the database"""
    if not metric_points:
        logger.warning(f"No metric points to insert for workout ID: {workout_id}")
        return 0

    # Prepare batch insert values
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
            point.get("power"),
            point.get("stride_length"),
            point.get("lap_index"),
            point.get("message_index"),
            point.get("distance"),
            point.get("duration"),
            point.get("start_latitude"),
            point.get("start_longitude"),
            point.get("end_latitude"),
            point.get("end_longitude"),
            point.get("elevation_gain"),
            point.get("elevation_loss")
        ))

    # Insert metrics in batches
    try:
        rows_inserted = 0
        batch_size = 1000  # Insert in batches of 1000

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO WorkoutMetrics (
                    WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence,
                    VerticalOscillation, VerticalRatio, GroundContactTime,
                    Power, StrideLength, LapIndex, MessageIndex,
                    Distance, Duration, StartLatitude, StartLongitude,
                    EndLatitude, EndLongitude, ElevationGain, ElevationLoss
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)
            logger.info(f"Inserted batch of {len(batch)} metrics (total: {rows_inserted})")

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting workout metrics: {e}")
        return 0


def insert_route_points(cursor, workout_id, route_points):
    """Insert GPS route points into the database"""
    if not route_points:
        logger.info(f"No route points to insert for workout ID: {workout_id}")
        return 0

    # Prepare batch insert values
    values = []
    for point in route_points:
        values.append((
            workout_id,
            point.get("timestamp"),
            point.get("latitude"),
            point.get("longitude"),
            point.get("altitude"),
            point.get("speed"),
            point.get("cumulative_ascent"),
            point.get("cumulative_descent"),
            point.get("distance_from_previous"),
            point.get("distance_in_meters")
        ))

    # Insert route points in batches
    try:
        rows_inserted = 0
        batch_size = 1000  # Insert in batches of 1000

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO WorkoutRoutePoints (
                    WorkoutID, Timestamp, Latitude, Longitude, 
                    Altitude, Speed, CumulativeAscent, CumulativeDescent,
                    DistanceFromPreviousPoint, DistanceInMeters
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)
            logger.info(f"Inserted batch of {len(batch)} route points (total: {rows_inserted})")

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting route points: {e}")
        return 0


def insert_heart_rate_zones(cursor, workout_id, hr_zones):
    """Insert heart rate zone data into the database"""
    if not hr_zones:
        logger.info(f"No heart rate zones to insert for workout ID: {workout_id}")
        return 0

    # Prepare insert values
    values = []
    for zone in hr_zones:
        values.append((
            workout_id,
            zone.get("zone_number"),
            zone.get("seconds_in_zone"),
            zone.get("zone_low_boundary")
        ))

    # Insert HR zones
    try:
        cursor.executemany("""
            INSERT INTO WorkoutHeartRateZones (
                WorkoutID, ZoneNumber, SecondsInZone, ZoneLowBoundary
            )
            VALUES (?, ?, ?, ?)
        """, values)

        rows_inserted = len(values)
        logger.info(f"Inserted {rows_inserted} heart rate zones")

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting heart rate zones: {e}")
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

        # Verify database structure
        check_table_structure(cursor)

        # Begin transaction
        activities_inserted = 0
        metrics_inserted = 0
        route_points_inserted = 0
        hr_zones_inserted = 0

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

                # Process and insert workout metrics (laps, splits)
                metric_points = process_metric_points(detailed_metrics)
                if metric_points:
                    rows = insert_workout_metrics(cursor, workout_id, metric_points)
                    metrics_inserted += rows
                    logger.info(f"Inserted {rows} detailed metric points for workout ID {workout_id}")
                else:
                    logger.warning(f"No detailed metrics found for activity ID {activity_id}")

                # Process and insert GPS route points
                route_points = process_route_points(detailed_metrics.get("gps_data", []))
                if route_points:
                    rows = insert_route_points(cursor, workout_id, route_points)
                    route_points_inserted += rows
                    logger.info(f"Inserted {rows} route points for workout ID {workout_id}")

                # Process and insert heart rate zones
                hr_zones = process_heart_rate_zones(detailed_metrics.get("hr_data", {}))
                if hr_zones:
                    rows = insert_heart_rate_zones(cursor, workout_id, hr_zones)
                    hr_zones_inserted += rows
                    logger.info(f"Inserted {rows} heart rate zones for workout ID {workout_id}")

        # Commit and close
        conn.commit()
        cursor.close()
        conn.close()

        print(
            f"All activities inserted successfully! ({activities_inserted} new activities, "
            f"{metrics_inserted} metric points, {route_points_inserted} route points, "
            f"{hr_zones_inserted} heart rate zones)"
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