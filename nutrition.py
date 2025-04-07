from datetime import datetime
import pyodbc
import sys

# 1) Database connection
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=QuantifiedStridesDB;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
print("Cursor connected")

# 2) Manual input for nutrition tracking
print("\n--- QuantifiedStrides Nutrition Log ---")
print("Enter details for your meal/nutrition intake")

# Helper functions for input
def get_float_input(prompt, min_val=0):
    while True:
        value = input(prompt + f" (minimum {min_val}, or press Enter for null): ")
        if value == "":
            return None
        try:
            val = float(value)
            if val >= min_val:
                return val
            else:
                print(f"Please enter a value of at least {min_val}")
        except ValueError:
            print("Please enter a valid number")

def get_int_input(prompt, min_val=0):
    while True:
        value = input(prompt + f" (minimum {min_val}, or press Enter for null): ")
        if value == "":
            return None
        try:
            val = int(value)
            if val >= min_val:
                return val
            else:
                print(f"Please enter a value of at least {min_val}")
        except ValueError:
            print("Please enter a valid number")

# 3) Collect nutrition data
current_time = datetime.now()
print(f"Recording nutrition intake for: {current_time.strftime('%Y-%m-%d %H:%M')}")

food_type = input("Food Type (e.g., 'Breakfast', 'Protein Shake', 'Dinner'): ")
calories = get_int_input("Total Calories")
carbs = get_float_input("Carbohydrates (g)")
protein = get_float_input("Protein (g)")
fat = get_float_input("Fat (g)")
supplements = input("Supplements (e.g., 'Multivitamin, Creatine', or press Enter for none): ")

# 4) Insert into database
sql_insert = """
INSERT INTO NutritionLog (
    UserID,
    IngestionTime,
    FoodType,
    TotalCalories,
    MacrosCarbs,
    MacrosProtein,
    MacrosFat,
    Supplements
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

try:
    cursor.execute(
        sql_insert,
        (
            1,  # UserID
            current_time,
            food_type,
            calories,
            carbs,
            protein,
            fat,
            supplements if supplements else None
        )
    )
    conn.commit()
    print("Nutrition data recorded successfully!")
except Exception as e:
    conn.rollback()
    print(f"Error recording nutrition data: {e}")
finally:
    cursor.close()
    conn.close()