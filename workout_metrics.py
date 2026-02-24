from datetime import datetime

import garminconnect
import pyodbc

from config import GARMIN_EMAIL, GARMIN_PASSWORD

# Maps Garmin metric descriptor keys to WorkoutMetrics column names.
# directDoubleCadence is the full steps/min figure; directCadence is half-cadence
# (strides/min). The script prefers directDoubleCadence when available.
GARMIN_KEY_TO_COLUMN = {
    "directHeartRate":           "HeartRate",
    "directSpeed":               "Pace",               # converted m/s → min/km
    "directDoubleCadence":       "Cadence",
    "directCadence":             "Cadence",
    "directVerticalOscillation": "VerticalOscillation",
    "directVerticalRatio":       "VerticalRatio",
    "directGroundContactTime":   "GroundContactTime",
    "directPower":               "Power",
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
            continue  # skip half-cadence when full cadence is available

        if key not in GARMIN_KEY_TO_COLUMN:
            continue

        col_name = GARMIN_KEY_TO_COLUMN[key]

        if col_name == "HeartRate":
            transform = lambda v: int(v) if v is not None else None
        elif col_name == "Pace":
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

    # 2) Connect to DB and find the matching WorkoutID
    conn = pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=localhost;"
        "Database=QuantifiedStridesDB;"
        "Trusted_Connection=yes;"
    )
    cursor = conn.cursor()

    # Match by exact start time first, fall back to date only
    cursor.execute(
        "SELECT WorkoutID FROM Workouts WHERE StartTime = ?",
        (start_time_dt,)
    )
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "SELECT WorkoutID FROM Workouts WHERE WorkoutDate = ? AND WorkoutType != 'Environmental Data Collection'",
            (workout_date,)
        )
        row = cursor.fetchone()

    if not row:
        print(f"No matching workout in DB for {workout_date}. Run workout.py first.")
        conn.close()
        return

    workout_id = row[0]
    print(f"Matched WorkoutID: {workout_id}")

    # 3) Skip if metrics already exist for this workout
    cursor.execute(
        "SELECT COUNT(*) FROM WorkoutMetrics WHERE WorkoutID = ?",
        (workout_id,)
    )
    if cursor.fetchone()[0] > 0:
        print(f"WorkoutMetrics already populated for WorkoutID {workout_id}. Skipping.")
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

    # Find the timestamp descriptor index
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

    # 5) Insert each data point
    sql_insert = """
    INSERT INTO WorkoutMetrics (
        WorkoutID,
        MetricTimestamp,
        HeartRate,
        Pace,
        Cadence,
        VerticalOscillation,
        VerticalRatio,
        GroundContactTime,
        Power
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    rows_inserted = 0
    for point in data_points:
        metrics = point.get("metrics", [])

        if timestamp_index >= len(metrics) or metrics[timestamp_index] is None:
            continue

        # Garmin timestamps are milliseconds since Unix epoch
        metric_timestamp = datetime.fromtimestamp(metrics[timestamp_index] / 1000)

        values = {
            "HeartRate": None,
            "Pace": None,
            "Cadence": None,
            "VerticalOscillation": None,
            "VerticalRatio": None,
            "GroundContactTime": None,
            "Power": None,
        }

        for idx, (col_name, transform) in col_map.items():
            if idx < len(metrics) and metrics[idx] is not None:
                values[col_name] = transform(metrics[idx])

        cursor.execute(sql_insert, (
            workout_id,
            metric_timestamp,
            values["HeartRate"],
            values["Pace"],
            values["Cadence"],
            values["VerticalOscillation"],
            values["VerticalRatio"],
            values["GroundContactTime"],
            values["Power"],
        ))
        rows_inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Inserted {rows_inserted} metric records for WorkoutID {workout_id}.")


if __name__ == "__main__":
    main()
