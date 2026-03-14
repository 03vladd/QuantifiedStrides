from datetime import datetime, timedelta

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

# 1) Connect to Garmin
client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

# 2) Get most recent activity
activities = client.get_activities(0, 1)

# 3) Connect to DB
conn = get_connection()
cursor = conn.cursor()
print("Cursor connected")

sql_insert = """
INSERT INTO workouts (
      user_id
    , sport
    , start_time
    , end_time
    , workout_type
    , calories_burned
    , avg_heart_rate
    , max_heart_rate
    , vo2max_estimate
    , lactate_threshold_bpm
    , time_in_hr_zone_1
    , time_in_hr_zone_2
    , time_in_hr_zone_3
    , time_in_hr_zone_4
    , time_in_hr_zone_5
    , training_volume
    , avg_vertical_oscillation
    , avg_ground_contact_time
    , avg_stride_length
    , avg_vertical_ratio
    , avg_running_cadence
    , max_running_cadence
    , location
    , start_latitude
    , start_longitude
    , workout_date
    , elevation_gain
    , elevation_loss
    , aerobic_training_effect
    , anaerobic_training_effect
    , training_stress_score
    , normalized_power
    , avg_power
    , max_power
    , total_steps
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

for activity in activities:
    user_id = 1

    sport = activity.get("activityType", {}).get("typeKey", "Unknown")
    workout_type = activity.get("activityName", "Unknown")

    start_time_str = activity.get("startTimeLocal", None)
    if start_time_str:
        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

    # Skip if already recorded
    cursor.execute(
        "SELECT workout_id FROM workouts WHERE user_id = %s AND start_time = %s",
        (user_id, start_time_dt)
    )
    if cursor.fetchone():
        print(f"Workout at {start_time_dt} already recorded. Skipping.")
        continue

    workout_date = start_time_dt.date()
    duration_seconds = activity.get("duration", 0.0)
    end_time_dt = start_time_dt + timedelta(seconds=float(duration_seconds))

    calories_burned = activity.get("calories", 0)
    avg_heart_rate = activity.get("averageHR", 0)
    max_heart_rate = activity.get("maxHR", 0)

    vo2max = activity.get("vO2MaxValue", None)
    lactate_threshold = activity.get("lactateThresholdBpm", None)

    time_in_zone_1 = activity.get("hrTimeInZone_1", 0.0)
    time_in_zone_2 = activity.get("hrTimeInZone_2", 0.0)
    time_in_zone_3 = activity.get("hrTimeInZone_3", 0.0)
    time_in_zone_4 = activity.get("hrTimeInZone_4", 0.0)
    time_in_zone_5 = activity.get("hrTimeInZone_5", 0.0)

    training_volume = activity.get("distance", 0.0)

    avg_vertical_osc = activity.get("avgVerticalOscillation", None)
    avg_ground_contact = activity.get("avgGroundContactTime", None)
    avg_stride_length = activity.get("avgStrideLength", None)
    avg_vertical_ratio = activity.get("avgVerticalRatio", None)
    avg_running_cadence = activity.get("averageRunningCadenceInStepsPerMinute", None)
    max_running_cadence = activity.get("maxRunningCadenceInStepsPerMinute", None)

    location = activity.get("locationName", "Unknown")
    start_latitude = activity.get("startLatitude")
    start_longitude = activity.get("startLongitude")

    elevation_gain = activity.get("elevationGain", None)
    elevation_loss = activity.get("elevationLoss", None)
    aerobic_training_effect = activity.get("aerobicTrainingEffect", None)
    anaerobic_training_effect = activity.get("anaerobicTrainingEffect", None)
    training_stress_score = activity.get("trainingStressScore", None)
    normalized_power = activity.get("normalizedPower", None)
    avg_power = activity.get("avgPower", None)
    max_power = activity.get("maxPower", None)
    total_steps = activity.get("steps", None)

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
            start_latitude,
            start_longitude,
            workout_date,
            elevation_gain,
            elevation_loss,
            aerobic_training_effect,
            anaerobic_training_effect,
            training_stress_score,
            normalized_power,
            avg_power,
            max_power,
            total_steps,
        )
    )

    workout_id = cursor.fetchone()[0]
    print(f"Workout saved with ID: {workout_id} for date: {workout_date}")

conn.commit()
cursor.close()
conn.close()
print("All activities inserted successfully!")
