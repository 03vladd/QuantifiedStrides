"""
One-time backfill: pull all Garmin activities from 2026-01-01 to today
and insert any that aren't already in the DB.

Run once:  python3 backfill_workouts.py
"""

from datetime import datetime, timedelta

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

START_DATE = "2026-01-01"
END_DATE   = datetime.today().strftime("%Y-%m-%d")

print(f"Fetching activities from {START_DATE} to {END_DATE}...")
activities = client.get_activities_by_date(START_DATE, END_DATE)
print(f"Found {len(activities)} activities on Garmin.")

conn   = get_connection()
cursor = conn.cursor()

sql_insert = """
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
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
RETURNING workout_id;
"""

inserted = 0
skipped  = 0

for activity in activities:
    start_time_str = activity.get("startTimeLocal")
    if not start_time_str:
        continue

    try:
        start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "SELECT workout_id FROM workouts WHERE user_id = 1 AND start_time = %s",
        (start_time_dt,)
    )
    if cursor.fetchone():
        skipped += 1
        continue

    workout_date     = start_time_dt.date()
    duration_seconds = activity.get("duration", 0.0)
    end_time_dt      = start_time_dt + timedelta(seconds=float(duration_seconds))

    cursor.execute(sql_insert, (
        1,
        activity.get("activityType", {}).get("typeKey", "Unknown"),
        start_time_dt,
        end_time_dt,
        activity.get("activityName", "Unknown"),
        activity.get("calories", 0),
        activity.get("averageHR", 0),
        activity.get("maxHR", 0),
        activity.get("vO2MaxValue"),
        activity.get("lactateThresholdBpm"),
        activity.get("hrTimeInZone_1", 0.0),
        activity.get("hrTimeInZone_2", 0.0),
        activity.get("hrTimeInZone_3", 0.0),
        activity.get("hrTimeInZone_4", 0.0),
        activity.get("hrTimeInZone_5", 0.0),
        activity.get("distance", 0.0),
        activity.get("avgVerticalOscillation"),
        activity.get("avgGroundContactTime"),
        activity.get("avgStrideLength"),
        activity.get("avgVerticalRatio"),
        activity.get("averageRunningCadenceInStepsPerMinute"),
        activity.get("maxRunningCadenceInStepsPerMinute"),
        activity.get("locationName", "Unknown"),
        activity.get("startLatitude"),
        activity.get("startLongitude"),
        workout_date,
    ))

    workout_id = cursor.fetchone()[0]
    print(f"  [{workout_date}] {activity.get('activityName')} — ID {workout_id}")
    inserted += 1

conn.commit()
cursor.close()
conn.close()
print(f"\nDone. {inserted} inserted, {skipped} already existed.")
