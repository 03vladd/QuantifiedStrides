"""
QuantifiedStrides Workout Data Collection v2.0
Handles Garmin's dynamic metric structure with dual storage
"""

from datetime import datetime, timedelta
import garminconnect
import pyodbc
import json
import hashlib
import logging
import sys
import config
from workout_data_archiver import WorkoutArchiver

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("workout_v2")


class GarminMetricsParser:
    """Parse Garmin's dynamic metric structure"""

    # Mapping from Garmin metric keys to our database columns
    METRIC_MAPPING = {
        'directHeartRate': 'HeartRate',
        'directSpeed': 'Speed',
        'directPower': 'Power',
        'directFractionalCadence': 'Cadence',
        'directRunCadence': 'Cadence',
        'directDoubleCadence': 'Cadence',
        'directElevation': 'Elevation',
        'directLatitude': 'Latitude',
        'directLongitude': 'Longitude',
        'sumDistance': 'Distance',
        'directVerticalOscillation': 'VerticalOscillation',
        'directVerticalRatio': 'VerticalRatio',
        'directGroundContactTime': 'GroundContactTime',
        'directStrideLength': 'StrideLength',
        'directBodyBattery': 'BodyBattery',
        'directPerformanceCondition': 'PerformanceCondition',
        'directTimestamp': 'TimestampGMT',
        'sumElapsedDuration': 'ElapsedSeconds'
    }

    def __init__(self, metric_descriptors):
        """
        Initialize parser with metric descriptors

        Args:
            metric_descriptors: List of descriptor dicts from Garmin API
        """
        self.descriptors = {}
        for desc in metric_descriptors:
            index = desc.get('metricsIndex')
            key = desc.get('key')
            unit = desc.get('unit', {})

            self.descriptors[index] = {
                'key': key,
                'unit_id': unit.get('id'),
                'unit_key': unit.get('key'),
                'factor': unit.get('factor', 1.0),
                'db_column': self.METRIC_MAPPING.get(key)
            }

    def parse_metric_point(self, metrics_array):
        """
        Parse a single time point's metrics

        Args:
            metrics_array: Array of metric values from Garmin

        Returns:
            Dictionary with parsed metrics
        """
        parsed = {}

        for index, value in enumerate(metrics_array):
            if value is None:
                continue

            descriptor = self.descriptors.get(index)
            if not descriptor:
                continue

            key = descriptor['key']
            db_column = descriptor['db_column']
            factor = descriptor['factor']

            # Apply unit factor if needed
            if factor and factor != 0:
                adjusted_value = value / factor
            else:
                adjusted_value = value

            # Store both raw key and mapped DB column name
            parsed[key] = adjusted_value
            if db_column:
                parsed[db_column] = adjusted_value

        return parsed


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


