"""
backfill_workout_metrics.py

Backfills workout_metrics time-series data for all matching activities
over the last N days (default 730 = 2 years).

Usage:
    python backfill_workout_metrics.py
    python backfill_workout_metrics.py --days 365
    python backfill_workout_metrics.py --sport running
"""

import argparse
import time
from datetime import datetime, timedelta

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

# Sports to include by default
SUPPORTED_SPORTS = {
    "running",
    "trail_running",
    "cycling",
    "mountain_biking",
    "indoor_cycling",
}

# Maps Garmin metric descriptor keys to workout_metrics column names.
GARMIN_KEY_TO_COLUMN = {
    "directHeartRate":           "heart_rate",
    "directSpeed":               "pace",               # converted m/s → min/km
    "directDoubleCadence":       "cadence",
    "directCadence":             "cadence",
    "directVerticalOscillation": "vertical_oscillation",
    "directVerticalRatio":       "vertical_ratio",
    "directGroundContactTime":   "ground_contact_time",
    "directPower":               "power",
    "directLatitude":            "latitude",
    "directLongitude":           "longitude",
    "directAltitude":            "altitude",
    "directElevation":           "altitude",           # some devices use this key
    "directDistance":            "distance",
}


def speed_to_pace(speed_ms):
    """Convert m/s to min/km. Returns None for zero/null speed."""
    if not speed_ms:
        return None
    return (1000 / speed_ms) / 60


def build_column_map(descriptors):
    """
    Return a dict of {metricsIndex: (column_name, transform_fn)} from the
    activity's metricDescriptors list.

    When both directCadence and directDoubleCadence are present, only
    directDoubleCadence is mapped (it's the full steps/min value).
    """
    has_double_cadence = any(d["key"] == "directDoubleCadence" for d in descriptors)

    col_map = {}
    for d in descriptors:
        key = d["key"]
        idx = d["metricsIndex"]

        if key == "directCadence" and has_double_cadence:
            continue

        if key not in GARMIN_KEY_TO_COLUMN:
            continue

        col_name = GARMIN_KEY_TO_COLUMN[key]

        if col_name == "heart_rate":
            transform = lambda v: int(v) if v is not None else None
        elif col_name == "pace":
            transform = speed_to_pace
        else:
            transform = lambda v: float(v) if v is not None else None

        col_map[idx] = (col_name, transform)

    return col_map


def extract_workout_fields(activity):
    """Extract all summary fields from a Garmin activity dict."""
    from datetime import timedelta

    start_time_str = activity.get("startTimeLocal", None)
    if start_time_str:
        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    else:
        return None

    duration_seconds = activity.get("duration", 0.0)
    end_time_dt = start_time_dt + timedelta(seconds=float(duration_seconds))
    workout_date = start_time_dt.date()

    return dict(
        user_id=1,
        sport=activity.get("activityType", {}).get("typeKey", "Unknown"),
        start_time=start_time_dt,
        end_time=end_time_dt,
        workout_type=activity.get("activityName", "Unknown"),
        calories_burned=activity.get("calories", 0),
        avg_heart_rate=activity.get("averageHR", 0),
        max_heart_rate=activity.get("maxHR", 0),
        vo2max=activity.get("vO2MaxValue", None),
        lactate_threshold=activity.get("lactateThresholdBpm", None),
        time_in_zone_1=activity.get("hrTimeInZone_1", 0.0),
        time_in_zone_2=activity.get("hrTimeInZone_2", 0.0),
        time_in_zone_3=activity.get("hrTimeInZone_3", 0.0),
        time_in_zone_4=activity.get("hrTimeInZone_4", 0.0),
        time_in_zone_5=activity.get("hrTimeInZone_5", 0.0),
        training_volume=activity.get("distance", 0.0),
        avg_vertical_osc=activity.get("avgVerticalOscillation", None),
        avg_ground_contact=activity.get("avgGroundContactTime", None),
        avg_stride_length=activity.get("avgStrideLength", None),
        avg_vertical_ratio=activity.get("avgVerticalRatio", None),
        avg_running_cadence=activity.get("averageRunningCadenceInStepsPerMinute", None),
        max_running_cadence=activity.get("maxRunningCadenceInStepsPerMinute", None),
        location=activity.get("locationName", "Unknown"),
        start_latitude=activity.get("startLatitude"),
        start_longitude=activity.get("startLongitude"),
        workout_date=workout_date,
        elevation_gain=activity.get("elevationGain", None),
        elevation_loss=activity.get("elevationLoss", None),
        aerobic_training_effect=activity.get("aerobicTrainingEffect", None),
        anaerobic_training_effect=activity.get("anaerobicTrainingEffect", None),
        training_stress_score=activity.get("trainingStressScore", None),
        normalized_power=activity.get("normalizedPower", None),
        avg_power=activity.get("avgPower", None),
        max_power=activity.get("maxPower", None),
        total_steps=activity.get("steps", None),
    )


