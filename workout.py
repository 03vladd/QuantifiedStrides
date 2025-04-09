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


def check_table_structure(cursor):
    """Check if necessary tables exist and create them if they don't"""
    try:
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
            ("ElevationLoss", "FLOAT"),
            ("StrideLength", "FLOAT")
        ]

        for column_name, data_type in required_columns:
            cursor.execute(f"""
                IF NOT EXISTS (SELECT * FROM sys.columns 
                              WHERE object_id = OBJECT_ID('WorkoutMetrics') AND name = '{column_name}')
                ALTER TABLE WorkoutMetrics 
                ADD {column_name} {data_type} NULL
            """)

        logger.info("Database structure verified and updated if needed")
        return True
    except Exception as e:
        logger.error(f"Error checking table structure: {e}")
        return False


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


def get_detailed_workout_metrics(client, activity_id):
    """Get detailed metrics for an activity"""
    logger.info(f"Fetching detailed metrics for activity ID: {activity_id}")

    try:
        # Get activity details with metrics (includes laps and splits)
        details = {}
        try:
            details = client.get_activity_details(activity_id)
            logger.info(f"Successfully retrieved activity details")
        except Exception as e:
            logger.warning(f"Could not get activity details: {e}")

        # Get split data if available
        splits = []
        try:
            splits = client.get_activity_splits(activity_id)
            logger.info(f"Successfully retrieved {len(splits) if isinstance(splits, list) else '0'} splits")
        except Exception as e:
            logger.warning(f"Could not get splits for activity {activity_id}: {e}")

        # Get HR data if available
        hr_data = {}
        try:
            hr_data = client.get_activity_hr_in_timezones(activity_id)
            logger.info(f"Successfully retrieved heart rate zone data")
        except Exception as e:
            logger.warning(f"Could not get HR zones for activity {activity_id}: {e}")

        # Get GPS route data if available - try different methods
        gps_data = []
        try:
            # Try different methods that might exist
            if hasattr(client, 'get_activity_route'):
                gps_data = client.get_activity_route(activity_id)
            elif hasattr(client, 'get_activity_gps_route'):
                gps_data = client.get_activity_gps_route(activity_id)
            elif hasattr(client, 'get_activity_gps'):
                gps_data = client.get_activity_gps(activity_id)
            else:
                # Last resort: try to get from details
                if details and isinstance(details, dict):
                    gps_data = details.get('gpsData', [])

            logger.info(f"Retrieved GPS data of type: {type(gps_data)}")
        except Exception as e:
            logger.warning(f"Could not get GPS route for activity {activity_id}: {e}")

        # Ensure gps_data is a list
        if isinstance(gps_data, dict):
            # Try common dictionary structures
            if 'points' in gps_data:
                gps_data = gps_data.get('points', [])
            elif 'gpsData' in gps_data:
                gps_data = gps_data.get('gpsData', [])
            else:
                logger.warning(f"GPS data in unexpected dictionary format")
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
        return {
            "details": {},
            "splits": [],
            "hr_data": {},
            "gps_data": []
        }


