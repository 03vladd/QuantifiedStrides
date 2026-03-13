from datetime import datetime

import garminconnect

from config import GARMIN_EMAIL, GARMIN_PASSWORD
from db import get_connection

# 1) Connect to Garmin
client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

conn = get_connection()
cursor = conn.cursor()
print("Cursor connected")

today_date_str = datetime.today().strftime("%Y-%m-%d")
today_date = datetime.strptime(today_date_str, "%Y-%m-%d").date()
print(today_date_str)

# Guard: skip if sleep data for today is already recorded
cursor.execute(
    "SELECT sleep_id FROM sleep_sessions WHERE user_id = 1 AND sleep_date = %s",
    (today_date,)
)
if cursor.fetchone():
    print(f"Sleep data for {today_date_str} already recorded. Skipping.")
    cursor.close()
    conn.close()
    raise SystemExit(0)

sleep_data = client.get_sleep_data(today_date_str)

sql_insert = """
INSERT INTO sleep_sessions (
      user_id
    , sleep_date
    , duration_minutes
    , sleep_score
    , hrv
    , rhr
    , time_in_deep
    , time_in_light
    , time_in_rem
    , time_awake
    , avg_sleep_stress
    , sleep_score_feedback
    , sleep_score_insight
    , overnight_hrv
    , hrv_status
    , body_battery_change
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

sleep_dto = sleep_data.get("dailySleepDTO", {})

deep_sleep_sec = sleep_dto.get("deepSleepSeconds") or 0
light_sleep_sec = sleep_dto.get("lightSleepSeconds") or 0
rem_sleep_sec = sleep_dto.get("remSleepSeconds") or 0
awake_sleep_sec = sleep_dto.get("awakeSleepSeconds") or 0

duration_minutes = (deep_sleep_sec + light_sleep_sec + rem_sleep_sec + awake_sleep_sec) // 60

sleep_score = sleep_data.get("sleepScore", None)
hrv = sleep_dto.get("avgOvernightHrv", None)
rhr = sleep_dto.get("restingHeartRate", None)

avg_stress = sleep_dto.get("avgSleepStress", None)
feedback = sleep_dto.get("sleepScoreFeedback", "")
insight = sleep_dto.get("sleepScoreInsight", "")
hrv_status = sleep_dto.get("hrvStatus", "")
battery_change = sleep_dto.get("bodyBatteryChange", None)

cursor.execute(sql_insert, (
    1,  # user_id
    today_date,
    duration_minutes,
    float(sleep_score) if sleep_score else None,
    float(hrv) if hrv else None,
    int(rhr) if rhr else None,
    deep_sleep_sec // 60,
    light_sleep_sec // 60,
    rem_sleep_sec // 60,
    awake_sleep_sec // 60,
    float(avg_stress) if avg_stress else None,
    feedback,
    insight,
    float(hrv) if hrv else None,
    hrv_status,
    int(battery_change) if battery_change else None,
))

conn.commit()
cursor.close()
conn.close()
print(f"Inserted today's sleep data for {today_date_str} successfully!")
