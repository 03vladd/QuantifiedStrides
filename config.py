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
# Garmin Connect API
GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL", "vasiuvlad984@gmail.com")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD", "Mariguanas1")

# OpenWeatherMap API
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "819ff67a3fe8e6af5f825bb2688729d9")

# Ambee API (Pollen data)
AMBEE_API_KEY = os.environ.get("AMBEE_API_KEY", "18659f688d4744d922beeb2bb44df415532241b138fe8ca07cae8b387009cd2b")

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