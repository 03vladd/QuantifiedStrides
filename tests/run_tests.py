#!/usr/bin/env python3
"""
QuantifiedStrides Test Runner

This script discovers and runs all tests for the QuantifiedStrides platform.
Place this file in the root directory of your project.

Usage:
    python run_tests.py               # Run all tests
    python run_tests.py --unit-only   # Run only unit tests
    python run_tests.py --test-file database_agnostic_testing.py  # Run specific test file
"""

import os
import sys
import unittest
import argparse
import logging
import json
from datetime import datetime

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

    # Create a custom test runner with result collection
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
    parser.add_argument('--unit-only', action='store_true', help='Run only unit tests')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Setup test environment
    setup_test_environment()

    # Run tests
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())