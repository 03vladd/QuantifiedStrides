from datetime import datetime, timedelta
import os
import garminconnect
import pyodbc
import json
import logging
import sys
import config

# Add this at the very top, right after imports
print("Sleep script starting...")
logger = logging.getLogger("sleep")
logger.setLevel(logging.DEBUG)
logger.info("Sleep script initialized")

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


def get_sleep_details(client, date_str):
    """Fetch detailed sleep data including movement, heart rate, etc."""
    try:
        logger.info(f"Getting detailed sleep data for {date_str}")

        # Basic sleep data
        sleep_data = client.get_sleep_data(date_str)

        # Get detailed sleep data with timestamps
        try:
            # Sleep movement data
            movement_data = client.get_sleep_movement_data(date_str)
        except Exception as e:
            logger.warning(f"Could not get sleep movement data: {e}")
            movement_data = {}

        # Get heart rate during sleep
        try:
            # HR data during sleep
            hr_data = client.get_heart_rates(date_str)
        except Exception as e:
            logger.warning(f"Could not get sleep heart rate data: {e}")
            hr_data = {}

        # Get respiration data if available
        try:
            respiration_data = client.get_respiration_data(date_str)
        except Exception as e:
            logger.warning(f"Could not get respiration data: {e}")
            respiration_data = {}

        # Get SpO2 data if available
        try:
            spo2_data = client.get_spo2_data(date_str)
        except Exception as e:
            logger.warning(f"Could not get SpO2 data: {e}")
            spo2_data = {}

        # Get sleep stages with timestamps if available
        try:
            sleep_stages = client.get_sleep_stages(sleep_data)
        except Exception as e:
            logger.warning(f"Could not get sleep stages: {e}")
            sleep_stages = []

        return {
            "summary": sleep_data,
            "movement": movement_data,
            "heart_rate": hr_data,
            "respiration": respiration_data,
            "spo2": spo2_data,
            "stages": sleep_stages
        }
    except Exception as e:
        logger.error(f"Error getting detailed sleep data: {e}")
        return {"summary": {}}


def check_existing_sleep_data(cursor, user_id, sleep_date):
    """Check if sleep data already exists for the date"""
    cursor.execute(
        "SELECT SleepID FROM SleepSessions WHERE UserID = ? AND SleepDate = ?",
        (user_id, sleep_date)
    )
    return cursor.fetchone()


def delete_existing_sleep_data(cursor, user_id, sleep_date):
    """Delete existing sleep data for the date"""
    # First delete detailed metrics if they exist
    try:
        cursor.execute("""
            DELETE FROM SleepMetrics 
            WHERE SleepID IN (SELECT SleepID FROM SleepSessions WHERE UserID = ? AND SleepDate = ?)
        """, (user_id, sleep_date))
        logger.info(f"Deleted {cursor.rowcount} sleep metric records")
    except Exception as e:
        logger.warning(f"Error deleting sleep metrics: {e}")

    # Then delete the main sleep record
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