def process_metric_points(detailed_metrics):
    """Process and extract time-series data points from detailed metrics"""
    processed_points = []

    try:
        # Process activity details
        details = detailed_metrics.get("details", {})

        # Process metrics from details
        if isinstance(details, dict):
            metrics_list = []

            # Try different places where metrics might be found
            if "metrics" in details:
                metrics_list = details.get("metrics", [])
            elif "activityMetrics" in details:
                metrics_list = details.get("activityMetrics", [])

            # Process each metric type
            for metric in metrics_list:
                if not isinstance(metric, dict):
                    continue

                metric_type = metric.get("metricType", "")
                metric_values = metric.get("metrics", [])

                if not metric_values:
                    continue

                # Process each data point for this metric
                for value in metric_values:
                    if not isinstance(value, dict) or "startTimeGMT" not in value:
                        continue

                    # Parse timestamp
                    timestamp = None
                    time_str = value.get("startTimeGMT", "")

                    if time_str:
                        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
                            try:
                                timestamp = datetime.strptime(time_str, fmt)
                                break
                            except ValueError:
                                continue

                    if not timestamp:
                        continue

                    # Look for existing point with this timestamp
                    existing_point = None
                    for point in processed_points:
                        if point["timestamp"] == timestamp:
                            existing_point = point
                            break

                    # Add or update point
                    if existing_point:
                        # Update existing point
                        if metric_type == "HEART_RATE" and "value" in value:
                            existing_point["heart_rate"] = value.get("value")
                        elif metric_type == "SPEED" and "value" in value:
                            existing_point["pace"] = value.get("value")
                        elif metric_type == "CADENCE" and "value" in value:
                            existing_point["cadence"] = value.get("value")
                        elif metric_type == "VERTICAL_OSCILLATION" and "value" in value:
                            existing_point["vertical_oscillation"] = value.get("value")
                        elif metric_type == "GROUND_CONTACT_TIME" and "value" in value:
                            existing_point["ground_contact_time"] = value.get("value")
                        elif metric_type == "VERTICAL_RATIO" and "value" in value:
                            existing_point["vertical_ratio"] = value.get("value")
                        elif metric_type == "STRIDE_LENGTH" and "value" in value:
                            existing_point["stride_length"] = value.get("value")
                        elif metric_type == "POWER" and "value" in value:
                            existing_point["power"] = value.get("value")
                    else:
                        # Create new point
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
                            "lap_index": None,
                            "message_index": None,
                            "distance": None,
                            "duration": None,
                            "start_latitude": None,
                            "start_longitude": None,
                            "end_latitude": None,
                            "end_longitude": None,
                            "elevation_gain": None,
                            "elevation_loss": None
                        }

                        # Set the specific metric
                        if metric_type == "HEART_RATE" and "value" in value:
                            new_point["heart_rate"] = value.get("value")
                        elif metric_type == "SPEED" and "value" in value:
                            new_point["pace"] = value.get("value")
                        elif metric_type == "CADENCE" and "value" in value:
                            new_point["cadence"] = value.get("value")
                        elif metric_type == "VERTICAL_OSCILLATION" and "value" in value:
                            new_point["vertical_oscillation"] = value.get("value")
                        elif metric_type == "GROUND_CONTACT_TIME" and "value" in value:
                            new_point["ground_contact_time"] = value.get("value")
                        elif metric_type == "VERTICAL_RATIO" and "value" in value:
                            new_point["vertical_ratio"] = value.get("value")
                        elif metric_type == "STRIDE_LENGTH" and "value" in value:
                            new_point["stride_length"] = value.get("value")
                        elif metric_type == "POWER" and "value" in value:
                            new_point["power"] = value.get("value")

                        processed_points.append(new_point)

        # Process splits data
        splits = detailed_metrics.get("splits", [])

        if isinstance(splits, list):
            for split in splits:
                if not isinstance(split, dict):
                    continue

                # Check if this is a lapDTOs field
                if "lapDTOs" in split:
                    # Use the nested lapDTOs instead
                    laps = split.get("lapDTOs", [])
                    if isinstance(laps, list):
                        for lap in laps:
                            process_single_lap(lap, processed_points)
                else:
                    # Process normal split
                    process_single_lap(split, processed_points)

        if processed_points:
            logger.info(f"Processed {len(processed_points)} metric points")
        else:
            logger.warning(f"No detailed metrics extracted for activity ID")

        return processed_points
    except Exception as e:
        logger.error(f"Error processing metric points: {e}")
        return []


def process_single_lap(lap, processed_points):
    """Process a single lap/split and add to processed_points"""
    if not isinstance(lap, dict):
        return

    # Try to get timestamp
    timestamp = None
    if "startTimeGMT" in lap:
        time_str = lap.get("startTimeGMT")

        for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                timestamp = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue

    if not timestamp:
        return

    # Create a new data point
    new_point = {
        "timestamp": timestamp,
        "heart_rate": lap.get("averageHR"),
        "pace": lap.get("averageSpeed"),
        "cadence": lap.get("averageRunCadence"),
        "vertical_oscillation": lap.get("verticalOscillation"),
        "vertical_ratio": lap.get("verticalRatio"),
        "ground_contact_time": lap.get("groundContactTime"),
        "stride_length": lap.get("strideLength"),
        "power": lap.get("averagePower"),
        "lap_index": lap.get("lapIndex"),
        "message_index": lap.get("messageIndex"),
        "distance": lap.get("distance"),
        "duration": lap.get("duration"),
        "start_latitude": lap.get("startLatitude"),
        "start_longitude": lap.get("startLongitude"),
        "end_latitude": lap.get("endLatitude"),
        "end_longitude": lap.get("endLongitude"),
        "elevation_gain": lap.get("elevationGain"),
        "elevation_loss": lap.get("elevationLoss")
    }

    # Check for existing point with this timestamp
    existing = False
    for point in processed_points:
        if point["timestamp"] == timestamp:
            # Update existing point with non-null values
            for key, value in new_point.items():
                if value is not None and key != "timestamp":
                    if point[key] is None:
                        point[key] = value
            existing = True
            break

    if not existing:
        processed_points.append(new_point)


