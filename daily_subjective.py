from datetime import datetime
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

# 2) Get today's date
today = datetime.now().date()
print(f"Recording daily subjective data for: {today}")

# 3) Check if we already have an entry for today
cursor.execute("SELECT SubjectiveID FROM DailySubjective WHERE EntryDate = ?", (today,))
row = cursor.fetchone()

if row:
    print(f"Data for today already exists with ID: {row[0]}")
    should_continue = input("Do you want to update today's entry? (y/n): ").lower()
    if should_continue != 'y':
        cursor.close()
        conn.close()
        print("Operation canceled.")
        exit()
    # Delete the existing entry if we're updating
    cursor.execute("DELETE FROM DailySubjective WHERE EntryDate = ?", (today,))
    conn.commit()
    print("Previous entry deleted. Please enter new values.")

# 4) Get workout ID for today if exists
workout_id = None
cursor.execute("SELECT WorkoutID FROM Workouts WHERE WorkoutDate = ?", (today,))
row = cursor.fetchone()
if row:
    workout_id = row[0]
    print(f"Found workout for today with ID: {workout_id}")
else:
    print("No workout found for today. Creating a reference workout...")
    # Create a placeholder workout for reference
    placeholder_sql = """
    INSERT INTO Workouts (
        UserID, Sport, StartTime, EndTime, WorkoutType, 
        CaloriesBurned, AvgHeartRate, MaxHeartRate, 
        TrainingVolume, Location, WorkoutDate
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    current_time = datetime.now()
    cursor.execute(
        placeholder_sql,
        (
            1,  # UserID
            "rest",  # Sport
            current_time,  # StartTime
            current_time,  # EndTime
            "Rest Day",  # WorkoutType
            0,  # CaloriesBurned
            0,  # AvgHeartRate
            0,  # MaxHeartRate
            0,  # TrainingVolume
            "Home",  # Location
            today  # WorkoutDate
        )
    )
    conn.commit()

    cursor.execute("SELECT SCOPE_IDENTITY()")
    workout_id = cursor.fetchone()[0]
    print(f"Created placeholder workout with ID: {workout_id}")

# 5) Collect subjective data from user
print("\n--- Daily Subjective Data Entry ---")
print("Rate the following from 1-10 (or leave blank for null)")


# Helper function to get integer input with null option
def get_int_input(prompt, min_val=1, max_val=10):
    while True:
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


energy_level = get_int_input("Energy Level")
mood = get_int_input("Mood")
hrv = get_int_input("HRV")
soreness = get_int_input("Soreness")
sleep_rating = get_int_input("Sleep Quality")
recovery = get_int_input("Recovery")
reflection = input("Reflection (any additional notes): ")

# 6) Insert the data
sql_insert = """
INSERT INTO DailySubjective (
    UserID,
    EntryDate,
    EnergyLevel,
    Mood,
    Soreness,
    SleepQuality,
    Recovery,
    Reflection
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

cursor.execute(
    sql_insert,
    (
        1,  # UserID
        today,
        energy_level,
        mood,
        hrv,
        soreness,
        sleep_rating,
        recovery,
        reflection
    )
)

conn.commit()
cursor.close()
conn.close()
print("Daily subjective data recorded successfully!")