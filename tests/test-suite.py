import unittest
import os
import sys
import pyodbc
import datetime
import subprocess
from unittest.mock import patch, MagicMock

# Add project directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class TestDatabaseConnection(unittest.TestCase):
    """Test database connectivity and schema validation"""

    def setUp(self):
        try:
            self.conn = pyodbc.connect(config.DB_CONNECTION)
            self.cursor = self.conn.cursor()
        except Exception as e:
            self.fail(f"Failed to connect to database: {e}")

    def tearDown(self):
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_connection(self):
        """Test basic database connectivity"""
        self.assertTrue(self.conn)
        self.assertTrue(self.cursor)

    def test_users_table(self):
        """Test Users table exists and has expected structure"""
        # Using LIMIT 1 instead of TOP 1 for better portability
        self.cursor.execute("SELECT * FROM Users LIMIT 1")
        columns = [column[0] for column in self.cursor.description]
        expected_columns = ['UserID', 'Name', 'DateOfBirth']
        for col in expected_columns:
            self.assertIn(col, columns, f"Missing column {col} in Users table")

    def test_workouts_table(self):
        """Test Workouts table exists and has expected structure"""
        # Using LIMIT 1 instead of TOP 1 for better portability
        self.cursor.execute("SELECT * FROM Workouts LIMIT 1")
        columns = [column[0] for column in self.cursor.description]
        expected_columns = [
            'WorkoutID', 'UserID', 'Sport', 'StartTime', 'EndTime',
            'WorkoutType', 'CaloriesBurned', 'AvgHeartRate', 'WorkoutDate'
        ]
        for col in expected_columns:
            self.assertIn(col, columns, f"Missing column {col} in Workouts table")

    def test_has_is_indoor_column(self):
        """Test that IsIndoor column exists in Workouts table"""
        self.cursor.execute("""
            SELECT * 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Workouts' AND COLUMN_NAME = 'IsIndoor'
        """)
        result = self.cursor.fetchone()
        self.assertIsNotNone(result, "IsIndoor column missing from Workouts table")


class TestScriptExecution(unittest.TestCase):
    """Test execution of individual data collection scripts"""

    @patch('subprocess.run')
    def test_workout_script(self, mock_run):
        """Test workout.py can be executed"""
        mock_process = MagicMock()
        mock_process.stdout = "Cursor connected\nAll activities inserted successfully!"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        from main import run_script
        result = run_script('workout.py')
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_sleep_script(self, mock_run):
        """Test sleep.py can be executed"""
        mock_process = MagicMock()
        mock_process.stdout = "Cursor connected\nInserted sleep data successfully!"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        from main import run_script
        result = run_script('sleep.py')
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_environment_script(self, mock_run):
        """Test environment.py can be executed"""
        mock_process = MagicMock()
        mock_process.stdout = "Cursor connected\nEnvironmental data recorded successfully!"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        from main import run_script
        result = run_script('enviroment.py')  # Note: using actual filename with typo
        self.assertTrue(result)
        mock_run.assert_called_once()


class TestConfigIntegrity(unittest.TestCase):
    """Test configuration integrity"""

    def test_config_values(self):
        """Test that all required config values are present"""
        required_values = [
            'DB_CONNECTION', 'DEFAULT_USER_ID', 'DEFAULT_LOCATION',
            'DATE_FORMAT', 'DATETIME_FORMAT', 'AUTOMATED_SCRIPTS',
            'INTERACTIVE_SCRIPTS'
        ]
        for value in required_values:
            self.assertTrue(hasattr(config, value), f"Missing config value: {value}")

    def test_api_keys(self):
        """Test that API keys are available"""
        self.assertTrue(hasattr(config, 'GARMIN_EMAIL'), "Missing Garmin email")
        self.assertTrue(hasattr(config, 'GARMIN_PASSWORD'), "Missing Garmin password")
        self.assertTrue(hasattr(config, 'OPENWEATHER_API_KEY'), "Missing OpenWeather API key")
        self.assertTrue(hasattr(config, 'AMBEE_API_KEY'), "Missing Ambee API key")

    def test_script_lists(self):
        """Test that script lists are correctly defined"""
        # Check that all automated scripts exist
        for script in config.AUTOMATED_SCRIPTS:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), script)
            self.assertTrue(os.path.exists(script_path), f"Script doesn't exist: {script}")

        # Check that all interactive scripts exist
        for script in config.INTERACTIVE_SCRIPTS:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), script)
            self.assertTrue(os.path.exists(script_path), f"Script doesn't exist: {script}")


