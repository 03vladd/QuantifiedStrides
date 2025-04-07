import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import datetime
import logging

# Add project directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("QuantifiedStridesTest")


class IntegrationTest(unittest.TestCase):
    """Integration test for the full QuantifiedStrides workflow"""

    @patch('garminconnect.Garmin')
    @patch('pyodbc.connect')
    @patch('requests.get')
    def test_end_to_end_workflow(self, mock_requests, mock_db_connect, mock_garmin):
        """
        Test the complete data collection workflow in sequence
        simulating a real-world scenario
        """
        logger.info("=== Starting End-to-End Integration Test ===")

        # --- Step 1: Set up all the mocks ---
        logger.info("Setting up test environment and mocks...")

        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_conn

        # Mock Garmin client
        mock_client = MagicMock()
        mock_garmin.return_value = mock_client

        # Set up test date
        test_date = datetime.datetime.now().date()
        test_date_str = test_date.strftime(config.DATE_FORMAT)

        # --- Step 2: Test workout.py execution ---
        logger.info("Testing workout.py execution...")

        # Mock Garmin activities
        mock_activity = {
            "activityType": {"typeKey": "running"},
            "activityName": "Morning Run",
            "startTimeLocal": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "duration": 3600,  # 1 hour in seconds
            "calories": 500,
            "averageHR": 140,
            "maxHR": 175,
            "distance": 10.0,  # 10 km
            "locationName": config.DEFAULT_LOCATION["name"]
        }
        mock_client.get_activities.return_value = [mock_activity]

        # Mock cursor for workout checks
        mock_cursor.fetchone.return_value = None  # No existing workout

        # Import and run workout.py functionality
        from workout import main as workout_main
        with patch('sys.exit'):  # Prevent actual system exit
            workout_result = workout_main()

        self.assertEqual(workout_result, 0, "workout.py execution failed")

        # --- Step 3: Test sleep.py execution ---
        logger.info("Testing sleep.py execution...")

        # Mock sleep data
        mock_sleep_data = {
            "deepSleepSeconds": 7200,  # 2 hours
            "lightSleepSeconds": 10800,  # 3 hours
            "remSleepSeconds": 5400,  # 1.5 hours
            "awakeSleepSeconds": 1800,  # 0.5 hours
            "sleepScore": 85,
            "avgOvernightHrv": 65,
            "restingHeartRate": 55,
            "avgSleepStress": 25,
            "sleepScoreFeedback": "Good sleep quality",
            "sleepScoreInsight": "Your sleep was restorative",
            "hrvStatus": "balanced",
            "bodyBatteryChange": 55
        }
        mock_client.get_sleep_data.return_value = mock_sleep_data

        # Reset cursor mock for sleep checks
        mock_cursor.fetchone.return_value = None  # No existing sleep data

        # Import and run sleep.py functionality
        from sleep import main as sleep_main
        with patch('sys.exit'):  # Prevent actual system exit
            sleep_result = sleep_main()

        self.assertEqual(sleep_result, 0, "sleep.py execution failed")

        # --- Step 4: Test environment.py execution ---
        logger.info("Testing environment.py execution...")

        # Mock workout search
        mock_cursor.fetchone.side_effect = [
            (1, config.DEFAULT_LOCATION["name"], False),  # Return workout ID, location, is_indoor
            None,  # No existing environment data
            None  # For other queries
        ]

        # Mock weather API response
        mock_weather_response = MagicMock()
        mock_weather_response.status_code = 200
        mock_weather_response.json.return_value = {
            "main": {"temp": 15.5, "humidity": 65},
            "wind": {"speed": 3.5, "deg": 180},
            "name": config.DEFAULT_LOCATION["name"]
        }

        # Mock UV API response
        mock_uv_response = MagicMock()
        mock_uv_response.status_code = 200
        mock_uv_response.json.return_value = {
            "current": {"uvi": 4.2}
        }

        # Mock pollen API response
        mock_pollen_response = MagicMock()
        mock_pollen_response.status_code = 200
        mock_pollen_response.json.return_value = {
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

        # Set up the mock requests to return different responses
        mock_requests.side_effect = [
            mock_weather_response,
            mock_uv_response,
            mock_pollen_response
        ]

        # Import and run environment.py functionality
        # Note: using the correct filename based on your codebase
        try:
            from enviroment import main as environment_main
            env_module_name = 'enviroment'
        except ImportError:
            try:
                from environment import main as environment_main
                env_module_name = 'environment'
            except ImportError:
                self.fail("Could not import either environment.py or enviroment.py")

        logger.info(f"Using {env_module_name}.py module")
        with patch('sys.exit'):  # Prevent actual system exit
            environment_result = environment_main()

        self.assertEqual(environment_result, 0, f"{env_module_name}.py execution failed")

        # --- Step 5: Main script execution simulation ---
        logger.info("Testing main.py orchestration...")

        # Simulate main.py execution with automated scripts only
        with patch('subprocess.run') as mock_run:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = "Test output"
            mock_run.return_value = mock_process

            # Import and run main functionality
            from main import main as main_func
            with patch('sys.argv', ['main.py', '--automated-only']):
                main_result = main_func()

            self.assertEqual(main_result, 0, "main.py execution failed")

            # Verify each automated script was called
            self.assertEqual(
                mock_run.call_count,
                len(config.AUTOMATED_SCRIPTS),
                f"Expected {len(config.AUTOMATED_SCRIPTS)} script calls, got {mock_run.call_count}"
            )

        logger.info("=== End-to-End Integration Test Completed Successfully ===")


def main():
    unittest.main()


if __name__ == '__main__':
    main()