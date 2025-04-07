import subprocess
import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("quantified_strides.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("QuantifiedStrides")


def run_script(script_name):
    """Run a Python script and log its output"""
    logger.info(f"Starting {script_name}")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"{script_name} output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_name}: {e}")
        logger.error(f"Script output: {e.stdout}")
        logger.error(f"Script error: {e.stderr}")
        return False


def main():
    """Main function to run all data collection scripts"""
    logger.info("===== Starting QuantifiedStrides data collection =====")
    logger.info(f"Current time: {datetime.now()}")

    # 1. Run the workout data collection
    workout_success = run_script("workout.py")
    if workout_success:
        logger.info("Workout data collection completed successfully")
    else:
        logger.warning("Workout data collection failed")

    # 2. Run the sleep data collection
    sleep_success = run_script("sleep.py")
    if sleep_success:
        logger.info("Sleep data collection completed successfully")
    else:
        logger.warning("Sleep data collection failed")

    # 3. Run the environment data collection
    env_success = run_script("environment.py")
    if env_success:
        logger.info("Environment data collection completed successfully")
    else:
        logger.warning("Environment data collection failed")

    # Summary
    logger.info("===== QuantifiedStrides data collection complete =====")
    success_count = sum([workout_success, sleep_success, env_success])
    logger.info(f"Successfully ran {success_count}/3 scripts")


if __name__ == "__main__":
    main()