def insert_sleep_metrics(cursor, sleep_id, metrics):
    """Insert detailed sleep metrics into the database"""
    if not metrics:
        logger.warning(f"No sleep metrics to insert for sleep ID: {sleep_id}")
        return 0

    # Check if SleepMetrics table exists, create it if not
    try:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'SleepMetrics')
            CREATE TABLE SleepMetrics (
                SleepMetricID INT PRIMARY KEY IDENTITY(1,1),
                SleepID INT NOT NULL,
                Timestamp DATETIME NOT NULL,
                HeartRate INT,
                HRV FLOAT,
                RespirationRate FLOAT,
                MovementIntensity FLOAT,
                SleepStage VARCHAR(20),
                BodyTemperature FLOAT,
                SpO2 FLOAT,
                FOREIGN KEY (SleepID) REFERENCES SleepSessions(SleepID)
            )
        """)

        # Create indexes
        try:
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_SleepMetrics_SleepID' AND object_id = OBJECT_ID('SleepMetrics'))
                CREATE INDEX IX_SleepMetrics_SleepID ON SleepMetrics(SleepID)
            """)

            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_SleepMetrics_Timestamp' AND object_id = OBJECT_ID('SleepMetrics'))
                CREATE INDEX IX_SleepMetrics_Timestamp ON SleepMetrics(Timestamp)
            """)
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    except Exception as e:
        logger.error(f"Error creating SleepMetrics table: {e}")
        return 0

    # Prepare batch insert values
    values = []
    for metric in metrics:
        # Extract values with defaults for missing metrics
        timestamp = metric.get("timestamp")
        heart_rate = metric.get("heart_rate")
        hrv = metric.get("hrv")
        respiration_rate = metric.get("respiration_rate")
        movement_intensity = metric.get("movement_intensity")
        sleep_stage = metric.get("sleep_stage")
        body_temperature = metric.get("body_temperature")
        spo2 = metric.get("spo2")

        values.append((
            sleep_id, timestamp, heart_rate, hrv, respiration_rate,
            movement_intensity, sleep_stage, body_temperature, spo2
        ))

    # Insert metrics in batches
    try:
        rows_inserted = 0
        batch_size = 1000  # Insert in batches of 1000

        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]

            cursor.executemany("""
                INSERT INTO SleepMetrics (
                    SleepID, Timestamp, HeartRate, HRV, RespirationRate,
                    MovementIntensity, SleepStage, BodyTemperature, SpO2
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

            rows_inserted += len(batch)
            logger.info(f"Inserted batch of {len(batch)} sleep metrics (total: {rows_inserted})")

        return rows_inserted
    except Exception as e:
        logger.error(f"Error inserting sleep metrics: {e}")
        return 0


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

    # Get the ID of the inserted sleep session
    cursor.execute("SELECT @@IDENTITY")
    sleep_id = cursor.fetchone()[0]

    return sleep_id


def process_sleep_metrics(sleep_details, sleep_date):
    """Process and extract time-series data from detailed sleep data"""
    metrics = []

    # Process sleep stages
    stages = sleep_details.get("stages", [])
    for stage in stages:
        try:
            # Convert timestamp to datetime
            timestamp_str = stage.get("timestamp", "")
            if not timestamp_str:
                continue

            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    logger.error(f"Could not parse timestamp: {timestamp_str}")
                    continue

            sleep_stage = stage.get("stage", "")
            metrics.append({
                "timestamp": timestamp,
                "sleep_stage": sleep_stage
            })
        except Exception as e:
            logger.error(f"Error processing sleep stage: {e}")

    # Process heart rate data
    heart_rate_data = sleep_details.get("heart_rate", {})
    hr_samples = heart_rate_data.get("heartRateValues", [])

    for sample in hr_samples:
        if len(sample) < 2:
            continue

        try:
            # Garmin typically returns timestamp as milliseconds since epoch
            timestamp = datetime.fromtimestamp(sample[0] / 1000.0)

            # Only include heart rate data from the sleep period
            sleep_date_start = datetime.combine(sleep_date, datetime.min.time())
            sleep_date_end = datetime.combine(sleep_date + timedelta(days=1), datetime.min.time())

            if sleep_date_start <= timestamp < sleep_date_end:
                heart_rate = sample[1]

                # Add heart rate to existing entry or create new one
                existing_entry = next((m for m in metrics if m["timestamp"] == timestamp), None)
                if existing_entry:
                    existing_entry["heart_rate"] = heart_rate
                else:
                    metrics.append({
                        "timestamp": timestamp,
                        "heart_rate": heart_rate
                    })
        except Exception as e:
            logger.error(f"Error processing heart rate sample: {e}")

    # Process movement data
    movement_data = sleep_details.get("movement", {})
    movement_samples = movement_data.get("movementValues", [])

    for sample in movement_samples:
        if len(sample) < 2:
            continue

        try:
            # Garmin typically returns timestamp as milliseconds since epoch
            timestamp = datetime.fromtimestamp(sample[0] / 1000.0)

            # Only include movement data from the sleep period
            sleep_date_start = datetime.combine(sleep_date, datetime.min.time())
            sleep_date_end = datetime.combine(sleep_date + timedelta(days=1), datetime.min.time())

            if sleep_date_start <= timestamp < sleep_date_end:
                movement = sample[1]

                # Add movement to existing entry or create new one
                existing_entry = next((m for m in metrics if m["timestamp"] == timestamp), None)
                if existing_entry:
                    existing_entry["movement_intensity"] = movement
                else:
                    metrics.append({
                        "timestamp": timestamp,
                        "movement_intensity": movement
                    })
        except Exception as e:
            logger.error(f"Error processing movement sample: {e}")

    # Process respiration data if available
    respiration_data = sleep_details.get("respiration", {})
    resp_samples = respiration_data.get("respirationValues", [])

    for sample in resp_samples:
        if len(sample) < 2:
            continue

        try:
            # Garmin typically returns timestamp as milliseconds since epoch
            timestamp = datetime.fromtimestamp(sample[0] / 1000.0)

            # Only include respiration data from the sleep period
            sleep_date_start = datetime.combine(sleep_date, datetime.min.time())
            sleep_date_end = datetime.combine(sleep_date + timedelta(days=1), datetime.min.time())

            if sleep_date_start <= timestamp < sleep_date_end:
                respiration_rate = sample[1]

                # Add respiration to existing entry or create new one
                existing_entry = next((m for m in metrics if m["timestamp"] == timestamp), None)
                if existing_entry:
                    existing_entry["respiration_rate"] = respiration_rate
                else:
                    metrics.append({
                        "timestamp": timestamp,
                        "respiration_rate": respiration_rate
                    })
        except Exception as e:
            logger.error(f"Error processing respiration sample: {e}")

    # Process SpO2 data if available
    spo2_data = sleep_details.get("spo2", {})
    spo2_samples = spo2_data.get("spo2Values", [])

    for sample in spo2_samples:
        if len(sample) < 2:
            continue

        try:
            # Garmin typically returns timestamp as milliseconds since epoch
            timestamp = datetime.fromtimestamp(sample[0] / 1000.0)

            # Only include SpO2 data from the sleep period
            sleep_date_start = datetime.combine(sleep_date, datetime.min.time())
            sleep_date_end = datetime.combine(sleep_date + timedelta(days=1), datetime.min.time())

            if sleep_date_start <= timestamp < sleep_date_end:
                spo2 = sample[1]

                # Add SpO2 to existing entry or create new one
                existing_entry = next((m for m in metrics if m["timestamp"] == timestamp), None)
                if existing_entry:
                    existing_entry["spo2"] = spo2
                else:
                    metrics.append({
                        "timestamp": timestamp,
                        "spo2": spo2
                    })
        except Exception as e:
            logger.error(f"Error processing SpO2 sample: {e}")

    # Sort metrics by timestamp
    metrics.sort(key=lambda x: x["timestamp"])

    return metrics


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

        # Get detailed sleep data from Garmin
        sleep_details = get_sleep_details(client, today_date_str)

        # Get basic sleep summary
        sleep_data = sleep_details.get("summary", {})

        # Process summary data
        processed_data = process_sleep_data(sleep_data)

        # Insert summary into database
        sleep_id = insert_sleep_data(cursor, today_date, processed_data)

        if sleep_id:
            logger.info(f"Inserted sleep summary for {today_date_str} with ID: {sleep_id}")

            # Process detailed metrics
            sleep_metrics = process_sleep_metrics(sleep_details, today_date)

            if sleep_metrics:
                # Insert detailed metrics
                metrics_inserted = insert_sleep_metrics(cursor, sleep_id, sleep_metrics)
                logger.info(f"Inserted {metrics_inserted} detailed sleep metrics")
            else:
                logger.warning("No detailed sleep metrics found")

            # Commit all changes
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