SQL_INSERT_WORKOUT = """
INSERT INTO workouts (
      user_id, sport, start_time, end_time, workout_type
    , calories_burned, avg_heart_rate, max_heart_rate
    , vo2max_estimate, lactate_threshold_bpm
    , time_in_hr_zone_1, time_in_hr_zone_2, time_in_hr_zone_3
    , time_in_hr_zone_4, time_in_hr_zone_5
    , training_volume
    , avg_vertical_oscillation, avg_ground_contact_time
    , avg_stride_length, avg_vertical_ratio
    , avg_running_cadence, max_running_cadence
    , location, start_latitude, start_longitude, workout_date
    , elevation_gain, elevation_loss
    , aerobic_training_effect, anaerobic_training_effect
    , training_stress_score, normalized_power
    , avg_power, max_power, total_steps
)
VALUES (
    %(user_id)s, %(sport)s, %(start_time)s, %(end_time)s, %(workout_type)s,
    %(calories_burned)s, %(avg_heart_rate)s, %(max_heart_rate)s,
    %(vo2max)s, %(lactate_threshold)s,
    %(time_in_zone_1)s, %(time_in_zone_2)s, %(time_in_zone_3)s,
    %(time_in_zone_4)s, %(time_in_zone_5)s,
    %(training_volume)s,
    %(avg_vertical_osc)s, %(avg_ground_contact)s,
    %(avg_stride_length)s, %(avg_vertical_ratio)s,
    %(avg_running_cadence)s, %(max_running_cadence)s,
    %(location)s, %(start_latitude)s, %(start_longitude)s, %(workout_date)s,
    %(elevation_gain)s, %(elevation_loss)s,
    %(aerobic_training_effect)s, %(anaerobic_training_effect)s,
    %(training_stress_score)s, %(normalized_power)s,
    %(avg_power)s, %(max_power)s, %(total_steps)s
)
ON CONFLICT (user_id, start_time) DO UPDATE SET
      elevation_gain             = EXCLUDED.elevation_gain
    , elevation_loss             = EXCLUDED.elevation_loss
    , aerobic_training_effect    = EXCLUDED.aerobic_training_effect
    , anaerobic_training_effect  = EXCLUDED.anaerobic_training_effect
    , training_stress_score      = EXCLUDED.training_stress_score
    , normalized_power           = EXCLUDED.normalized_power
    , avg_power                  = EXCLUDED.avg_power
    , max_power                  = EXCLUDED.max_power
    , total_steps                = EXCLUDED.total_steps
RETURNING workout_id;
"""

SQL_INSERT_METRIC = """
INSERT INTO workout_metrics (
    workout_id, metric_timestamp,
    heart_rate, pace, cadence,
    vertical_oscillation, vertical_ratio, ground_contact_time, power,
    latitude, longitude, altitude, distance, gradient_pct
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING;
"""


def insert_metric_rows(cursor, workout_id, details):
    """Parse and insert time-series metric rows. Returns count of rows inserted."""
    descriptors = details.get("metricDescriptors", [])
    data_points = details.get("activityDetailMetrics", [])

    if not descriptors or not data_points:
        return 0

    timestamp_index = next(
        (d["metricsIndex"] for d in descriptors if d["key"] == "directTimestamp"),
        None,
    )
    if timestamp_index is None:
        return 0

    col_map = build_column_map(descriptors)
    rows_inserted = 0
    prev_altitude = None
    prev_distance = None

    for point in data_points:
        metrics = point.get("metrics", [])
        if timestamp_index >= len(metrics) or metrics[timestamp_index] is None:
            continue

        metric_timestamp = datetime.fromtimestamp(metrics[timestamp_index] / 1000)

        values = {
            "heart_rate": None,
            "pace": None,
            "cadence": None,
            "vertical_oscillation": None,
            "vertical_ratio": None,
            "ground_contact_time": None,
            "power": None,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "distance": None,
        }

        for idx, (col_name, transform) in col_map.items():
            if idx < len(metrics) and metrics[idx] is not None:
                values[col_name] = transform(metrics[idx])

        # gradient_pct = Δaltitude / Δhorizontal_distance × 100
        # Primary: cumulative distance; fallback: pace × Δt (1s per point)
        gradient_pct = None
        alt  = values["altitude"]
        dist = values["distance"]
        pace = values["pace"]   # min/km

        if alt is not None and prev_altitude is not None:
            d_alt = alt - prev_altitude
            d_dist = None
            if dist is not None and prev_distance is not None:
                d_dist = dist - prev_distance
            elif pace is not None and pace > 0:
                speed_ms = 1000.0 / (pace * 60.0)
                d_dist = speed_ms * 1.0   # 1-second intervals
            if d_dist is not None and d_dist > 0.5:
                gradient_pct = round(d_alt / d_dist * 100, 2)

        if alt  is not None: prev_altitude = alt
        if dist is not None: prev_distance = dist

        cursor.execute(SQL_INSERT_METRIC, (
            workout_id,
            metric_timestamp,
            values["heart_rate"],
            values["pace"],
            values["cadence"],
            values["vertical_oscillation"],
            values["vertical_ratio"],
            values["ground_contact_time"],
            values["power"],
            values["latitude"],
            values["longitude"],
            values["altitude"],
            values["distance"],
            gradient_pct,
        ))
        rows_inserted += 1

    return rows_inserted


