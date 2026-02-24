from datetime import datetime, timedelta

import garminconnect
import pyodbc
import json

from config import GARMIN_EMAIL, GARMIN_PASSWORD

# 1) Connect to Garmin
client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=QuantifiedStridesDB;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
print("Cursor connected")

today_date_str = datetime.today().strftime("%Y-%m-%d")
print(today_date_str)

# Guard: skip if sleep data for today is already recorded
today_date = datetime.strptime(today_date_str, "%Y-%m-%d").date()
cursor.execute(
    "SELECT SleepID FROM SleepSessions WHERE UserID = 1 AND SleepDate = ?",
    (today_date,)
)
if cursor.fetchone():
    print(f"Sleep data for {today_date_str} already recorded. Skipping.")
    cursor.close()
    conn.close()
    raise SystemExit(0)

sleep_data = client.get_sleep_data(today_date_str)

'''print(json.dumps(sleep_data, indent=4))'''

sql_insert = """
INSERT INTO SleepSessions (
        UserID
    , SleepDate
    , DurationMinutes
    , SleepScore
    , HRV
    , RHR
    , TimeInDeep
    , TimeInLight
    , TimeInRem
    , TimeAwake
    , AvgSleepStress
    , SleepScoreFeedback
    , SleepScoreInsight
    , OvernightHRV
    , HRVStatus
    , BodyBatteryChange
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# 6) Extract the data from the returned JSON/dict
# Most fields are nested under "dailySleepDTO"; sleepScore sits at the root.
user_id = 1  # assuming just one user

sleep_dto = sleep_data.get("dailySleepDTO", {})

deep_sleep_sec = sleep_dto.get("deepSleepSeconds", 0)
light_sleep_sec = sleep_dto.get("lightSleepSeconds", 0)
rem_sleep_sec = sleep_dto.get("remSleepSeconds", 0)
awake_sleep_sec = sleep_dto.get("awakeSleepSeconds", 0)

# Duration is the total of all phases (in seconds), then convert to minutes
duration_minutes = (deep_sleep_sec + light_sleep_sec + rem_sleep_sec + awake_sleep_sec) // 60

sleep_score = sleep_data.get("sleepScore", None)  # root-level
hrv = sleep_dto.get("avgOvernightHrv", None)
rhr = sleep_dto.get("restingHeartRate", None)

avg_stress = sleep_dto.get("avgSleepStress", None)
feedback = sleep_dto.get("sleepScoreFeedback", "")
insight = sleep_dto.get("sleepScoreInsight", "")
hrv_status = sleep_dto.get("hrvStatus", "")
battery_change = sleep_dto.get("bodyBatteryChange", None)

# 8. Execute the INSERT (assuming user ID = 1)
cursor.execute(sql_insert, (
    1,  # UserID
    today_date,
    duration_minutes,
    float(sleep_score) if sleep_score else None,
    float(hrv) if hrv else None,
    int(rhr) if rhr else None,
    deep_sleep_sec // 60,    # TimeInDeep in minutes
    light_sleep_sec // 60,   # TimeInLight in minutes
    rem_sleep_sec // 60,     # TimeInRem in minutes
    awake_sleep_sec // 60,   # TimeAwake in minutes
    float(avg_stress) if avg_stress else None,
    feedback,
    insight,
    float(hrv) if hrv else None,  # same as HRV above, or separate if you want
    hrv_status,
    int(battery_change) if battery_change else None
))

conn.commit()
cursor.close()
conn.close()

print(f"Inserted today's sleep data for {today_date_str} successfully!")