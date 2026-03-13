from datetime import datetime

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

# Maps Garmin metric descriptor keys to workout_metrics column names.
# directDoubleCadence is the full steps/min figure; directCadence is half-cadence.
# The script prefers directDoubleCadence when available.
GARMIN_KEY_TO_COLUMN = {
    "directHeartRate":           "heart_rate",
    "directSpeed":               "pace",               # converted m/s → min/km
    "directDoubleCadence":       "cadence",
    "directCadence":             "cadence",
    "directVerticalOscillation": "vertical_oscillation",
    "directVerticalRatio":       "vertical_ratio",
    "directGroundContactTime":   "ground_contact_time",
    "directPower":               "power",
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


def main():
    # 1) Connect to Garmin and fetch the latest activity
    client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    client.login()

    activities = client.get_activities(0, 1)
    if not activities:
        print("No activities found on Garmin Connect.")
        return

    activity = activities[0]
    activity_id = activity["activityId"]
    activity_name = activity.get("activityName", "Unknown")
    start_time_str = activity.get("startTimeLocal", "")

    print(f"Activity: {activity_name} (ID: {activity_id})")

    try:
        start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

    workout_date = start_time_dt.date()

    # 2) Connect to DB and find the matching workout_id
    conn = get_connection()
    cursor = conn.cursor()

    # Match by exact start time first, fall back to date
    cursor.execute(
        "SELECT workout_id FROM workouts WHERE start_time = %s",
        (start_time_dt,)
    )
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "SELECT workout_id FROM workouts WHERE workout_date = %s AND user_id = 1",
            (workout_date,)
        )
        row = cursor.fetchone()

    if not row:
        print(f"No matching workout in DB for {workout_date}. Run workout.py first.")
        conn.close()
        return

    workout_id = row[0]
    print(f"Matched workout_id: {workout_id}")

    # 3) Skip if metrics already exist for this workout
    cursor.execute(
        "SELECT COUNT(*) FROM workout_metrics WHERE workout_id = %s",
        (workout_id,)
    )
    if cursor.fetchone()[0] > 0:
        print(f"workout_metrics already populated for workout_id {workout_id}. Skipping.")
        conn.close()
        return

    # 4) Download time-series details from Garmin
    print("Downloading activity details...")
    details = client.get_activity_details(activity_id, maxchart=2000)

    descriptors = details.get("metricDescriptors", [])
    data_points = details.get("activityDetailMetrics", [])

    if not descriptors or not data_points:
        print("No time-series data in activity details.")
        conn.close()
        return

    timestamp_index = next(
        (d["metricsIndex"] for d in descriptors if d["key"] == "directTimestamp"),
        None
    )
    if timestamp_index is None:
        print("No directTimestamp found in metricDescriptors.")
        conn.close()
        return

    col_map = build_column_map(descriptors)
    print(f"Mapped columns: {sorted(set(col for col, _ in col_map.values()))}")

    sql_insert = """
    INSERT INTO workout_metrics (
        workout_id,
        metric_timestamp,
        heart_rate,
        pace,
        cadence,
        vertical_oscillation,
        vertical_ratio,
        ground_contact_time,
        power
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    rows_inserted = 0
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
        }

        for idx, (col_name, transform) in col_map.items():
            if idx < len(metrics) and metrics[idx] is not None:
                values[col_name] = transform(metrics[idx])

        cursor.execute(sql_insert, (
            workout_id,
            metric_timestamp,
            values["heart_rate"],
            values["pace"],
            values["cadence"],
            values["vertical_oscillation"],
            values["vertical_ratio"],
            values["ground_contact_time"],
            values["power"],
        ))
        rows_inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Inserted {rows_inserted} metric records for workout_id {workout_id}.")


if __name__ == "__main__":
    main()
