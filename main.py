import subprocess
import sys
import time
import logging
import os
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

    # Identify which scripts are interactive (require user input)
    interactive_scripts = ["daily_subjective.py", "injuries.py", "nutrition.py"]

    if script_name in interactive_scripts:
        logger.info(f"{script_name} is interactive - running in interactive mode")
        try:
            # Run interactive script without capturing stdout/stderr
            # This allows it to interact directly with the console
            process = subprocess.Popen(
                [sys.executable, script_name],
                # Don't redirect stdin/stdout/stderr
                stdin=None,  # Use parent's stdin
                stdout=None,  # Output directly to console
                stderr=None  # Error directly to console
            )

            # Wait for the process to complete
            logger.info(f"Waiting for {script_name} to complete...")
            return_code = process.wait()

            if return_code == 0:
                logger.info(f"{script_name} completed successfully with return code {return_code}")
                return True
            else:
                logger.error(f"{script_name} failed with return code {return_code}")
                return False

        except Exception as e:
            logger.error(f"Error running {script_name}: {e}")
            return False
    else:
        # For non-interactive scripts, run with output capture
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

    # Get list of scripts to run
    scripts_to_run = [
        "workout.py",
        "sleep.py",
        "enviroment.py",
        "daily_subjective.py",
        "injuries.py"
    ]

    # Add nutrition.py if it exists
    if os.path.exists("nutrition.py"):
        scripts_to_run.append("nutrition.py")

    # Track success/failure of each script
    results = {}

    # Run each script
    for script in scripts_to_run:
        success = run_script(script)
        results[script] = success

        if success:
            logger.info(f"{script} completed successfully")
        else:
            logger.warning(f"{script} failed")

    # Summary
    logger.info("===== QuantifiedStrides data collection complete =====")
    success_count = sum(results.values())
    total_scripts = len(scripts_to_run)
    logger.info(f"Successfully ran {success_count}/{total_scripts} scripts")

    # List any failed scripts
    failed_scripts = [script for script, success in results.items() if not success]
    if failed_scripts:
        logger.warning(f"Failed scripts: {', '.join(failed_scripts)}")


if __name__ == "__main__":
    main()