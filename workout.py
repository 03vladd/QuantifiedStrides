from datetime import datetime, timedelta
import os
import garminconnect
import pyodbc
import json
import logging
import sys
import config

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("workout")


def connect_to_garmin():
    """Connect to Garmin API and return client."""
    client = garminconnect.Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
    client.login()
    return client


def connect_to_database():
    """Connect to the database and return connection and cursor."""
    try:
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def check_existing_workout(cursor, user_id, start_time):
    """Check if a workout already exists with the same start time."""
    cursor.execute(
        "SELECT WorkoutID FROM Workouts WHERE UserID = ? AND StartTime = ?",
        (user_id, start_time)
    )
    return cursor.fetchone()


def check_has_is_indoor_column(cursor):
    """Check if the Workouts table has the IsIndoor column."""
    try:
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
    """Determine if a workout is indoor based on sport type keywords."""
    return any(keyword in str(sport_type).lower() for keyword in config.INDOOR_KEYWORDS)


def parse_activity(activity):
    """
    Parse a single activity summary from Garmin.
    This includes top-level fields like 'activityId', 'startTimeLocal', 'duration', etc.
    """
    user_id = config.DEFAULT_USER_ID
    sport = activity.get("activityType", {}).get("typeKey", "Unknown")
    workout_type = activity.get("activityName", "Unknown")
    is_indoor = is_indoor_workout(sport)

    start_time_str = activity.get("startTimeLocal", None)
    if start_time_str:
        # Often "YYYY-MM-DDTHH:MM:SS"
        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                # fallback if there's space instead of T
                start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.error(f"Could not parse start time: {start_time_str}")
                start_time_dt = datetime.now()
    else:
        start_time_dt = datetime.now()

    # durations in seconds
    duration_seconds = activity.get("duration", 0.0)
    end_time_dt = start_time_dt + timedelta(seconds=float(duration_seconds))

    workout_date = start_time_dt.date()

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
        "activity_id": activity.get("activityId", None)  # crucial for fetching detailed data
    }
    return processed_data


def insert_workout(cursor, data):
    """
    Insert the top-level workout into the database, returning the new local workout_id.
    """
    has_is_indoor = check_has_is_indoor_column(cursor)
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
            data["user_id"], data["sport"], data["start_time"], data["end_time"],
            data["workout_type"], data["calories_burned"], data["avg_heart_rate"],
            data["max_heart_rate"], data["vo2max"], data["lactate_threshold"],
            data["time_in_zone_1"], data["time_in_zone_2"], data["time_in_zone_3"],
            data["time_in_zone_4"], data["time_in_zone_5"], data["training_volume"],
            data["avg_vertical_osc"], data["avg_ground_contact"], data["avg_stride_length"],
            data["avg_vertical_ratio"], data["avg_running_cadence"], data["max_running_cadence"],
            data["location"], data["workout_date"], data["is_indoor"]
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
            data["user_id"], data["sport"], data["start_time"], data["end_time"],
            data["workout_type"], data["calories_burned"], data["avg_heart_rate"],
            data["max_heart_rate"], data["vo2max"], data["lactate_threshold"],
            data["time_in_zone_1"], data["time_in_zone_2"], data["time_in_zone_3"],
            data["time_in_zone_4"], data["time_in_zone_5"], data["training_volume"],
            data["avg_vertical_osc"], data["avg_ground_contact"], data["avg_stride_length"],
            data["avg_vertical_ratio"], data["avg_running_cadence"], data["max_running_cadence"],
            data["location"], data["workout_date"]
        )

    cursor.execute(sql_insert, params)
    # Return the newly inserted ID
    cursor.execute("SELECT @@IDENTITY")
    workout_id = cursor.fetchone()[0]
    return workout_id


