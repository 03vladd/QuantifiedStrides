from datetime import datetime, timedelta

import garminconnect
import pyodbc
import json

# 1) Connect to Garmin
client = garminconnect.Garmin("vasiuvlad984@gmail.com", "Mariguanas1")
client.login()

# 2) Get recent activities
activities = client.get_activities(0, 1)  # from index 0, 1 activity

'''print(json.dumps(activities, indent=4))'''

# 3) Connect to SQL Server
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=QuantifiedStridesDB;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
print("Cursor connected")

sql_insert = """
INSERT INTO Workouts (
      UserID
    , Sport
    , StartTime
    , EndTime
    , WorkoutType
    , CaloriesBurned
    , AvgHeartRate
    , MaxHeartRate
    , VO2MaxEstimate
    , LactateThresholdBpm
    , TimeInHRZone1
    , TimeInHRZone2
    , TimeInHRZone3
    , TimeInHRZone4
    , TimeInHRZone5
    , TrainingVolume
    , AvgVerticalOscillation
    , AvgGroundContactTime
    , AvgStrideLength
    , AvgVerticalRatio
    , AverageRunningCadence
    , MaxRunningCadence
    , Location
    , WorkoutDate
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# 4) Loop through each activity and parse/insert data
for activity in activities:
    # --- BASIC FIELDS ---
    # Primary user ID (assuming 1 for yourself)
    user_id = 1

    sport = activity.get("activityType", {}).get("typeKey", "Unknown")  # e.g. "run", "cycling"
    workout_type = activity.get("activityName", "Unknown")  # or "activityName"

    # Start time: parse the "startTimeLocal" field ("YYYY-MM-DDTHH:MM:SS")
    start_time_str = activity.get("startTimeLocal", None)
    if start_time_str:
        # Try parsing with 'T', then fallback to space-based.
        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    else:
        start_time_dt = datetime.now()  # or some fallback

    # Extract the date portion for the new WorkoutDate column
    workout_date = start_time_dt.date()

    # Duration in seconds (for deriving EndTime)
    duration_seconds = activity.get("duration", 0.0)

    # EndTime: if Garmin provided duration, we add to StartTime
    end_time_dt = start_time_dt + timedelta(seconds=float(duration_seconds))

    # Calories, HR, etc.
    calories_burned = activity.get("calories", 0)
    avg_heart_rate = activity.get("averageHR", 0)
    max_heart_rate = activity.get("maxHR", 0)

    # --- ADVANCED METRICS ---
    vo2max = activity.get("vO2MaxValue", None)
    lactate_threshold = activity.get("lactateThresholdBpm", None)

    time_in_zone_1 = activity.get("hrTimeInZone_1", 0.0)
    time_in_zone_2 = activity.get("hrTimeInZone_2", 0.0)
    time_in_zone_3 = activity.get("hrTimeInZone_3", 0.0)
    time_in_zone_4 = activity.get("hrTimeInZone_4", 0.0)
    time_in_zone_5 = activity.get("hrTimeInZone_5", 0.0)

    # TrainingVolume can be distance or TSS.
    # The 'distance' field in Garmin is usually in meters:
    training_volume = activity.get("distance", 0.0)

    avg_vertical_osc = activity.get("avgVerticalOscillation", None)
    avg_ground_contact = activity.get("avgGroundContactTime", None)
    avg_stride_length = activity.get("avgStrideLength", None)
    avg_vertical_ratio = activity.get("avgVerticalRatio", None)
    avg_running_cadence = activity.get("averageRunningCadenceInStepsPerMinute", None)
    max_running_cadence = activity.get("maxRunningCadenceInStepsPerMinute", None)

    # Some activities might include "locationName" or similar
    location = activity.get("locationName", "Unknown")

    # 5) Execute the insertion
    cursor.execute(
        sql_insert,
        (
            user_id,
            sport,
            start_time_dt,
            end_time_dt,
            workout_type,
            calories_burned,
            avg_heart_rate,
            max_heart_rate,
            vo2max,
            lactate_threshold,
            time_in_zone_1,
            time_in_zone_2,
            time_in_zone_3,
            time_in_zone_4,
            time_in_zone_5,
            training_volume,
            avg_vertical_osc,
            avg_ground_contact,
            avg_stride_length,
            avg_vertical_ratio,
            avg_running_cadence,
            max_running_cadence,
            location,
            workout_date  # New date column
        )
    )

    # 6) After saving workout, get the latest workoutID to link with environment data
    cursor.execute("SELECT SCOPE_IDENTITY()")
    workout_id = cursor.fetchone()[0]
    print(f"Workout saved with ID: {workout_id} for date: {workout_date}")

conn.commit()
cursor.close()
conn.close()
print("All activities inserted successfully!")