def process_route_points(gps_data):
    """Process GPS route points from the activity"""
    route_points = []

    if not gps_data:
        logger.info("No GPS route points available")
        return route_points

    try:
        # Check data format
        if not isinstance(gps_data, list):
            logger.warning(f"GPS data not in expected list format: {type(gps_data)}")
            return route_points

        # Process each GPS point
        for i, point in enumerate(gps_data):
            if not isinstance(point, dict):
                continue

            # Check for lat/lon coordinates
            has_lat_lon = all(key in point for key in ['lat', 'lon'])
            has_latitude_longitude = all(key in point for key in ['latitude', 'longitude'])

            if not has_lat_lon and not has_latitude_longitude:
                continue

            # Get coordinates (try different field names)
            latitude = point.get('lat', point.get('latitude'))
            longitude = point.get('lon', point.get('longitude'))

            # Get timestamp (try different field names and formats)
            timestamp = None
            if 'time' in point:
                try:
                    # Try parsing as unix timestamp (milliseconds)
                    time_val = point['time']
                    if isinstance(time_val, (int, float)):
                        timestamp = datetime.fromtimestamp(time_val / 1000.0)
                except (ValueError, TypeError, OverflowError):
                    pass

            if timestamp is None and 'startTimeGMT' in point:
                time_str = point['startTimeGMT']
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        timestamp = datetime.strptime(time_str, fmt)
                        break
                    except ValueError:
                        continue

            # If no timestamp, use a sequential one
            if timestamp is None:
                timestamp = datetime.now() + timedelta(seconds=i)

            # Create route point
            route_point = {
                "timestamp": timestamp,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": point.get("altitude", point.get("ele")),
                "speed": point.get("speed"),
                "cumulative_ascent": point.get("cumulativeAscent"),
                "cumulative_descent": point.get("cumulativeDescent"),
                "distance_from_previous": point.get("distanceFromPreviousPoint"),
                "distance_in_meters": point.get("distanceInMeters")
            }

            route_points.append(route_point)

        if route_points:
            logger.info(f"Processed {len(route_points)} GPS route points")

        return route_points
    except Exception as e:
        logger.error(f"Error processing route points: {e}")
        return []


def process_heart_rate_zones(hr_data):
    """Process heart rate zone data from the activity"""
    hr_zones = []

    if not hr_data:
        return hr_zones

    try:
        # Handle different data formats
        zones = []

        # If hr_data is a list, it might be the zones directly
        if isinstance(hr_data, list):
            zones = hr_data
        # If hr_data is a dict, look for zones in various places
        elif isinstance(hr_data, dict):
            # Check different possible locations
            for key in ['zones', 'timeInZones', 'heartRateZones']:
                if key in hr_data and isinstance(hr_data[key], list):
                    zones = hr_data[key]
                    break

            # If still not found, check allZones
            if not zones and 'allZones' in hr_data and isinstance(hr_data['allZones'], dict):
                zones = hr_data['allZones'].get('zones', [])

        # Process each zone
        for zone in zones:
            if not isinstance(zone, dict):
                continue

            # Get zone data (try different field names)
            zone_number = zone.get("zoneNumber", zone.get("zone"))
            seconds_in_zone = zone.get("secsInZone", zone.get("timeInZone", zone.get("seconds")))
            zone_low_boundary = zone.get("zoneLowBoundary", zone.get("min", zone.get("lower")))

            # Skip if missing essential data
            if zone_number is None or seconds_in_zone is None:
                continue

            hr_zones.append({
                "zone_number": zone_number,
                "seconds_in_zone": seconds_in_zone,
                "zone_low_boundary": zone_low_boundary
            })

        return hr_zones
    except Exception as e:
        logger.error(f"Error processing heart rate zones: {e}")
        return []