def check_existing_workout(cursor, user_id, activity_id):
    """Check if a workout already exists"""
    try:
        cursor.execute(
            "SELECT WorkoutID FROM Workouts_v2 WHERE UserID = ? AND ActivityID = ?",
            (user_id, activity_id)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error checking for existing workout: {e}")
        return None


def is_indoor_workout(sport_type, workout_name=""):
    """Determine if a workout is indoor"""
    if not sport_type and not workout_name:
        return False

    sport_str = str(sport_type).lower() if sport_type else ""
    name_str = str(workout_name).lower() if workout_name else ""

    for keyword in config.INDOOR_KEYWORDS:
        if keyword.lower() in sport_str or keyword.lower() in name_str:
            return True

    return False


def insert_workout_summary(cursor, activity):
    """Insert workout summary into Workouts_v2 table"""
    user_id = config.DEFAULT_USER_ID
    activity_id = activity.get("activityId")

    # Extract sport type
    sport = None
    if "activityType" in activity:
        activity_type = activity.get("activityType", {})
        if isinstance(activity_type, dict):
            sport = activity_type.get("typeKey", "Unknown")
    if not sport:
        sport = activity.get("activityType", "Unknown")

    workout_type = activity.get("activityName", "Unknown")
    location = activity.get("locationName", "Unknown")
    is_indoor = is_indoor_workout(sport, workout_type)

    # Parse start time
    start_time_str = activity.get("startTimeLocal", "")
    start_time_dt = None
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ"
    ]
    for fmt in formats:
        try:
            start_time_dt = datetime.strptime(start_time_str, fmt)
            break
        except ValueError:
            continue

    if not start_time_dt:
        start_time_dt = datetime.now()

    workout_date = start_time_dt.date()
    duration_seconds = int(activity.get("duration", 0))
    end_time_dt = start_time_dt + timedelta(seconds=duration_seconds)

    # Extract metrics
    distance_meters = activity.get("distance", 0)
    calories = int(activity.get("calories", 0))
    avg_hr = int(activity.get("averageHR", 0)) if activity.get("averageHR") else None
    max_hr = int(activity.get("maxHR", 0)) if activity.get("maxHR") else None
    vo2max = activity.get("vO2MaxValue")
    lactate = activity.get("lactateThresholdBpm")
    training_effect = activity.get("aerobicTrainingEffect")
    anaerobic_effect = activity.get("anaerobicTrainingEffect")

    # HR Zones
    hr_zones = [
        activity.get("hrTimeInZone_1", 0),
        activity.get("hrTimeInZone_2", 0),
        activity.get("hrTimeInZone_3", 0),
        activity.get("hrTimeInZone_4", 0),
        activity.get("hrTimeInZone_5", 0)
    ]

    # Running metrics
    avg_cadence = activity.get("averageRunningCadenceInStepsPerMinute")
    max_cadence = activity.get("maxRunningCadenceInStepsPerMinute")
    avg_vo = activity.get("avgVerticalOscillation")
    avg_gct = activity.get("avgGroundContactTime")
    avg_stride = activity.get("avgStrideLength")
    avg_vr = activity.get("avgVerticalRatio")

    # Cycling metrics
    avg_power = activity.get("avgPower")
    max_power = activity.get("maxPower")
    norm_power = activity.get("normalizedPower")

    try:
        sql = """
        INSERT INTO Workouts_v2 (
            UserID, ActivityID, Sport, WorkoutType, WorkoutDate,
            StartTime, EndTime, Location, IsIndoor,
            DurationSeconds, DistanceMeters, CaloriesBurned,
            AvgHeartRate, MaxHeartRate, VO2MaxEstimate, LactateThresholdBpm,
            TrainingEffect, AnaerobicTrainingEffect,
            TimeInHRZone1, TimeInHRZone2, TimeInHRZone3, TimeInHRZone4, TimeInHRZone5,
            AvgRunningCadence, MaxRunningCadence, AvgVerticalOscillation,
            AvgGroundContactTime, AvgStrideLength, AvgVerticalRatio,
            AvgPower, MaxPower, NormalizedPower
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(sql, (
            user_id, activity_id, sport, workout_type, workout_date,
            start_time_dt, end_time_dt, location, is_indoor,
            duration_seconds, distance_meters, calories,
            avg_hr, max_hr, vo2max, lactate,
            training_effect, anaerobic_effect,
            hr_zones[0], hr_zones[1], hr_zones[2], hr_zones[3], hr_zones[4],
            avg_cadence, max_cadence, avg_vo,
            avg_gct, avg_stride, avg_vr,
            avg_power, max_power, norm_power
        ))

        cursor.execute("SELECT @@IDENTITY")
        workout_id = cursor.fetchone()[0]
        return workout_id

    except Exception as e:
        logger.error(f"Error inserting workout summary: {e}")
        return None


def insert_metric_descriptors(cursor, workout_id, descriptors):
    """Insert metric descriptors into cache table"""
    try:
        values = []
        for desc in descriptors:
            index = desc.get('metricsIndex')
            key = desc.get('key')
            unit = desc.get('unit', {})

            values.append((
                workout_id,
                index,
                key,
                unit.get('key'),
                unit.get('factor', 1.0)
            ))

        cursor.executemany("""
            INSERT INTO MetricDescriptorCache 
            (WorkoutID, MetricIndex, MetricKey, MetricUnit, UnitFactor)
            VALUES (?, ?, ?, ?, ?)
        """, values)

        return len(values)
    except Exception as e:
        logger.error(f"Error inserting metric descriptors: {e}")
        return 0


def insert_metrics_time_series(cursor, workout_id, parser, metrics_data):
    """Insert parsed time-series metrics"""
    try:
        values = []

        for metric_point in metrics_data:
            metrics_array = metric_point.get('metrics', [])
            parsed = parser.parse_metric_point(metrics_array)

            if not parsed:
                continue

            # Extract values with None as default
            values.append((
                workout_id,
                parsed.get('TimestampGMT'),
                parsed.get('ElapsedSeconds'),
                parsed.get('Latitude'),
                parsed.get('Longitude'),
                parsed.get('Elevation'),
                parsed.get('HeartRate'),
                parsed.get('Speed'),
                parsed.get('Distance'),
                parsed.get('Cadence'),
                parsed.get('VerticalOscillation'),
                parsed.get('VerticalRatio'),
                parsed.get('GroundContactTime'),
                parsed.get('StrideLength'),
                parsed.get('Power'),
                parsed.get('BodyBattery'),
                parsed.get('PerformanceCondition')
            ))

        if not values:
            logger.warning(f"No metric values to insert for workout {workout_id}")
            return 0

        # Batch insert
        batch_size = 1000
        rows_inserted = 0

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO WorkoutMetrics_v2 (
                    WorkoutID, TimestampGMT, ElapsedSeconds,
                    Latitude, Longitude, Elevation,
                    HeartRate, Speed, Distance,
                    Cadence, VerticalOscillation, VerticalRatio,
                    GroundContactTime, StrideLength, Power,
                    BodyBattery, PerformanceCondition
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)

        return rows_inserted

    except Exception as e:
        logger.error(f"Error inserting time-series metrics: {e}")
        return 0


def insert_raw_metrics(cursor, workout_id, activity_details):
    """Store complete raw metrics as JSON"""
    try:
        descriptors = activity_details.get('metricDescriptors', [])
        metrics_data = activity_details.get('activityDetailMetrics', [])

        descriptors_json = json.dumps(descriptors)
        metrics_json = json.dumps(metrics_data)

        # Calculate checksum
        checksum = hashlib.md5((descriptors_json + metrics_json).encode()).hexdigest()

        cursor.execute("""
            INSERT INTO WorkoutMetricsRaw 
            (WorkoutID, MetricDescriptors, MetricsData, TotalPoints, DataChecksum)
            VALUES (?, ?, ?, ?, ?)
        """, (workout_id, descriptors_json, metrics_json, len(metrics_data), checksum))

        return True

    except Exception as e:
        logger.error(f"Error inserting raw metrics: {e}")
        return False


def process_activity_complete(client, cursor, activity, archiver):
    """Process complete activity with all metrics"""
    activity_id = activity.get("activityId")

    if not activity_id:
        logger.warning("Activity missing activityId")
        return None

    # Check if already exists
    existing = check_existing_workout(cursor, config.DEFAULT_USER_ID, activity_id)
    if existing:
        logger.info(f"Activity {activity_id} already in database")
        return existing[0]

    # Step 1: Archive to JSON (data lake)
    logger.info(f"[DATA LAKE] Archiving activity {activity_id}")
    archiver.archive_activity_complete(client, activity)

    # Step 2: Insert summary
    logger.info(f"[DATABASE] Inserting summary for activity {activity_id}")
    workout_id = insert_workout_summary(cursor, activity)

    if not workout_id:
        logger.error(f"Failed to insert workout summary for {activity_id}")
        return None

    # Step 3: Get detailed metrics from Garmin
    try:
        logger.info(f"Fetching detailed metrics for activity {activity_id}")
        activity_details = client.get_activity_details(activity_id)

        if not activity_details or 'activityDetails' not in activity_details:
            logger.warning(f"No detailed metrics available for {activity_id}")
            return workout_id

        details = activity_details.get('activityDetails', {})
        descriptors = details.get('metricDescriptors', [])
        metrics_data = details.get('activityDetailMetrics', [])

        if not descriptors or not metrics_data:
            logger.warning(f"Empty metrics data for {activity_id}")
            return workout_id

        # Step 4: Store metric descriptors
        desc_count = insert_metric_descriptors(cursor, workout_id, descriptors)
        logger.info(f"Inserted {desc_count} metric descriptors")

        # Step 5: Parse and store time-series metrics
        parser = GarminMetricsParser(descriptors)
        metrics_count = insert_metrics_time_series(cursor, workout_id, parser, metrics_data)
        logger.info(f"Inserted {metrics_count} time-series metric points")

        # Step 6: Store raw JSON
        if insert_raw_metrics(cursor, workout_id, details):
            logger.info(f"Stored raw metrics JSON")

    except Exception as e:
        logger.error(f"Error processing detailed metrics for {activity_id}: {e}")

    return workout_id


def main():
    """Main function"""
    try:
        # Initialize
        archiver = WorkoutArchiver()
        client = connect_to_garmin()
        conn, cursor = connect_to_database()

        logger.info("Fetching recent activities...")
        activities = client.get_activities(0, 10)

        if not activities:
            logger.info("No activities found")
            return 0

        stats = {'processed': 0, 'inserted': 0, 'skipped': 0, 'errors': 0}

        for activity in activities:
            try:
                workout_id = process_activity_complete(client, cursor, activity, archiver)

                if workout_id:
                    conn.commit()
                    stats['processed'] += 1
                    stats['inserted'] += 1
                    logger.info(f"✓ Successfully processed activity {activity.get('activityId')}")
                else:
                    stats['skipped'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing activity: {e}")
                conn.rollback()

        cursor.close()
        conn.close()

        print(f"\n{'=' * 60}")
        print(f"Processing Complete")
        print(f"{'=' * 60}")
        print(f"Processed: {stats['processed']}")
        print(f"Inserted:  {stats['inserted']}")
        print(f"Skipped:   {stats['skipped']}")
        print(f"Errors:    {stats['errors']}")
        print(f"{'=' * 60}")

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())