import subprocess
import sys
import time
import logging
import os
from datetime import datetime
import argparse
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("QuantifiedStrides")


def run_script(script_name, interactive_mode=False):
    """Run a Python script and log its output"""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)

    # Check if script exists
    if not os.path.exists(script_path):
        logger.error(f"Script {script_name} not found at {script_path}")
        return False

    logger.info(f"Starting {script_name}")

    if interactive_mode:
        logger.info(f"{script_name} is interactive - running in interactive mode")
        try:
            # Run interactive script without capturing stdout/stderr
            # This allows it to interact directly with the console
            process = subprocess.Popen(
                [sys.executable, script_path],
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
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"{script_name} output: {result.stdout}")
            logger.info(f"{script_name} completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Error running {script_name}: {e}")
            logger.error(f"Script output: {e.stdout}")
            logger.error(f"Script error: {e.stderr}")
            return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='QuantifiedStrides Data Collection System')
    parser.add_argument('--automated-only', action='store_true', help='Run only automated scripts')
    parser.add_argument('--interactive-only', action='store_true', help='Run only interactive scripts')
    parser.add_argument('--script', type=str, help='Run a specific script')
    return parser.parse_args()


def main():
    """Main function to run all data collection scripts"""
    # Parse command line arguments
    args = parse_arguments()

    logger.info("===== Starting QuantifiedStrides data collection =====")
    logger.info(f"Current time: {datetime.now()}")

    # Determine which scripts to run based on arguments
    scripts_to_run = []

    if args.script:
        # Run a specific script
        if args.script in config.AUTOMATED_SCRIPTS + config.INTERACTIVE_SCRIPTS:
            scripts_to_run.append(args.script)
        else:
            logger.error(f"Unknown script: {args.script}")
            return 1
    elif args.automated_only:
        scripts_to_run = config.AUTOMATED_SCRIPTS
    elif args.interactive_only:
        scripts_to_run = config.INTERACTIVE_SCRIPTS
    else:
        # Run all scripts
        scripts_to_run = config.AUTOMATED_SCRIPTS + config.INTERACTIVE_SCRIPTS

    # Track success/failure of each script
    results = {}

    # Count scripts by category
    automated_count = sum(1 for script in scripts_to_run if script in config.AUTOMATED_SCRIPTS)
    interactive_count = sum(1 for script in scripts_to_run if script in config.INTERACTIVE_SCRIPTS)

    logger.info(
        f"Planning to run {len(scripts_to_run)} scripts ({automated_count} automated, {interactive_count} interactive)")

    # Run each script
    for script in scripts_to_run:
        is_interactive = script in config.INTERACTIVE_SCRIPTS
        success = run_script(script, interactive_mode=is_interactive)
        results[script] = success

    # Summary
    logger.info("===== QuantifiedStrides data collection complete =====")

    # Count successes by category
    automated_success = sum(1 for script in config.AUTOMATED_SCRIPTS if script in results and results[script])
    interactive_success = sum(1 for script in config.INTERACTIVE_SCRIPTS if script in results and results[script])

    # Report on automated scripts
    if automated_count > 0:
        logger.info(f"Successfully ran {automated_success}/{automated_count} automated scripts")

    # Report on interactive scripts
    if interactive_count > 0:
        logger.info(f"Successfully ran {interactive_success}/{interactive_count} interactive scripts")

    # List any failed scripts
    failed_scripts = [script for script, success in results.items() if not success]
    if failed_scripts:
        logger.warning(f"Failed scripts: {', '.join(failed_scripts)}")

    # List any skipped scripts (not run)
    all_scripts = config.AUTOMATED_SCRIPTS + config.INTERACTIVE_SCRIPTS
    skipped_scripts = [script for script in all_scripts if script not in scripts_to_run]
    if skipped_scripts:
        logger.info(f"Skipped scripts: {', '.join(skipped_scripts)}")

    # Return success status (0 for success, 1 for any failures)
    return 0 if not failed_scripts else 1


if __name__ == "__main__":
    exit(main())