def insert_workout_metrics(cursor, workout_id, metric_points):
    """Insert detailed workout metrics into the database"""
    if not metric_points:
        logger.warning(f"No metric points to insert for workout ID: {workout_id}")
        return 0

    try:
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
        logger.info(f"No route points to insert for workout ID {workout_id}")
        return 0

    try:
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
        logger.info(f"No heart rate zones to insert for workout ID {workout_id}")
        return 0

    try:
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

        # Verify database structure
        check_table_structure(cursor)

        # Track insertion statistics
        activities_inserted = 0
        metrics_inserted = 0
        route_points_inserted = 0
        hr_zones_inserted = 0

        # Process each activity
        for activity in activities:
            try:
                # Extract activity ID early for better error reporting
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

                    # Check if workout metrics already exist
                    cursor.execute("SELECT COUNT(*) FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
                    metrics_count = cursor.fetchone()[0]

                    if metrics_count > 0:
                        # Check if we have heart rate zones
                        cursor.execute("SELECT COUNT(*) FROM WorkoutHeartRateZones WHERE WorkoutID = ?", (workout_id,))
                        hr_count = cursor.fetchone()[0]

                        if hr_count > 0:
                            logger.info(f"Workout ID {workout_id} already has metrics and HR zones. Skipping...")
                            continue

                    logger.info(f"Adding detailed metrics to existing workout ID: {workout_id}")
                else:
                    # Insert the new workout
                    workout_id = insert_workout(cursor, processed_data)
                    if workout_id:
                        activities_inserted += 1
                        logger.info(
                            f"Inserted workout: {processed_data['workout_type']} on {processed_data['workout_date']} (ID: {workout_id})")
                    else:
                        logger.error(f"Failed to insert workout for activity ID: {activity_id}")
                        continue

                # Get detailed metrics for the workout
                logger.info(f"Fetching detailed metrics for activity ID: {activity_id}")
                detailed_metrics = get_detailed_workout_metrics(client, activity_id)

                # Process and insert workout metrics (time series data, laps, splits)
                metric_points = process_metric_points(detailed_metrics)
                if metric_points:
                    rows = insert_workout_metrics(cursor, workout_id, metric_points)
                    metrics_inserted += rows
                    logger.info(f"Inserted {rows} detailed metric points for workout ID {workout_id}")

                # Process and insert GPS route points
                gps_data = detailed_metrics.get("gps_data", [])
                if gps_data:
                    route_points = process_route_points(gps_data)
                    if route_points:
                        rows = insert_route_points(cursor, workout_id, route_points)
                        route_points_inserted += rows
                        logger.info(f"Inserted {rows} route points for workout ID {workout_id}")
                    else:
                        logger.info(f"No GPS route points available for workout ID {workout_id}")
                else:
                    logger.info(f"No GPS data available for workout ID {workout_id}")

                # Process and insert heart rate zones
                hr_data = detailed_metrics.get("hr_data", {})
                hr_zones = process_heart_rate_zones(hr_data)
                if hr_zones:
                    rows = insert_heart_rate_zones(cursor, workout_id, hr_zones)
                    hr_zones_inserted += rows
                    logger.info(f"Inserted {rows} heart rate zones for workout ID {workout_id}")
                else:
                    logger.info(f"No heart rate zone data available for workout ID {workout_id}")

                # Commit after each activity is fully processed
                conn.commit()
                logger.info(f"Successfully processed and committed activity ID: {activity_id}")

            except Exception as e:
                logger.error(f"Error processing activity: {e}")
                # Rollback changes for this activity
                conn.rollback()
                # Continue to next activity
                continue

        # Close connections
        cursor.close()
        conn.close()

        # Print summary
        print(
            f"All activities inserted successfully! ({activities_inserted} new activities, "
            f"{metrics_inserted} metric points, {route_points_inserted} route points, "
            f"{hr_zones_inserted} heart rate zones)"
        )
        return 0

    except Exception as e:
        logger.error(f"Error in workout data collection: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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