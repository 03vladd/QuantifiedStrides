"""
One-time backfill: pull all Garmin sleep data from 2026-01-01 to today.

Run once:  python3 backfill_sleep.py
"""

from datetime import datetime, date, timedelta

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

conn   = get_connection()
cursor = conn.cursor()

sql_insert = """
INSERT INTO sleep_sessions (
      user_id, sleep_date, duration_minutes, sleep_score
    , hrv, rhr
    , time_in_deep, time_in_light, time_in_rem, time_awake
    , avg_sleep_stress, sleep_score_feedback, sleep_score_insight
    , overnight_hrv, hrv_status, body_battery_change
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (user_id, sleep_date) DO NOTHING;
"""

start = date(2026, 1, 1)
end   = date.today()
delta = (end - start).days + 1

inserted = 0
skipped  = 0
no_data  = 0

for i in range(delta):
    day     = start + timedelta(days=i)
    day_str = day.strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT sleep_id FROM sleep_sessions WHERE user_id = 1 AND sleep_date = %s",
        (day,)
    )
    if cursor.fetchone():
        skipped += 1
        continue

    try:
        sleep_data = client.get_sleep_data(day_str)
    except Exception as e:
        print(f"  [{day_str}] Error fetching: {e}")
        continue

    sleep_dto = sleep_data.get("dailySleepDTO", {})
    if not sleep_dto:
        no_data += 1
        continue

    deep  = sleep_dto.get("deepSleepSeconds")  or 0
    light = sleep_dto.get("lightSleepSeconds") or 0
    rem   = sleep_dto.get("remSleepSeconds")   or 0
    awake = sleep_dto.get("awakeSleepSeconds") or 0
    duration_minutes = (deep + light + rem + awake) // 60

    if duration_minutes == 0:
        no_data += 1
        continue

    sleep_score  = sleep_dto.get("sleepScores", {}).get("overall", {}).get("value")
    hrv          = sleep_data.get("avgOvernightHrv")
    rhr          = sleep_data.get("restingHeartRate")
    avg_stress   = sleep_dto.get("avgSleepStress")
    feedback     = sleep_dto.get("sleepScoreFeedback", "")
    insight      = sleep_dto.get("sleepScoreInsight", "")
    hrv_status   = sleep_data.get("hrvStatus", "")
    batt_change  = sleep_data.get("bodyBatteryChange")

    cursor.execute(sql_insert, (
        1, day, duration_minutes,
        float(sleep_score) if sleep_score else None,
        float(hrv)         if hrv         else None,
        int(rhr)           if rhr         else None,
        deep  // 60, light // 60, rem // 60, awake // 60,
        float(avg_stress)  if avg_stress  else None,
        feedback, insight,
        float(hrv)         if hrv         else None,
        hrv_status,
        int(batt_change)   if batt_change else None,
    ))
    print(f"  [{day_str}] score={sleep_score}, hrv={hrv}, deep={deep//60}m, light={light//60}m, rem={rem//60}m, awake={awake//60}m")
    inserted += 1

conn.commit()
cursor.close()
conn.close()
print(f"\nDone. {inserted} inserted, {skipped} already existed, {no_data} days with no data.")