def get_detailed_workout_metrics(client, activity_id):
    """
    Use the activity_id to get a more detailed breakdown:
    activity details, splits, HR in timezones, etc.
    """
    logger.info(f"Fetching detailed metrics for activity ID: {activity_id}")
    details = {}

    try:
        # Main activity details with metrics
        details["activityDetails"] = client.get_activity_details(activity_id)
    except Exception as e:
        logger.error(f"Error fetching activity_details for {activity_id}: {e}")
        details["activityDetails"] = {}

    try:
        # Get split data if available
        details["splits"] = client.get_activity_splits(activity_id)
    except Exception as e:
        logger.warning(f"Could not get splits for activity {activity_id}: {e}")
        details["splits"] = []

    try:
        # Get HR data if available
        details["hrZones"] = client.get_activity_hr_in_timezones(activity_id)
    except Exception as e:
        logger.warning(f"Could not get HR zones for activity {activity_id}: {e}")
        details["hrZones"] = {}

    # Save the full detailed data to a JSON file for inspection
    try:
        with open(f"activity_{activity_id}_details.json", "w") as f:
            json.dump(details, f, indent=2)
        logger.info(f"Saved detailed activity data to activity_{activity_id}_details.json")
    except Exception as e:
        logger.warning(f"Could not save activity details to file: {e}")

    return details


def process_metric_points(detailed_metrics):
    """
    Extract time-series data from the activity details.
    This function focuses specifically on the metrics array in activityDetails.
    """
    processed_points = []

    activity_details = detailed_metrics.get("activityDetails", {})

    # The metrics array contains time series data grouped by metric type
    metrics_array = activity_details.get("metrics", [])

    if not metrics_array:
        logger.warning("No metrics array found in activity details")
        return processed_points

    # Create a dictionary to store metrics by timestamp
    metrics_by_timestamp = {}

    # Process each metric type
    for metric in metrics_array:
        metric_type = metric.get("metricType", "")
        metric_values = metric.get("metrics", [])

        if not metric_values:
            continue

        logger.info(f"Processing {len(metric_values)} {metric_type} values")

        for value in metric_values:
            # Skip if no timestamp
            if "startTimeGMT" not in value:
                continue

            # Parse timestamp
            try:
                timestamp_str = value.get("startTimeGMT")
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
            except Exception as e:
                logger.error(f"Could not parse timestamp: {value.get('startTimeGMT')}, error: {e}")
                continue

            # Get the metric value
            metric_value = value.get("value")

            # Initialize timestamp entry if it doesn't exist
            if timestamp not in metrics_by_timestamp:
                metrics_by_timestamp[timestamp] = {"timestamp": timestamp}

            # Add the metric value to the timestamp entry based on the metric type
            if metric_type == "HEART_RATE":
                metrics_by_timestamp[timestamp]["heart_rate"] = metric_value
            elif metric_type == "SPEED":
                metrics_by_timestamp[timestamp]["pace"] = metric_value
            elif metric_type == "CADENCE":
                metrics_by_timestamp[timestamp]["cadence"] = metric_value
            elif metric_type == "VERTICAL_OSCILLATION":
                metrics_by_timestamp[timestamp]["vertical_oscillation"] = metric_value
            elif metric_type == "GROUND_CONTACT_TIME":
                metrics_by_timestamp[timestamp]["ground_contact_time"] = metric_value
            elif metric_type == "VERTICAL_RATIO":
                metrics_by_timestamp[timestamp]["vertical_ratio"] = metric_value
            elif metric_type == "STRIDE_LENGTH":
                metrics_by_timestamp[timestamp]["stride_length"] = metric_value
            elif metric_type == "POWER":
                metrics_by_timestamp[timestamp]["power"] = metric_value
            elif metric_type == "ELEVATION":
                metrics_by_timestamp[timestamp]["altitude"] = metric_value
            elif metric_type == "TEMPERATURE":
                metrics_by_timestamp[timestamp]["temperature"] = metric_value

    # Convert the dictionary to a list
    for timestamp, metrics in metrics_by_timestamp.items():
        processed_points.append(metrics)

    # Sort by timestamp
    processed_points.sort(key=lambda x: x["timestamp"])

    # Log summary of metrics found
    if processed_points:
        sample_point = processed_points[0]
        available_metrics = [key for key in sample_point.keys() if key != "timestamp"]
        logger.info(f"Found {len(processed_points)} data points with metrics: {', '.join(available_metrics)}")
    else:
        logger.warning("No metric points were processed")

    return processed_points


