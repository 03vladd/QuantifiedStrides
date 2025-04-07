from datetime import datetime
import pyodbc
import sys
import time

# 1) Database connection
try:
    print("Attempting database connection...")
    conn = pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=localhost;"
        "Database=QuantifiedStridesDB;"
        "Trusted_Connection=yes;"
    )
    cursor = conn.cursor()
    print("✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    sys.exit(1)

# 2) Get today's date
today = datetime.now().date()
print(f"Recording daily subjective data for: {today}")

# 3) Check if we already have an entry for today
cursor.execute("SELECT SubjectiveID FROM DailySubjective WHERE EntryDate = ?", (today,))
row = cursor.fetchone()

if row:
    print(f"Data for today already exists with ID: {row[0]}")
    print("WAITING FOR INPUT: Do you want to update today's entry? (y/n)")
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

# 5) Collect subjective data from user
print("\n--- Daily Subjective Data Entry ---")
print("Rate the following from 1-10 (or leave blank for null)")


# Helper function to get integer input with null option
def get_int_input(prompt, min_val=1, max_val=10):
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


print("Starting to collect subjective data...")
energy_level = get_int_input("Energy Level")
print(f"✓ Energy Level recorded: {energy_level}")

mood = get_int_input("Mood")
print(f"✓ Mood recorded: {mood}")

rpe = get_int_input("RPE (Rate of Perceived Exertion)")
print(f"✓ RPE recorded: {rpe}")

soreness = get_int_input("Soreness")
print(f"✓ Soreness recorded: {soreness}")

enough_food = get_int_input("Enough Food (1-10, where 10 is completely satisfied)")
print(f"✓ Enough Food recorded: {enough_food}")

recovery = get_int_input("Recovery")
print(f"✓ Recovery recorded: {recovery}")

print("WAITING FOR INPUT: Reflection (any additional notes)")
reflection = input("Reflection (any additional notes): ")
print(f"✓ Reflection recorded (length: {len(reflection)} characters)")

# 6) Insert the data
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
            1,  # UserID
            today,
            energy_level,
            mood,
            rpe,
            soreness,
            enough_food,
            recovery,
            reflection
        )
    )

    conn.commit()
    print("✓ Database insert successful")
except Exception as e:
    print(f"✗ Database insert failed: {e}")
    conn.rollback()

cursor.close()
conn.close()
print("Daily subjective data recorded successfully!")
print("Script completed at:", datetime.now())