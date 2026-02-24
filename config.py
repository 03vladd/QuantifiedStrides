"""
Configuration settings for QuantifiedStrides

This file contains all configuration settings for the application.
For security, API keys and credentials should be stored as environment variables.
"""

import os
from datetime import datetime

# Application settings
APP_NAME = "QuantifiedStrides"
VERSION = "1.0.1"
DEFAULT_USER_ID = 1

# Database settings
DB_CONNECTION = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=QuantifiedStridesDB;Trusted_Connection=yes;"

# API credentials
# All credentials must be set as environment variables. No default values are
# provided here intentionally - hardcoded credentials in source code are a
# security risk (CWE-798). Set these before running the application:
#
#   export GARMIN_EMAIL="your@email.com"
#   export GARMIN_PASSWORD="yourpassword"
#   export OPENWEATHER_API_KEY="your_key"
#   export AMBEE_API_KEY="your_key"
#
# Or create a .env file and load it with python-dotenv (not included in repo).

# Garmin Connect API
GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")

# OpenWeatherMap API
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

# Ambee API (Pollen data)
AMBEE_API_KEY = os.environ.get("AMBEE_API_KEY")

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
LOG_FILE = "quantified_strides.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Scripts
AUTOMATED_SCRIPTS = ["workout.py", "sleep.py", "environment.py"]
INTERACTIVE_SCRIPTS = ["daily_subjective.py", "injuries.py", "nutrition.py"]