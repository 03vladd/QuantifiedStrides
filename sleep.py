from datetime import datetime, timedelta
import os
import garminconnect
import pyodbc
import json
import logging
import sys
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT
)
logger = logging.getLogger("sleep")


def connect_to_garmin():
    """Connect to Garmin API and return client"""
    client = garminconnect.Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
    client.login()
    return client


def connect_to_database():
    """Connect to the database and return connection and cursor"""
    try:
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def get_sleep_data(client, date_str):
    """Fetch sleep data from Garmin for the specified date"""
    return client.get_sleep_data(date_str)


def check_existing_sleep_data(cursor, user_id, sleep_date):
    """Check if sleep data already exists for the date"""
    cursor.execute(
        "SELECT SleepID FROM SleepSessions WHERE UserID = ? AND SleepDate = ?",
        (user_id, sleep_date)
    )
    return cursor.fetchone()


def delete_existing_sleep_data(cursor, user_id, sleep_date):
    """Delete existing sleep data for the date"""
    cursor.execute(
        "DELETE FROM SleepSessions WHERE UserID = ? AND SleepDate = ?",
        (user_id, sleep_date)
    )
    return cursor.rowcount


def process_sleep_data(sleep_data):
    """Process and extract relevant fields from the sleep data"""
    user_id = config.DEFAULT_USER_ID

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
    overnight_hrv = sleep_data.get("avgOvernightHrv", None)  # Same as HRV above
    hrv_status = sleep_data.get("hrvStatus", "")
    battery_change = sleep_data.get("bodyBatteryChange", None)

    return {
        "user_id": user_id,
        "duration_minutes": duration_minutes,
        "sleep_score": float(sleep_score) if sleep_score else None,
        "hrv": float(hrv) if hrv else None,
        "rhr": int(rhr) if rhr else None,
        "time_in_deep": deep_sleep_sec // 60,
        "time_in_light": light_sleep_sec // 60,
        "time_in_rem": rem_sleep_sec // 60,
        "time_awake": awake_sleep_sec // 60,
        "avg_stress": float(avg_stress) if avg_stress else None,
        "feedback": feedback,
        "insight": insight,
        "overnight_hrv": float(overnight_hrv) if overnight_hrv else None,
        "hrv_status": hrv_status,
        "battery_change": int(battery_change) if battery_change else None
    }


def insert_sleep_data(cursor, sleep_date, data):
    """Insert sleep data into the database"""
    sql_insert = """
    INSERT INTO SleepSessions (
        UserID, SleepDate, DurationMinutes, SleepScore, HRV, RHR, 
        TimeInDeep, TimeInLight, TimeInRem, TimeAwake, 
        AvgSleepStress, SleepScoreFeedback, SleepScoreInsight, 
        OvernightHRV, HRVStatus, BodyBatteryChange
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    cursor.execute(sql_insert, (
        data["user_id"],
        sleep_date,
        data["duration_minutes"],
        data["sleep_score"],
        data["hrv"],
        data["rhr"],
        data["time_in_deep"],
        data["time_in_light"],
        data["time_in_rem"],
        data["time_awake"],
        data["avg_stress"],
        data["feedback"],
        data["insight"],
        data["overnight_hrv"],
        data["hrv_status"],
        data["battery_change"]
    ))
    return cursor.rowcount


def main():
    try:
        # Get today's date
        today_date_str = datetime.today().strftime(config.DATE_FORMAT)
        today_date = datetime.strptime(today_date_str, config.DATE_FORMAT).date()
        print(f"Fetching sleep data for: {today_date_str}")

        # Connect to Garmin
        client = connect_to_garmin()

        # Connect to database
        conn, cursor = connect_to_database()
        print("Cursor connected")

        # Check if data already exists for today
        existing_data = check_existing_sleep_data(cursor, config.DEFAULT_USER_ID, today_date)

        if existing_data:
            logger.info(f"Sleep data for {today_date_str} already exists. Deleting existing record.")
            deleted = delete_existing_sleep_data(cursor, config.DEFAULT_USER_ID, today_date)
            logger.info(f"Deleted {deleted} existing record(s).")

        # Get sleep data from Garmin
        sleep_data = get_sleep_data(client, today_date_str)

        # Process the data
        processed_data = process_sleep_data(sleep_data)

        # Insert into database
        rows_inserted = insert_sleep_data(cursor, today_date, processed_data)

        if rows_inserted:
            # Commit and close
            conn.commit()
            print(f"Inserted sleep data for {today_date_str} successfully!")
        else:
            logger.error("Failed to insert sleep data")
            conn.rollback()

        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        logger.error(f"Error in sleep data collection: {e}")
        if 'conn' in locals() and conn:
            try:
                conn.rollback()
            except:
                pass
            try:
                conn.close()
            except:
                pass
        return 1


if __name__ == "__main__":
    exit(main())