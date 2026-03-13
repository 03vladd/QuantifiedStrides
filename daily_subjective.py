from datetime import datetime

from db import get_connection

conn = get_connection()
cursor = conn.cursor()
print("Cursor connected")

today = datetime.now().date()
print(f"Recording daily subjective data for: {today}")

# Check if we already have an entry for today
cursor.execute(
    "SELECT subjective_id FROM daily_subjective WHERE entry_date = %s",
    (today,)
)
row = cursor.fetchone()

if row:
    print(f"Data for today already exists with ID: {row[0]}")
    should_continue = input("Do you want to update today's entry? (y/n): ").lower()
    if should_continue != 'y':
        cursor.close()
        conn.close()
        print("Operation canceled.")
        exit()
    cursor.execute("DELETE FROM daily_subjective WHERE entry_date = %s", (today,))
    conn.commit()
    print("Previous entry deleted. Please enter new values.")

print("\n--- Daily Subjective Data Entry ---")
print("Rate the following from 1-10 (or leave blank for null)")


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

sql_insert = """
INSERT INTO daily_subjective (
    user_id,
    entry_date,
    energy_level,
    mood,
    hrv,
    soreness,
    sleep_quality,
    recovery,
    reflection
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

cursor.execute(sql_insert, (
    1,
    today,
    energy_level,
    mood,
    hrv,
    soreness,
    sleep_rating,
    recovery,
    reflection,
))

conn.commit()
cursor.close()
conn.close()
print("Daily subjective data recorded successfully!")