def insert_workout_metrics(cursor, workout_id, metric_points):
    """
    Insert detailed workout metrics into the DB.
    Handles batching and ensures proper error handling.
    """
    if not metric_points:
        logger.warning(f"No metric points to insert for workout ID: {workout_id}")
        return 0

    # First, clear any existing metrics for this workout to avoid duplicates
    try:
        cursor.execute("DELETE FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
        logger.info(f"Deleted existing metrics for workout ID {workout_id}")
    except Exception as e:
        logger.warning(f"Error deleting existing metrics: {e}")

    # Get column information for WorkoutMetrics table - using LIMIT instead of TOP for MySQL
    try:
        cursor.execute("SELECT * FROM WorkoutMetrics LIMIT 0")
        columns = [column[0] for column in cursor.description]
        logger.info(f"WorkoutMetrics table columns: {', '.join(columns)}")
    except Exception as e:
        logger.error(f"Could not get table structure: {e}")
        return 0

    # Prepare values for batch insert
    values = []
    for point in metric_points:
        # Skip if missing timestamp
        if "timestamp" not in point:
            continue

        # Extract values with defaults for missing metrics
        timestamp = point.get("timestamp")
        heart_rate = point.get("heart_rate")
        pace = point.get("pace")
        cadence = point.get("cadence")
        vertical_oscillation = point.get("vertical_oscillation")
        vertical_ratio = point.get("vertical_ratio")
        ground_contact_time = point.get("ground_contact_time")
        power = point.get("power")
        altitude = point.get("altitude")
        temperature = point.get("temperature")
        stride_length = point.get("stride_length")

        values.append((
            workout_id, timestamp, heart_rate, pace, cadence,
            vertical_oscillation, vertical_ratio, ground_contact_time,
            power, altitude, temperature, stride_length
        ))

    # Use batch insert for better performance
    rows_inserted = 0
    batch_size = 1000  # Insert in batches of 1000

    try:
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            try:
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
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")
                # Try inserting individually to identify problem records
                for record in batch:
                    try:
                        cursor.execute("""
                            INSERT INTO WorkoutMetrics (
                                WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence, 
                                VerticalOscillation, VerticalRatio, GroundContactTime,
                                Power, Altitude, Temperature, StrideLength
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, record)
                        rows_inserted += 1
                    except Exception as e2:
                        logger.error(f"Error inserting record: {e2}, values: {record}")
    except Exception as e:
        logger.error(f"Error in batch insertion: {e}")

    return rows_inserted


def process_saved_activity_json(activity_id, workout_id):
    """
    Process a previously saved activity JSON file and extract all time series data.
    This function reads the JSON file, extracts all available metrics, and inserts them into the database.
    """
    json_file_path = f"activity_{activity_id}_details.json"

    logger.info(f"Processing saved activity JSON from {json_file_path}")

    try:
        # Read the JSON file
        with open(json_file_path, 'r') as f:
            detailed_metrics = json.load(f)

        # Connect to database
        conn, cursor = connect_to_database()

        # Clear existing metrics for this workout
        try:
            cursor.execute("DELETE FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
            logger.info(f"Deleted existing metrics for workout ID {workout_id}")
        except Exception as e:
            logger.warning(f"Error deleting existing metrics: {e}")

        # Extract time series data
        activity_details = detailed_metrics.get("activityDetails", {})
        metrics_array = activity_details.get("metrics", [])

        # Dictionary to collect metrics by timestamp
        metrics_by_timestamp = {}

        if metrics_array:
            logger.info(f"Found {len(metrics_array)} metric types in the JSON file")

            # Process each metric type (HR, Pace, Cadence, etc.)
            for metric in metrics_array:
                metric_type = metric.get("metricType", "Unknown")
                metric_values = metric.get("metrics", [])

                if not metric_values:
                    continue

                logger.info(f"Processing {len(metric_values)} values for {metric_type}")

                # Process each data point for this metric type
                for value in metric_values:
                    # Skip if no timestamp
                    if "startTimeGMT" not in value:
                        continue

                    # Parse timestamp
                    try:
                        timestamp_str = value.get("startTimeGMT")
                        try:
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
                    except Exception as e:
                        logger.error(f"Could not parse timestamp: {value.get('startTimeGMT')}, error: {e}")
                        continue

                    # Get the metric value
                    metric_value = value.get("value")

                    # Skip if no value
                    if metric_value is None:
                        continue

                    # Initialize timestamp entry if it doesn't exist
                    if timestamp not in metrics_by_timestamp:
                        metrics_by_timestamp[timestamp] = {"timestamp": timestamp}

                    # Map Garmin metric types to database columns
                    if metric_type == "HEART_RATE":
                        metrics_by_timestamp[timestamp]["heart_rate"] = metric_value
                    elif metric_type == "SPEED":
                        metrics_by_timestamp[timestamp]["pace"] = metric_value
                    elif metric_type == "CADENCE":
                        metrics_by_timestamp[timestamp]["cadence"] = metric_value
                    elif metric_type == "VERTICAL_OSCILLATION":
                        metrics_by_timestamp[timestamp]["vertical_oscillation"] = metric_value
                    elif metric_type == "GROUND_CONTACT_TIME":
                        metrics_by_timestamp[timestamp]["ground_contact_time"] = metric_value
                    elif metric_type == "VERTICAL_RATIO":
                        metrics_by_timestamp[timestamp]["vertical_ratio"] = metric_value
                    elif metric_type == "STRIDE_LENGTH":
                        metrics_by_timestamp[timestamp]["stride_length"] = metric_value
                    elif metric_type == "POWER":
                        metrics_by_timestamp[timestamp]["power"] = metric_value
                    elif metric_type == "ELEVATION" or metric_type == "ALTITUDE":
                        metrics_by_timestamp[timestamp]["altitude"] = metric_value
                    elif metric_type == "TEMPERATURE":
                        metrics_by_timestamp[timestamp]["temperature"] = metric_value
        else:
            logger.warning("No metrics array found in the JSON file")

        # Convert the dictionary to a list
        processed_points = []
        for timestamp, metrics in metrics_by_timestamp.items():
            processed_points.append(metrics)

        # Sort by timestamp
        processed_points.sort(key=lambda x: x["timestamp"])

        # Print a summary of what we found
        if processed_points:
            logger.info(f"Extracted {len(processed_points)} data points from the JSON file")

            # Show metrics availability statistics
            metrics_count = {
                "heart_rate": sum(1 for p in processed_points if "heart_rate" in p),
                "pace": sum(1 for p in processed_points if "pace" in p),
                "cadence": sum(1 for p in processed_points if "cadence" in p),
                "power": sum(1 for p in processed_points if "power" in p),
                "altitude": sum(1 for p in processed_points if "altitude" in p),
                "vertical_oscillation": sum(1 for p in processed_points if "vertical_oscillation" in p),
                "ground_contact_time": sum(1 for p in processed_points if "ground_contact_time" in p),
                "vertical_ratio": sum(1 for p in processed_points if "vertical_ratio" in p),
                "stride_length": sum(1 for p in processed_points if "stride_length" in p),
                "temperature": sum(1 for p in processed_points if "temperature" in p)
            }

            print("\nMetrics availability in the JSON file:")
            for metric, count in metrics_count.items():
                percentage = (count / len(processed_points)) * 100 if processed_points else 0
                print(f"  {metric}: {count} points ({percentage:.1f}%)")

            # Insert the metrics into the database
            logger.info(f"Inserting {len(processed_points)} metric points for workout ID {workout_id}...")

            # Prepare values for insertion
            values = []
            for point in processed_points:
                # Skip if missing timestamp
                if "timestamp" not in point:
                    continue

                # Extract values with defaults for missing metrics
                timestamp = point.get("timestamp")
                heart_rate = point.get("heart_rate")
                pace = point.get("pace")
                cadence = point.get("cadence")
                vertical_oscillation = point.get("vertical_oscillation")
                vertical_ratio = point.get("vertical_ratio")
                ground_contact_time = point.get("ground_contact_time")
                power = point.get("power")
                altitude = point.get("altitude")
                temperature = point.get("temperature")
                stride_length = point.get("stride_length")

                values.append((
                    workout_id, timestamp, heart_rate, pace, cadence,
                    vertical_oscillation, vertical_ratio, ground_contact_time,
                    power, altitude, temperature, stride_length
                ))

            # Insert in batches
            rows_inserted = 0
            batch_size = 1000

            try:
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

                # Commit the changes
                conn.commit()
                logger.info(f"Successfully inserted {rows_inserted} metric points from JSON into WorkoutMetrics table")
                print(f"\nSuccessfully inserted {rows_inserted} metric points into WorkoutMetrics table")
            except Exception as e:
                logger.error(f"Error inserting metrics: {e}")
                conn.rollback()
        else:
            logger.warning("No data points extracted from the JSON file")

        # Close connections
        cursor.close()
        conn.close()

        return processed_points
    except Exception as e:
        logger.error(f"Error processing JSON file: {e}")
        import traceback
        traceback.print_exc()
        return []


def process_metrics_from_json_file(json_file_path, workout_id):
    """Process metrics from the saved JSON file using the correct data structure."""
    logger.info(f"Processing saved activity JSON from {json_file_path}")

    try:
        # Read the JSON file
        with open(json_file_path, 'r') as f:
            detailed_metrics = json.load(f)

        activity_details = detailed_metrics.get("activityDetails", {})

        # Get the metric descriptors which define what each index in the metrics array means
        metric_descriptors = activity_details.get("metricDescriptors", [])
        if not metric_descriptors:
            logger.warning("No metric descriptors found in the JSON")
            return []

        # Create a mapping of index to metric type
        metric_index_mapping = {}
        timestamp_index = None

        logger.info(f"Found {len(metric_descriptors)} metric descriptors")

        # Log all descriptors to understand the data structure
        for descriptor in metric_descriptors:
            metrics_index = descriptor.get("metricsIndex")
            key = descriptor.get("key")
            logger.info(f"Metric descriptor: index={metrics_index}, key={key}")

            # Store the mapping
            metric_index_mapping[metrics_index] = key

            # Find which index contains the timestamp
            if key in ["timeFromActivityStartInSeconds", "timeFromActivityStart", "timestamp"]:
                timestamp_index = metrics_index
                logger.info(f"Found timestamp index: {timestamp_index}")

        # If we couldn't identify the timestamp index, look for anything time-related
        if timestamp_index is None:
            for index, key in metric_index_mapping.items():
                if "time" in key.lower() or "timestamp" in key.lower():
                    timestamp_index = index
                    logger.info(f"Using alternative timestamp index: {timestamp_index} ({key})")
                    break

        # If we still don't have a timestamp index, try to use the last index as a fallback
        if timestamp_index is None and metric_descriptors:
            timestamp_index = max(descriptor.get("metricsIndex", 0) for descriptor in metric_descriptors)
            logger.warning(f"No timestamp index found, using last index ({timestamp_index}) as fallback")

        # Now process the actual metrics
        activity_detail_metrics = activity_details.get("activityDetailMetrics", [])
        logger.info(f"Found {len(activity_detail_metrics)} metric data points")

        # Create a list to hold processed points
        processed_points = []

        # Process each data point
        for i, data_point in enumerate(activity_detail_metrics):
            metrics_array = data_point.get("metrics", [])

            # Skip if no metrics or not enough elements
            if not metrics_array or timestamp_index is None or timestamp_index >= len(metrics_array):
                continue

            # Get the timestamp
            timestamp_value = metrics_array[timestamp_index]
            if timestamp_value is None:
                continue

            # Convert timestamp to datetime (assuming milliseconds since epoch)
            if isinstance(timestamp_value, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_value / 1000.0)
            else:
                # Try to parse as string if not a number
                try:
                    timestamp = datetime.strptime(str(timestamp_value), "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        timestamp = datetime.strptime(str(timestamp_value), "%Y-%m-%dT%H:%M:%SZ")
                    except:
                        logger.warning(f"Could not parse timestamp: {timestamp_value}")
                        continue

            # Initialize a point with the timestamp
            point = {"timestamp": timestamp}

            # Map each metric value to the appropriate field
            for index, value in enumerate(metrics_array):
                if index in metric_index_mapping and value is not None:
                    key = metric_index_mapping[index]

                    # Map the key to our database column
                    if "heartRate" in key or "hr" in key.lower():
                        point["heart_rate"] = value
                    elif "speed" in key.lower() or "pace" in key.lower():
                        point["pace"] = value
                    elif "cadence" in key.lower():
                        point["cadence"] = value
                    elif "verticalOscillation" in key or "vertical_oscillation" in key:
                        point["vertical_oscillation"] = value
                    elif "groundContactTime" in key or "ground_contact_time" in key:
                        point["ground_contact_time"] = value
                    elif "verticalRatio" in key or "vertical_ratio" in key:
                        point["vertical_ratio"] = value
                    elif "strideLength" in key or "stride_length" in key:
                        point["stride_length"] = value
                    elif "power" in key.lower():
                        point["power"] = value
                    elif "altitude" in key.lower() or "elevation" in key.lower():
                        point["altitude"] = value
                    elif "temperature" in key.lower() or "temp" in key.lower():
                        point["temperature"] = value

            # Add the point if it has metrics beyond just the timestamp
            if len(point) > 1:
                processed_points.append(point)

            # Log progress periodically
            if i % 500 == 0:
                logger.info(f"Processed {i}/{len(activity_detail_metrics)} data points")

        logger.info(f"Extracted {len(processed_points)} valid data points with metrics")
        return processed_points

    except Exception as e:
        logger.error(f"Error processing JSON file: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    try:
        client = connect_to_garmin()
        conn, cursor = connect_to_database()
        print("Cursor connected")

        # Target this specific activity ID
        target_activity_id = 18698089374
        logger.info(f"Focusing on specific activity ID: {target_activity_id}")

        # Try to fetch the activity directly from Garmin
        activity = None
        try:
            activity = client.get_activity(target_activity_id)
        except Exception as e:
            logger.warning(f"Could not get activity directly by ID: {e}")
            # Fallback: search in the recent activities
            try:
                activities = client.get_activities(0, 20)
                for act in activities:
                    if act.get("activityId") == target_activity_id:
                        activity = act
                        break
            except Exception as e2:
                logger.error(f"Could not retrieve activity from recent list: {e2}")

        # If still no activity found, create a placeholder
        if not activity:
            logger.warning("Could not retrieve activity details. Creating placeholder.")
            activity = {
                "activityId": target_activity_id,
                "activityName": "Unknown Activity",
                "activityType": {"typeKey": "Unknown"},
                "startTimeLocal": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "duration": 0,
                "distance": 0
            }

        # Print basic info
        print("\n=== ACTIVITY SUMMARY ===")
        activity_name = activity.get("activityName", "Unknown Activity")
        activity_type = activity.get("activityType", {}).get("typeKey", "Unknown")
        start_time = activity.get("startTimeLocal", "Unknown")
        duration = activity.get("duration", 0)
        distance = activity.get("distance", 0)
        print(f"Name: {activity_name}")
        print(f"Type: {activity_type}")
        print(f"Date: {start_time}")
        print(f"Duration: {duration / 60:.2f} minutes")
        print(f"Distance: {distance / 1000:.2f} km")

        # Parse activity for workout table
        parsed = parse_activity(activity)

        # Check if a matching workout already exists
        existing = check_existing_workout(cursor, parsed["user_id"], parsed["start_time"])
        if existing:
            workout_id = existing[0]
            logger.info(f"Workout already exists in database with ID: {workout_id}")
        else:
            workout_id = insert_workout(cursor, parsed)
            logger.info(f"Inserted new workout with ID: {workout_id}")

        # Fetch detailed metrics from Garmin
        logger.info(f"Fetching detailed metrics for activity ID: {target_activity_id}")
        detailed_metrics = get_detailed_workout_metrics(client, target_activity_id)

        # Process the metric points
        logger.info("Processing metric points from detailed activity data...")
        metric_points = process_metric_points(detailed_metrics)

        # If no metric points were processed, try parsing the saved JSON file instead
        if not metric_points:
            logger.info("No metrics processed directly. Attempting to process from saved JSON...")
            json_file_path = f"activity_{target_activity_id}_details.json"

            if os.path.exists(json_file_path):
                # Here is where we call the new function
                metric_points = process_metrics_from_json_file(json_file_path, workout_id)
            else:
                logger.warning(f"JSON file {json_file_path} not found")

        # Show a sample of what we got
        if metric_points:
            print("\n=== PROCESSED METRICS SAMPLE ===")
            print(f"Total data points: {len(metric_points)}")

            if len(metric_points) >= 3:
                first_point = metric_points[0]
                last_point = metric_points[-1]
                middle_point = metric_points[len(metric_points) // 2]

                print(f"First point ({first_point['timestamp']}): {first_point}")
                print(f"Middle point ({middle_point['timestamp']}): {middle_point}")
                print(f"Last point ({last_point['timestamp']}): {last_point}")
            else:
                for i, point in enumerate(metric_points):
                    print(f"Point {i + 1} ({point['timestamp']}): {point}")

            # Show metrics availability
            metrics_count = {
                "heart_rate": sum(1 for p in metric_points if "heart_rate" in p),
                "pace": sum(1 for p in metric_points if "pace" in p),
                "cadence": sum(1 for p in metric_points if "cadence" in p),
                "power": sum(1 for p in metric_points if "power" in p),
                "altitude": sum(1 for p in metric_points if "altitude" in p),
                "vertical_oscillation": sum(1 for p in metric_points if "vertical_oscillation" in p),
                "ground_contact_time": sum(1 for p in metric_points if "ground_contact_time" in p),
                "vertical_ratio": sum(1 for p in metric_points if "vertical_ratio" in p),
                "stride_length": sum(1 for p in metric_points if "stride_length" in p),
                "temperature": sum(1 for p in metric_points if "temperature" in p)
            }

            print("\nMetrics availability:")
            for metric, count in metrics_count.items():
                percentage = (count / len(metric_points)) * 100
                print(f"  {metric}: {count} points ({percentage:.1f}%)")

            # Clear any existing metrics for this workout
            try:
                cursor.execute("DELETE FROM WorkoutMetrics WHERE WorkoutID = ?", (workout_id,))
                logger.info(f"Deleted existing metrics for workout ID {workout_id}")
            except Exception as e:
                logger.warning(f"Error deleting existing metrics: {e}")

            # Prepare insertion
            values = []
            for point in metric_points:
                if "timestamp" not in point:
                    continue

                # Extract each field or set default
                timestamp = point.get("timestamp")
                heart_rate = point.get("heart_rate")
                pace = point.get("pace")
                cadence = point.get("cadence")
                vertical_oscillation = point.get("vertical_oscillation")
                vertical_ratio = point.get("vertical_ratio")
                ground_contact_time = point.get("ground_contact_time")
                power = point.get("power")
                altitude = point.get("altitude")
                temperature = point.get("temperature")
                stride_length = point.get("stride_length")

                values.append((
                    workout_id, timestamp, heart_rate, pace, cadence,
                    vertical_oscillation, vertical_ratio, ground_contact_time,
                    power, altitude, temperature, stride_length
                ))

            logger.info(f"Inserting {len(values)} metric points for workout ID {workout_id}...")
            rows_inserted = 0
            batch_size = 1000

            try:
                for i in range(0, len(values), batch_size):
                    batch = values[i:i + batch_size]
                    try:
                        cursor.executemany(
                            """
                            INSERT INTO WorkoutMetrics (
                                WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence,
                                VerticalOscillation, VerticalRatio, GroundContactTime,
                                Power, Altitude, Temperature, StrideLength
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            batch
                        )
                        rows_inserted += len(batch)
                        logger.info(f"Inserted batch of {len(batch)} metrics (total: {rows_inserted})")
                    except Exception as e:
                        logger.error(f"Error inserting batch: {e}")
                        # Insert individually to identify problem records
                        for j, record in enumerate(batch):
                            try:
                                cursor.execute(
                                    """
                                    INSERT INTO WorkoutMetrics (
                                        WorkoutID, MetricTimestamp, HeartRate, Pace, Cadence,
                                        VerticalOscillation, VerticalRatio, GroundContactTime,
                                        Power, Altitude, Temperature, StrideLength
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    record
                                )
                                rows_inserted += 1
                                if j % 100 == 0:
                                    logger.info(f"Inserted {j} individual records in current batch")
                            except Exception as e2:
                                logger.error(f"Error inserting record {i + j}: {e2}")

                # Commit
                conn.commit()
                print(f"\nSuccessfully inserted {rows_inserted} metric points into WorkoutMetrics table")
                logger.info(f"Successfully inserted {rows_inserted} metric points into WorkoutMetrics table")
                logger.info("Database changes committed successfully")
            except Exception as e:
                logger.error(f"Error in batch insertion: {e}")
                conn.rollback()
                logger.error("Transaction rolled back due to error")
        else:
            logger.warning("No metric points were processed from the detailed data")
            print("\n=== ACTIVITY DETAILS STRUCTURE ===")
            activity_details = detailed_metrics.get("activityDetails", {})
            print("Top level keys in activityDetails:")
            for key in activity_details.keys():
                print(f"  - {key}")
            for key, value in activity_details.items():
                if isinstance(value, list) and len(value) > 0:
                    print(f"\nFound array in '{key}' with {len(value)} items")
                    if len(value) > 0 and isinstance(value[0], dict):
                        print(f"Sample item: {value[0]}")
                        print(f"Keys in sample item: {', '.join(value[0].keys())}")

        # Close connections
        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        logger.error(f"Error in workout data collection: {e}")
        import traceback
        traceback.print_exc()
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