def main():
    parser = argparse.ArgumentParser(description="Backfill workout_metrics from Garmin history.")
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="How many days back to fetch (default: 730 = 2 years)",
    )
    parser.add_argument(
        "--sport",
        type=str,
        default=None,
        help="Filter to a single sport type (e.g. running, cycling). Default: all supported sports.",
    )
    args = parser.parse_args()

    target_sports = {args.sport} if args.sport else SUPPORTED_SPORTS
    cutoff_date = datetime.now().date() - timedelta(days=args.days)

    print(f"Connecting to Garmin...")
    client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    client.login()
    print("Garmin login successful.")

    # Paginate through all activities
    all_activities = []
    start = 0
    batch_size = 100
    while True:
        batch = client.get_activities(start, batch_size)
        if not batch:
            break
        all_activities.extend(batch)
        start += batch_size
        if len(batch) < batch_size:
            break

    print(f"Fetched {len(all_activities)} total activities from Garmin.")

    # Filter by sport and date cutoff
    matching = []
    for activity in all_activities:
        sport = activity.get("activityType", {}).get("typeKey", "")
        if sport not in target_sports:
            continue
        start_time_str = activity.get("startTimeLocal", "")
        if not start_time_str:
            continue
        try:
            try:
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if start_dt.date() < cutoff_date:
            continue
        matching.append(activity)

    print(f"Filtered to {len(matching)} activities matching sports {target_sports} within last {args.days} days.")

    conn = get_connection()
    cursor = conn.cursor()

    total_processed = 0
    total_rows_inserted = 0
    total_skipped = 0

    for i, activity in enumerate(matching, start=1):
        activity_id = activity["activityId"]
        activity_name = activity.get("activityName", "Unknown")
        sport = activity.get("activityType", {}).get("typeKey", "")
        start_time_str = activity.get("startTimeLocal", "")
        try:
            try:
                start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Activity {i}/{len(matching)}: {activity_name} — skipped (bad timestamp: {e})")
            continue

        activity_date = start_time_dt.date()

        try:
            # Check if workout already in DB
            cursor.execute(
                "SELECT workout_id FROM workouts WHERE start_time = %s AND user_id = 1",
                (start_time_dt,),
            )
            row = cursor.fetchone()

            if row:
                workout_id = row[0]
            else:
                # Insert minimal workout row
                fields = extract_workout_fields(activity)
                if fields is None:
                    print(f"Activity {i}/{len(matching)}: {activity_name} {activity_date} — skipped (could not parse fields)")
                    continue
                cursor.execute(SQL_INSERT_WORKOUT, fields)
                result = cursor.fetchone()
                if result:
                    workout_id = result[0]
                else:
                    # ON CONFLICT updated but didn't return — fetch manually
                    cursor.execute(
                        "SELECT workout_id FROM workouts WHERE start_time = %s AND user_id = 1",
                        (start_time_dt,),
                    )
                    row = cursor.fetchone()
                    workout_id = row[0] if row else None

                if workout_id is None:
                    print(f"Activity {i}/{len(matching)}: {activity_name} {activity_date} — skipped (could not get workout_id)")
                    continue
                conn.commit()

            # Check if metrics already populated
            cursor.execute(
                "SELECT COUNT(*) FROM workout_metrics WHERE workout_id = %s",
                (workout_id,),
            )
            if cursor.fetchone()[0] > 0:
                print(f"Activity {i}/{len(matching)}: {activity_name} {activity_date} — skipped (already populated)")
                total_skipped += 1
                total_processed += 1
                continue

            # Download time-series details
            details = client.get_activity_details(activity_id, maxchart=2000)
            time.sleep(1.5)

            rows_inserted = insert_metric_rows(cursor, workout_id, details)
            conn.commit()

            print(f"Activity {i}/{len(matching)}: {activity_name} {activity_date} — {rows_inserted} metric rows inserted")
            total_rows_inserted += rows_inserted
            total_processed += 1

        except Exception as e:
            print(f"Activity {i}/{len(matching)}: {activity_name} {activity_date} — ERROR: {e}")
            conn.rollback()
            continue

    cursor.close()
    conn.close()

    print()
    print("=== Backfill Summary ===")
    print(f"Total activities processed : {total_processed}")
    print(f"Total metric rows inserted : {total_rows_inserted}")
    print(f"Total skipped              : {total_skipped}")


if __name__ == "__main__":
    main()
