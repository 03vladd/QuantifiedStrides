from datetime import datetime
import pyodbc
import sys
import time
import logging
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT
)
logger = logging.getLogger("daily_subjective")


def connect_to_database():
    """Connect to the database and return connection and cursor"""
    try:
        print("Attempting database connection...")
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        print("✓ Database connection successful")
        return conn, cursor
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)


def check_existing_entry(cursor, today):
    """Check if an entry already exists for today"""
    cursor.execute("SELECT SubjectiveID FROM DailySubjective WHERE EntryDate = ?", (today,))
    return cursor.fetchone()


def delete_existing_entry(cursor, today):
    """Delete the existing entry for today"""
    cursor.execute("DELETE FROM DailySubjective WHERE EntryDate = ?", (today,))
    return cursor.rowcount


def get_int_input(prompt, min_val=1, max_val=10):
    """Get integer input from user with validation"""
    while True:
        print(f"WAITING FOR INPUT: {prompt} ({min_val}-{max_val}, or press Enter for null)")
        value = input(prompt + f" ({min_val}-{max_val}, or press Enter for null): ")
        if value == "":
            return None
        try:
            val = int(value)
            if min_val <= val <= max_val:
                return val
            else:
                print(f"Please enter a value between {min_val} and {max_val}")
        except ValueError:
            print("Please enter a valid number")


def collect_subjective_data():
    """Collect subjective data from user"""
    print("\n--- Daily Subjective Data Entry ---")
    print("Rate the following from 1-10 (or leave blank for null)")

    print("Starting to collect subjective data...")

    data = {}

    data["energy_level"] = get_int_input("Energy Level")
    print(f"✓ Energy Level recorded: {data['energy_level']}")

    data["mood"] = get_int_input("Mood")
    print(f"✓ Mood recorded: {data['mood']}")

    data["rpe"] = get_int_input("RPE (Rate of Perceived Exertion)")
    print(f"✓ RPE recorded: {data['rpe']}")

    data["soreness"] = get_int_input("Soreness")
    print(f"✓ Soreness recorded: {data['soreness']}")

    data["enough_food"] = get_int_input("Enough Food (1-10, where 10 is completely satisfied)")
    print(f"✓ Enough Food recorded: {data['enough_food']}")

    data["recovery"] = get_int_input("Recovery")
    print(f"✓ Recovery recorded: {data['recovery']}")

    print("WAITING FOR INPUT: Reflection (any additional notes)")
    data["reflection"] = input("Reflection (any additional notes): ")
    print(f"✓ Reflection recorded (length: {len(data['reflection'])} characters)")

    return data


def insert_subjective_data(cursor, user_id, today, data):
    """Insert subjective data into database"""
    print("Inserting data into database...")
    sql_insert = """
    INSERT INTO DailySubjective (
        UserID,
        EntryDate,
        EnergyLevel,
        Mood,
        RPE,
        Soreness,
        EnoughFood,
        Recovery,
        Reflection
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    try:
        cursor.execute(
            sql_insert,
            (
                user_id,  # UserID
                today,
                data["energy_level"],
                data["mood"],
                data["rpe"],
                data["soreness"],
                data["enough_food"],
                data["recovery"],
                data["reflection"]
            )
        )
        return cursor.rowcount
    except Exception as e:
        print(f"✗ Database insert failed: {e}")
        return 0


def main():
    try:
        # Get today's date
        today = datetime.now().date()
        print(f"Recording daily subjective data for: {today}")

        # Connect to database
        conn, cursor = connect_to_database()

        # Check if we already have an entry for today
        existing = check_existing_entry(cursor, today)

        if existing:
            print(f"Data for today already exists with ID: {existing[0]}")
            print("WAITING FOR INPUT: Do you want to update today's entry? (y/n)")
            should_continue = input("Do you want to update today's entry? (y/n): ").lower()
            if should_continue != 'y':
                cursor.close()
                conn.close()
                print("Operation canceled.")
                return 0

            # Delete the existing entry if we're updating
            deleted = delete_existing_entry(cursor, today)
            print(f"Previous entry deleted ({deleted} rows). Please enter new values.")

        # Collect subjective data
        data = collect_subjective_data()

        # Insert the data
        rows_inserted = insert_subjective_data(cursor, config.DEFAULT_USER_ID, today, data)

        if rows_inserted:
            conn.commit()
            print("✓ Database insert successful")
            print("Daily subjective data recorded successfully!")
        else:
            conn.rollback()
            print("Failed to record subjective data.")

        cursor.close()
        conn.close()
        print("Script completed at:", datetime.now())
        return 0 if rows_inserted else 1

    except Exception as e:
        logger.error(f"Error in daily subjective data collection: {e}")
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