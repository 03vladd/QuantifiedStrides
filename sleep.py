from datetime import datetime, timedelta

import garminconnect
import pyodbc
import json

# 1) Connect to Garmin
client = garminconnect.Garmin("vasiuvlad984@gmail.com", "Mariguanas1")
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

'''week_ago = today - timedelta(days=7)'''

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
#    The actual keys may differ — check print(sleep_data) to be sure.
user_id = 1  # assuming just one user

deep_sleep_sec = sleep_data.get("deepSleepSeconds", 0)
light_sleep_sec = sleep_data.get("lightSleepSeconds", 0)
rem_sleep_sec = sleep_data.get("remSleepSeconds", 0)
awake_sleep_sec = sleep_data.get("awakeSleepSeconds", 0)

# Duration is the total of all phases (in seconds), then convert to minutes
duration_minutes = (deep_sleep_sec + light_sleep_sec + rem_sleep_sec + awake_sleep_sec) // 60

sleep_score = sleep_data.get("sleepScore", None)
hrv = sleep_data.get("avgOvernightHrv", None)
rhr = sleep_data.get("restingHeartRate", None)

avg_stress = sleep_data.get("avgSleepStress", None)
feedback = sleep_data.get("sleepScoreFeedback", "")
insight = sleep_data.get("sleepScoreInsight", "")
hrv_status = sleep_data.get("hrvStatus", "")
battery_change = sleep_data.get("bodyBatteryChange", None)

today_date = datetime.strptime(today_date_str, "%Y-%m-%d").date()

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