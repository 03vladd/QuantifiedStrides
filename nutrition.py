from datetime import datetime
import pyodbc
import sys
import logging
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT
)
logger = logging.getLogger("nutrition")


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


def get_today_nutrition_entries(cursor, user_id=1):
    """Get all nutrition entries for today"""
    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    try:
        cursor.execute("""
            SELECT NutritionID, IngestionTime, FoodType, TotalCalories, 
                   MacrosCarbs, MacrosProtein, MacrosFat, Supplements
            FROM NutritionLog
            WHERE UserID = ? AND IngestionTime BETWEEN ? AND ?
            ORDER BY IngestionTime DESC
        """, (user_id, start_of_day, end_of_day))

        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching nutrition entries: {e}")
        return []


def get_float_input(prompt, min_val=0):
    """Get a float input with validation"""
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
    """Get an integer input with validation"""
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


def collect_nutrition_data(ingestion_time=None):
    """Collect nutrition data from user input"""
    if ingestion_time is None:
        ingestion_time = datetime.now()

    print(f"Recording nutrition intake for: {ingestion_time.strftime(config.DATETIME_FORMAT)}")

    food_type = input("Food Type (e.g., 'Breakfast', 'Protein Shake', 'Dinner'): ")
    calories = get_int_input("Total Calories")
    carbs = get_float_input("Carbohydrates (g)")
    protein = get_float_input("Protein (g)")
    fat = get_float_input("Fat (g)")
    supplements = input("Supplements (e.g., 'Multivitamin, Creatine', or press Enter for none): ")

    return {
        "ingestion_time": ingestion_time,
        "food_type": food_type,
        "calories": calories,
        "carbs": carbs,
        "protein": protein,
        "fat": fat,
        "supplements": supplements if supplements else None
    }


def insert_nutrition_data(cursor, user_id, data):
    """Insert nutrition data into the database"""
    try:
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

        cursor.execute(
            sql_insert,
            (
                user_id,
                data["ingestion_time"],
                data["food_type"],
                data["calories"],
                data["carbs"],
                data["protein"],
                data["fat"],
                data["supplements"]
            )
        )
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Error inserting nutrition data: {e}")
        return 0


def main():
    try:
        # Connect to database
        conn, cursor = connect_to_database()

        print("\n--- QuantifiedStrides Nutrition Log ---")

        # Get today's nutrition entries
        today_entries = get_today_nutrition_entries(cursor, config.DEFAULT_USER_ID)

        if today_entries:
            print(f"Today's nutrition entries ({len(today_entries)}):")
            for entry in today_entries:
                time_str = entry.IngestionTime.strftime('%H:%M')
                cals = f"{entry.TotalCalories} cal" if entry.TotalCalories else "N/A"
                print(f"- {time_str}: {entry.FoodType} ({cals})")

        # Ask if user wants to record a new entry or exit
        print("\nOptions:")
        print("1. Record a new nutrition entry")
        print("2. Exit")
        choice = input("Enter choice (1-2): ")

        if choice == "2":
            conn.close()
            print("Exiting without recording new data.")
            return 0

        # Collect nutrition data
        print("\nEnter details for your meal/nutrition intake")
        nutrition_data = collect_nutrition_data()

        # Insert the data
        rows_inserted = insert_nutrition_data(cursor, config.DEFAULT_USER_ID, nutrition_data)

        if rows_inserted:
            conn.commit()
            print("Nutrition data recorded successfully!")
        else:
            conn.rollback()
            print("Failed to record nutrition data.")

        # Close connections
        cursor.close()
        conn.close()
        return 0 if rows_inserted else 1

    except Exception as e:
        logger.error(f"Error in nutrition logging: {e}")
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