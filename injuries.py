from datetime import datetime, timedelta
import pyodbc

# 1) Database connection
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=QuantifiedStridesDB;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
print("Cursor connected")

# 2) Check active injuries
print("\n--- QuantifiedStrides Injury Tracker ---")

# Get current date for comparison
current_date = datetime.now().date()

cursor.execute("""
    SELECT InjuryID, InjuryType, StartDate, EndDate, Severity
    FROM Injuries
    WHERE UserID = 1 AND (EndDate IS NULL OR EndDate >= ?)
    ORDER BY StartDate DESC
""", (current_date,))

active_injuries = cursor.fetchall()

if active_injuries:
    print("Active injuries:")
    for injury in active_injuries:
        print(
            f"ID: {injury.InjuryID}, Type: {injury.InjuryType}, Started: {injury.StartDate.strftime('%Y-%m-%d')}, Severity: {injury.Severity}")

    # Option to update an existing injury
    print("\nOptions:")
    print("1. Update an existing injury")
    print("2. Record a new injury")
    choice = input("Enter choice (1-2): ")

    if choice == "1":
        injury_id = input("Enter injury ID to update: ")
        try:
            injury_id = int(injury_id)
            # Check if injury exists
            cursor.execute("SELECT InjuryID FROM Injuries WHERE InjuryID = ? AND UserID = 1", (injury_id,))
            if not cursor.fetchone():
                print("Injury not found.")
                conn.close()
                exit()

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
                    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                cursor.execute("UPDATE Injuries SET EndDate = ? WHERE InjuryID = ?", (end_date, injury_id))
                conn.commit()
                print(f"Injury marked as resolved as of {end_date}")

            elif update_choice == "2":
                severity = input("Enter new severity (Mild/Moderate/Severe): ")
                cursor.execute("UPDATE Injuries SET Severity = ? WHERE InjuryID = ?", (severity, injury_id))
                conn.commit()
                print(f"Injury severity updated to {severity}")

            elif update_choice == "3":
                notes = input("Enter new notes: ")
                cursor.execute("UPDATE Injuries SET Notes = ? WHERE InjuryID = ?", (notes, injury_id))
                conn.commit()
                print("Injury notes updated")

            else:
                print("Invalid choice.")

        except ValueError:
            print("Invalid injury ID.")
            conn.close()
            exit()

else:
    print("No active injuries found.")

# Record a new injury if no active injuries or user chose option 2
if not active_injuries or choice == "2":
    print("\n--- Record New Injury ---")

    injury_type = input("Injury Type (e.g., 'Runner's knee', 'Achilles tendonitis'): ")

    start_date = input("Start Date (YYYY-MM-DD, or press Enter for today): ")
    if start_date.strip() == "":
        start_date = datetime.now().date()
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

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

    # Insert the new injury
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
            1,  # UserID
            start_date,
            None,  # EndDate (null for active injuries)
            injury_type,
            severity,
            notes
        )
    )

    conn.commit()
    print(f"New injury ({injury_type}) recorded successfully.")

cursor.close()
conn.close()
print("Injury tracking completed.")