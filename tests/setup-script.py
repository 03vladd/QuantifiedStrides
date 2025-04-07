#!/usr/bin/env python3
"""
QuantifiedStrides Test Suite Runner

This script sets up and runs the test suite for the QuantifiedStrides application.
It handles test discovery, environment setup, and reports results.

Usage:
    python run_tests.py               # Run all tests
    python run_tests.py --skip-setup  # Skip environment setup
    python run_tests.py --test-file integration_test.py  # Run specific test file
    python run_tests.py --integration-only  # Run only integration tests
    python run_tests.py --unit-only  # Run only unit tests
"""

import os
import sys
import unittest
import argparse
import logging
import json
import importlib.util
from datetime import datetime

# Try to import config, if it fails, we'll create a dummy one for testing
try:
    import config

    CONFIG_EXISTS = True
except ImportError:
    CONFIG_EXISTS = False
    print("Warning: config.py not found, using test defaults")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_results.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("TestRunner")


def create_test_config():
    """Create a temporary test config if the real one doesn't exist"""
    config_path = os.path.join(os.path.dirname(__file__), "test_config.py")

    with open(config_path, "w") as f:
        f.write("""
# Test configuration for QuantifiedStrides
APP_NAME = "QuantifiedStrides"
VERSION = "1.0.1-test"
DEFAULT_USER_ID = 1

# Test database connection string
DB_CONNECTION = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=QuantifiedStridesTest;Trusted_Connection=yes;"

# Test API credentials
GARMIN_EMAIL = "test@example.com"
GARMIN_PASSWORD = "test_password"
OPENWEATHER_API_KEY = "test_key"
AMBEE_API_KEY = "test_key"

# Default location (Cluj-Napoca)
DEFAULT_LOCATION = {
    "name": "Cluj-Napoca",
    "lat": 46.7667,
    "lon": 23.6000,
    "timezone": "Europe/Bucharest"
}

# Sport types
SPORT_TYPES = {
    "running": "Run",
    "cycling": "Cycling",
    "swimming": "Swimming",
    "strength_training": "Strength Training",
    "other": "Other"
}

# Indoor activities keywords
INDOOR_KEYWORDS = [
    'indoor',
    'treadmill',
    'stationary',
    'trainer',
    'gym',
    'strength',
    'pool',
    'home'
]

# Date and time settings
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Logging settings
LOG_FILE = "test_quantified_strides.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Scripts
AUTOMATED_SCRIPTS = ["workout.py", "sleep.py", "enviroment.py"]
INTERACTIVE_SCRIPTS = ["daily_subjective.py", "injuries.py", "nutrition.py"]
""")

    # Dynamically load the test config
    spec = importlib.util.spec_from_file_location("test_config", config_path)
    test_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_config)
    sys.modules["config"] = test_config

    return test_config


def setup_test_environment():
    """Set up the test environment"""
    logger.info("Setting up test environment...")

    # Create test directory if it doesn't exist
    test_dir = os.path.join(os.path.dirname(__file__), "tests")
    os.makedirs(test_dir, exist_ok=True)

    # Create an __init__.py file to make it a proper package
    init_path = os.path.join(test_dir, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("# QuantifiedStrides Test Package")

    # Copy the test files to the test directory if they don't exist
    test_files = ["test_suite.py", "integration_test.py"]

    for file in test_files:
        target_path = os.path.join(test_dir, file)
        if not os.path.exists(target_path):
            # Determine source path based on current script location
            source_path = os.path.join(os.path.dirname(__file__), file)

            if os.path.exists(source_path):
                with open(source_path, "r") as src, open(target_path, "w") as dst:
                    dst.write(src.read())
                logger.info(f"Copied {file} to test directory")
            else:
                logger.warning(f"Source file {file} not found, skipping")

    # Check config
    if not CONFIG_EXISTS:
        test_config = create_test_config()
        logger.info("Created test config")

    logger.info("Test environment setup complete")


def run_tests(args):
    """Run the test suite"""
    logger.info("Starting test execution...")

    # Start timing
    start_time = datetime.now()

    # Discover and run tests
    loader = unittest.TestLoader()
    test_dir = os.path.join(os.path.dirname(__file__), "tests")

    if args.test_file:
        # Run specific test file
        test_path = os.path.join(test_dir, args.test_file)
        if os.path.exists(test_path):
            suite = loader.discover(os.path.dirname(test_path), pattern=os.path.basename(test_path))
        else:
            logger.error(f"Test file not found: {args.test_file}")
            return 1
    elif args.integration_only:
        # Run only integration tests
        integration_pattern = "*integration_test*.py"
        logger.info(f"Running only integration tests (pattern: {integration_pattern})")
        suite = loader.discover(test_dir, pattern=integration_pattern)
    elif args.unit_only:
        # Run only unit tests - exclude integration tests
        logger.info("Running only unit tests")
        suite = loader.discover(test_dir)

        # Filter out integration tests
        filtered_suite = unittest.TestSuite()
        for test_suite in suite:
            for test_case in test_suite:
                if "integration" not in test_case.id().lower():
                    filtered_suite.addTest(test_case)

        suite = filtered_suite
    else:
        # Run all tests
        suite = loader.discover(test_dir)

    # Set up result collection
    test_results = {}

    class JSONTestResult(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.results = {}

        def addSuccess(self, test):
            super().addSuccess(test)
            self.results[test.id()] = "PASS"

        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.results[test.id()] = "FAIL"

        def addError(self, test, err):
            super().addError(test, err)
            self.results[test.id()] = "ERROR"

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            self.results[test.id()] = "SKIP"

    # Create a test runner with the custom result class
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=JSONTestResult
    )

    # Run the tests
    result = runner.run(suite)

    # Store results
    test_results = result.results

    # End timing
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # Create a report
    report = {
        "timestamp": datetime.now().isoformat(),
        "execution_time": execution_time,
        "total_tests": result.testsRun,
        "passed": len([v for v in test_results.values() if v == "PASS"]),
        "failed": len([v for v in test_results.values() if v == "FAIL"]),
        "errors": len([v for v in test_results.values() if v == "ERROR"]),
        "skipped": len([v for v in test_results.values() if v == "SKIP"]),
        "details": test_results
    }

    # Save the report
    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # Log summary
    logger.info(f"Test execution completed in {execution_time:.2f} seconds")
    logger.info(f"Total tests: {report['total_tests']}")
    logger.info(f"Passed: {report['passed']}")
    logger.info(f"Failed: {report['failed']}")
    logger.info(f"Errors: {report['errors']}")
    logger.info(f"Skipped: {report['skipped']}")
    logger.info(f"Test report saved to test_report.json")

    return 0 if report['failed'] == 0 and report['errors'] == 0 else 1


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='QuantifiedStrides Test Runner')
    parser.add_argument('--test-file', type=str, help='Run a specific test file')
    parser.add_argument('--skip-setup', action='store_true', help='Skip test environment setup')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--integration-only', action='store_true', help='Run only integration tests')
    parser.add_argument('--unit-only', action='store_true', help='Run only unit tests')

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Setup test environment if needed
    if not args.skip_setup:
        setup_test_environment()
    else:
        logger.info("Skipping test environment setup")

    # Run tests
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())