class TestAPIIntegration(unittest.TestCase):
    """Test integration with external APIs"""

    @patch('requests.get')
    def test_weather_api(self, mock_get):
        """Test OpenWeatherMap API integration"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 15.5, "humidity": 65},
            "wind": {"speed": 3.5, "deg": 180},
            "name": "Cluj-Napoca"
        }
        mock_get.return_value = mock_response

        # Import function directly from environment.py
        from environment import get_weather_data
        weather_data = get_weather_data(
            config.DEFAULT_LOCATION['lat'],
            config.DEFAULT_LOCATION['lon'],
            config.OPENWEATHER_API_KEY
        )

        self.assertEqual(weather_data['main']['temp'], 15.5)
        self.assertEqual(weather_data['main']['humidity'], 65)
        self.assertEqual(weather_data['wind']['speed'], 3.5)

    @patch('requests.get')
    def test_pollen_api(self, mock_get):
        """Test Ambee API integration for pollen data"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "success",
            "data": [{
                "Count": {
                    "grass_pollen": 10,
                    "tree_pollen": 50,
                    "weed_pollen": 5
                },
                "Risk": {
                    "grass_pollen": "Low",
                    "tree_pollen": "Moderate",
                    "weed_pollen": "Low"
                }
            }]
        }
        mock_get.return_value = mock_response

        # Import function directly from environment.py
        from environment import get_pollen_data, process_pollen_data
        pollen_data = get_pollen_data(
            config.DEFAULT_LOCATION['lat'],
            config.DEFAULT_LOCATION['lon'],
            config.AMBEE_API_KEY
        )

        current_month = datetime.datetime.now().month
        processed_data = process_pollen_data(pollen_data, current_month)

        self.assertEqual(processed_data['grass_pollen'], 10)
        self.assertEqual(processed_data['tree_pollen'], 50)
        self.assertEqual(processed_data['weed_pollen'], 5)
        self.assertEqual(processed_data['grass_pollen_risk'], "Low")
        self.assertEqual(processed_data['tree_pollen_risk'], "Moderate")


class TestEndToEndExecution(unittest.TestCase):
    """Test end-to-end execution of the main application"""

    @patch('subprocess.run')
    def test_main_automated_only(self, mock_run):
        """Test running main.py with --automated-only flag"""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Override sys.argv to include the flag
        original_argv = sys.argv
        sys.argv = ['main.py', '--automated-only']

        try:
            # Import and run main function
            from main import main
            result = main()
            self.assertEqual(result, 0)

            # Check that run was called for each automated script
            self.assertEqual(mock_run.call_count, len(config.AUTOMATED_SCRIPTS))
        finally:
            # Restore original argv
            sys.argv = original_argv


class TestFilenameCorrection(unittest.TestCase):
    """Test to ensure we're using the correct filenames (especially environment.py vs enviroment.py)"""

    def test_environment_filename(self):
        """Test that the environment script filename is used consistently"""
        # Check which file exists
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'environment.py')
        env_alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'enviroment.py')

        if os.path.exists(env_path):
            correct_name = 'environment.py'
        elif os.path.exists(env_alt_path):
            correct_name = 'enviroment.py'
        else:
            self.fail("Neither environment.py nor enviroment.py exists")

        # Check that the correct name is used in config
        self.assertIn(correct_name, config.AUTOMATED_SCRIPTS,
                      f"Config uses incorrect environment script name, should be {correct_name}")


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and relationships between tables"""

    def setUp(self):
        try:
            self.conn = pyodbc.connect(config.DB_CONNECTION)
            self.cursor = self.conn.cursor()
        except Exception as e:
            self.fail(f"Failed to connect to database: {e}")

    def tearDown(self):
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_workout_environment_relationship(self):
        """Test relationship between Workouts and EnvironmentData"""
        # Find a workout that has environment data
        self.cursor.execute("""
            SELECT w.WorkoutID 
            FROM Workouts w
            JOIN EnvironmentData e ON w.WorkoutID = e.WorkoutID
            WHERE w.UserID = ?
            LIMIT 1
        """, (config.DEFAULT_USER_ID,))

        result = self.cursor.fetchone()
        if result:
            workout_id = result[0]

            # Verify we can retrieve both workout and its environment data
            self.cursor.execute("SELECT * FROM Workouts WHERE WorkoutID = ?", (workout_id,))
            workout = self.cursor.fetchone()

            self.cursor.execute("SELECT * FROM EnvironmentData WHERE WorkoutID = ?", (workout_id,))
            env_data = self.cursor.fetchone()

            self.assertIsNotNone(workout, "Failed to retrieve workout")
            self.assertIsNotNone(env_data, "Failed to retrieve environment data")
        else:
            self.skipTest("No workout with environment data found for testing relationship")

    def test_user_sleep_relationship(self):
        """Test relationship between Users and SleepSessions"""
        # Verify we can find sleep sessions for the default user
        self.cursor.execute("""
            SELECT COUNT(*) 
            FROM SleepSessions
            WHERE UserID = ?
        """, (config.DEFAULT_USER_ID,))

        count = self.cursor.fetchone()[0]
        self.assertGreaterEqual(count, 0, "Failed to query sleep sessions for default user")


def main():
    unittest.main()


if __name__ == '__main__':
    main()