from datetime import datetime, timedelta
import pyodbc
import logging
import sys
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT
)
logger = logging.getLogger("injuries")


def connect_to_database():
    """Connect to the database and return connection and cursor"""
    try:
        conn = pyodbc.connect(config.DB_CONNECTION)
        cursor = conn.cursor()
        print("Cursor connected")
        return conn, cursor
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def get_active_injuries(cursor, user_id=1):
    """Get all active injuries for the user"""
    current_date = datetime.now().date()

    try:
        cursor.execute("""
            SELECT InjuryID, InjuryType, StartDate, EndDate, Severity, Notes
            FROM Injuries
            WHERE UserID = ? AND (EndDate IS NULL OR EndDate >= ?)
            ORDER BY StartDate DESC
        """, (user_id, current_date))

        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching active injuries: {e}")
        return []


def update_injury(cursor, injury_id, field, value):
    """Update a specific field for an injury"""
    try:
        if field == "EndDate" and isinstance(value, str):
            # Convert string date to datetime
            value = datetime.strptime(value, config.DATE_FORMAT).date()

        sql = f"UPDATE Injuries SET {field} = ? WHERE InjuryID = ?"
        cursor.execute(sql, (value, injury_id))
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Error updating injury: {e}")
        return 0


def insert_new_injury(cursor, user_id, injury_data):
    """Insert a new injury record"""
    try:
        sql_insert = """
        INSERT INTO Injuries (
            UserID,
            StartDate,
            EndDate,
            InjuryType,
            Severity,
            Notes
        ) VALUES (?, ?, ?, ?, ?, ?);
        """

        cursor.execute(
            sql_insert,
            (
                user_id,
                injury_data["start_date"],
                injury_data["end_date"],
                injury_data["injury_type"],
                injury_data["severity"],
                injury_data["notes"]
            )
        )
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Error inserting injury: {e}")
        return 0


def main():
    try:
        # Connect to database
        conn, cursor = connect_to_database()

        print("\n--- QuantifiedStrides Injury Tracker ---")

        # Get active injuries
        active_injuries = get_active_injuries(cursor, config.DEFAULT_USER_ID)

        if active_injuries:
            print("Active injuries:")
            for injury in active_injuries:
                print(
                    f"ID: {injury.InjuryID}, Type: {injury.InjuryType}, Started: {injury.StartDate.strftime(config.DATE_FORMAT)}, Severity: {injury.Severity}"
                )

            # Option to update an existing injury
            print("\nOptions:")
            print("1. Update an existing injury")
            print("2. Record a new injury")
            print("3. Exit without changes")
            choice = input("Enter choice (1-3): ")

            if choice == "1":
                # Update existing injury
                injury_id = input("Enter injury ID to update: ")
                try:
                    injury_id = int(injury_id)
                    # Check if injury exists
                    cursor.execute("SELECT InjuryID FROM Injuries WHERE InjuryID = ? AND UserID = ?",
                                   (injury_id, config.DEFAULT_USER_ID))
                    if not cursor.fetchone():
                        print("Injury not found.")
                        conn.close()
                        return 0

                    print("\nWhat would you like to update?")
                    print("1. Mark as resolved (set end date)")
                    print("2. Update severity")
                    print("3. Update notes")
                    update_choice = input("Enter choice (1-3): ")

                    if update_choice == "1":
                        end_date = input("Enter end date (YYYY-MM-DD, or press Enter for today): ")
                        if end_date.strip() == "":
                            end_date = datetime.now().date()
                        else:
                            try:
                                end_date = datetime.strptime(end_date, config.DATE_FORMAT).date()
                            except ValueError:
                                print("Invalid date format. Using today's date.")
                                end_date = datetime.now().date()

                        rows_updated = update_injury(cursor, injury_id, "EndDate", end_date)
                        if rows_updated:
                            print(f"Injury marked as resolved as of {end_date}")
                            conn.commit()
                        else:
                            print("Failed to update injury.")
                            conn.rollback()

                    elif update_choice == "2":
                        severity_options = ["Mild", "Moderate", "Severe"]
                        print("Severity Options:")
                        for i, option in enumerate(severity_options, 1):
                            print(f"{i}. {option}")

                        severity_choice = input("Select severity (1-3): ")
                        try:
                            severity = severity_options[int(severity_choice) - 1]
                            rows_updated = update_injury(cursor, injury_id, "Severity", severity)
                            if rows_updated:
                                print(f"Injury severity updated to {severity}")
                                conn.commit()
                            else:
                                print("Failed to update injury.")
                                conn.rollback()
                        except (ValueError, IndexError):
                            print("Invalid choice.")
                            conn.rollback()

                    elif update_choice == "3":
                        notes = input("Enter new notes: ")
                        rows_updated = update_injury(cursor, injury_id, "Notes", notes)
                        if rows_updated:
                            print("Injury notes updated")
                            conn.commit()
                        else:
                            print("Failed to update injury.")
                            conn.rollback()

                    else:
                        print("Invalid choice.")

                except ValueError:
                    print("Invalid injury ID.")

            elif choice == "3":
                # Exit without changes
                conn.close()
                return 0

            # If choice is 2 or invalid, proceed to recording a new injury
            if choice != "1":
                choice = "2"
        else:
            print("No active injuries found.")
            print("\nOptions:")
            print("1. Record a new injury")
            print("2. Exit")
            choice = input("Enter choice (1-2): ")

            if choice == "2":
                conn.close()
                return 0

            choice = "1"  # Set to record a new injury

        # Record a new injury
        if choice == "2":
            print("\n--- Record New Injury ---")

            injury_type = input("Injury Type (e.g., 'Runner's knee', 'Achilles tendonitis'): ")

            start_date = input("Start Date (YYYY-MM-DD, or press Enter for today): ")
            if start_date.strip() == "":
                start_date = datetime.now().date()
            else:
                try:
                    start_date = datetime.strptime(start_date, config.DATE_FORMAT).date()
                except ValueError:
                    print("Invalid date format. Using today's date.")
                    start_date = datetime.now().date()

            severity_options = ["Mild", "Moderate", "Severe"]
            print("Severity Options:")
            for i, option in enumerate(severity_options, 1):
                print(f"{i}. {option}")

            severity_choice = input("Select severity (1-3): ")
            try:
                severity = severity_options[int(severity_choice) - 1]
            except (ValueError, IndexError):
                print("Invalid choice, defaulting to 'Moderate'")
                severity = "Moderate"

            notes = input("Notes (symptoms, context, etc.): ")

            # Prepare injury data
            injury_data = {
                "start_date": start_date,
                "end_date": None,  # No end date for new injuries
                "injury_type": injury_type,
                "severity": severity,
                "notes": notes
            }

            # Insert the injury
            rows_inserted = insert_new_injury(cursor, config.DEFAULT_USER_ID, injury_data)

            if rows_inserted:
                conn.commit()
                print(f"New injury ({injury_type}) recorded successfully.")
            else:
                conn.rollback()
                print("Failed to record injury.")

        # Close connections
        cursor.close()
        conn.close()
        print("Injury tracking completed.")
        return 0

    except Exception as e:
        logger.error(f"Error in injury tracking: {e}")
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