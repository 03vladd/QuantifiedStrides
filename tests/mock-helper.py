#!/usr/bin/env python3
"""
QuantifiedStrides Test Mock Helpers

This module contains helper functions for creating mock objects and test data
for the QuantifiedStrides test suite.
"""

import datetime
import json
from unittest.mock import MagicMock


def create_mock_garmin_client():
    """Create a mock Garmin Connect client for testing"""

    mock_client = MagicMock()

    # Set up activities data
    mock_activities = [
        {
            "activityId": 1001,
            "activityType": {"typeKey": "running", "typeId": 1},
            "activityName": "Morning Run",
            "startTimeLocal": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "duration": 3600,  # 1 hour in seconds
            "calories": 500,
            "averageHR": 140,
            "maxHR": 175,
            "vO2MaxValue": 52.5,
            "lactateThresholdBpm": 165,
            "hrTimeInZone_1": 600,  # 10 min
            "hrTimeInZone_2": 1200,  # 20 min
            "hrTimeInZone_3": 1500,  # 25 min
            "hrTimeInZone_4": 300,  # 5 min
            "hrTimeInZone_5": 0,
            "distance": 10000,  # 10 km in meters
            "averageRunningCadenceInStepsPerMinute": 175,
            "maxRunningCadenceInStepsPerMinute": 185,
            "avgVerticalOscillation": 9.5,
            "avgGroundContactTime": 235,
            "avgStrideLength": 1.15,
            "avgVerticalRatio": 7.2,
            "locationName": "City Park"
        },
        {
            "activityId": 1002,
            "activityType": {"typeKey": "cycling", "typeId": 2},
            "activityName": "Evening Ride",
            "startTimeLocal": (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            "duration": 5400,  # 1.5 hours in seconds
            "calories": 750,
            "averageHR": 135,
            "maxHR": 165,
            "vO2MaxValue": 51.0,
            "lactateThresholdBpm": 160,
            "hrTimeInZone_1": 1200,  # 20 min
            "hrTimeInZone_2": 2400,  # 40 min
            "hrTimeInZone_3": 1800,  # 30 min
            "hrTimeInZone_4": 0,
            "hrTimeInZone_5": 0,
            "distance": 30000,  # 30 km in meters
            "locationName": "Country Road"
        }
    ]

    # Set up sleep data
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

    # Configure the mock client
    mock_client.login.return_value = True
    mock_client.get_activities.return_value = mock_activities
    mock_client.get_sleep_data.return_value = mock_sleep_data

    return mock_client


def create_mock_api_responses():
    """Create mock API responses for testing"""

    # Weather API response
    weather_response = MagicMock()
    weather_response.status_code = 200
    weather_response.json.return_value = {
        "coord": {"lon": 23.6, "lat": 46.77},
        "weather": [
            {
                "id": 800,
                "main": "Clear",
                "description": "clear sky",
                "icon": "01d"
            }
        ],
        "base": "stations",
        "main": {
            "temp": 15.5,
            "feels_like": 14.8,
            "temp_min": 14.2,
            "temp_max": 16.7,
            "pressure": 1018,
            "humidity": 65
        },
        "visibility": 10000,
        "wind": {
            "speed": 3.5,
            "deg": 180
        },
        "clouds": {
            "all": 0
        },
        "dt": int(datetime.datetime.now().timestamp()),
        "sys": {
            "type": 2,
            "id": 2032717,
            "country": "RO",
            "sunrise": int((datetime.datetime.now() - datetime.timedelta(hours=6)).timestamp()),
            "sunset": int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp())
        },
        "timezone": 10800,
        "id": 681290,
        "name": "Cluj-Napoca",
        "cod": 200
    }

    # UV API response
    uv_response = MagicMock()
    uv_response.status_code = 200
    uv_response.json.return_value = {
        "lat": 46.77,
        "lon": 23.6,
        "timezone": "Europe/Bucharest",
        "timezone_offset": 10800,
        "current": {
            "dt": int(datetime.datetime.now().timestamp()),
            "sunrise": int((datetime.datetime.now() - datetime.timedelta(hours=6)).timestamp()),
            "sunset": int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp()),
            "temp": 15.5,
            "feels_like": 14.8,
            "pressure": 1018,
            "humidity": 65,
            "dew_point": 9.1,
            "uvi": 4.2,
            "clouds": 0,
            "visibility": 10000,
            "wind_speed": 3.5,
            "wind_deg": 180,
            "weather": [
                {
                    "id": 800,
                    "main": "Clear",
                    "description": "clear sky",
                    "icon": "01d"
                }
            ]
        }
    }

    # Pollen API response
    pollen_response = MagicMock()
    pollen_response.status_code = 200
    pollen_response.json.return_value = {
        "message": "success",
        "lat": 46.77,
        "lng": 23.6,
        "data": [
            {
                "timezone": "Europe/Bucharest",
                "Species": {
                    "Grass": {"Grass / Poaceae": 5},
                    "Others": 4,
                    "Tree": {
                        "Alder": 18,
                        "Birch": 85,
                        "Cypress": 52,
                        "Elm": 21,
                        "Hazel": 6,
                        "Oak": 33,
                        "Pine": 3,
                        "Plane": 24,
                        "Poplar / Cottonwood": 61
                    },
                    "Weed": {
                        "Chenopod": 0,
                        "Mugwort": 0,
                        "Nettle": 0,
                        "Ragweed": 0
                    }
                },
                "Risk": {
                    "grass_pollen": "Low",
                    "tree_pollen": "High",
                    "weed_pollen": "Low"
                },
                "Count": {
                    "grass_pollen": 5,
                    "tree_pollen": 303,
                    "weed_pollen": 0
                },
                "updatedAt": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        ]
    }

    return {
        "weather": weather_response,
        "uv": uv_response,
        "pollen": pollen_response
    }


def create_mock_database():
    """Create a mock database connection and cursor"""

    # Create mock cursor with realistic behavior
    mock_cursor = MagicMock()

    # Mock database table structure
    table_columns = {
        "Users": ["UserID", "Name", "DateOfBirth"],
        "Workouts": [
            "WorkoutID", "UserID", "Sport", "StartTime", "EndTime", "WorkoutType",
            "CaloriesBurned", "AvgHeartRate", "MaxHeartRate", "VO2MaxEstimate",
            "LactateThresholdBpm", "TimeInHRZone1", "TimeInHRZone2", "TimeInHRZone3",
            "TimeInHRZone4", "TimeInHRZone5", "TrainingVolume", "AvgVerticalOscillation",
            "AvgGroundContactTime", "AvgStrideLength", "AvgVerticalRatio",
            "AverageRunningCadence", "MaxRunningCadence", "Location", "WorkoutDate", "IsIndoor"
        ],
        "SleepSessions": [
            "SleepID", "UserID", "SleepDate", "DurationMinutes", "SleepScore", "HRV",
            "RHR", "TimeInDeep", "TimeInLight", "TimeInRem", "TimeAwake", "AvgSleepStress",
            "SleepScoreFeedback", "SleepScoreInsight", "OvernightHRV", "HRVStatus", "BodyBatteryChange"
        ],
        "EnvironmentData": [
            "EnvID", "WorkoutID", "RecordDateTime", "Location", "Temperature", "WindSpeed",
            "WindDirection", "Humidity", "Precipitation", "TotalPollenIndex", "UVIndex",
            "SubjectiveNotes", "GrassPollen", "TreePollen", "WeedPollen", "GrassPollenRisk",
            "TreePollenRisk", "WeedPollenRisk", "PollenIndex"
        ],
        "DailySubjective": [
            "SubjectiveID", "UserID", "EntryDate", "EnergyLevel", "Mood", "RPE",
            "Soreness", "EnoughFood", "Recovery", "Reflection"
        ],
        "Injuries": [
            "InjuryID", "UserID", "StartDate", "EndDate", "InjuryType", "Severity", "Notes"
        ],
        "NutritionLog": [
            "NutritionID", "UserID", "IngestionTime", "FoodType", "TotalCalories",
            "MacrosCarbs", "MacrosProtein", "MacrosFat", "Supplements"
        ],
        "WorkoutMetrics": [
            "MetricID", "WorkoutID", "MetricTimestamp", "HeartRate", "Pace", "Cadence",
            "VerticalOscillation", "VerticalRatio", "GroundContactTime", "Power"
        ],
        "INFORMATION_SCHEMA.COLUMNS": [
            "TABLE_CATALOG", "TABLE_SCHEMA", "TABLE_NAME", "COLUMN_NAME", "ORDINAL_POSITION",
            "COLUMN_DEFAULT", "IS_NULLABLE", "DATA_TYPE", "CHARACTER_MAXIMUM_LENGTH",
            "CHARACTER_OCTET_LENGTH", "NUMERIC_PRECISION", "NUMERIC_PRECISION_RADIX",
            "NUMERIC_SCALE", "DATETIME_PRECISION", "CHARACTER_SET_CATALOG",
            "CHARACTER_SET_SCHEMA", "CHARACTER_SET_NAME", "COLLATION_CATALOG",
            "COLLATION_SCHEMA", "COLLATION_NAME", "DOMAIN_CATALOG", "DOMAIN_SCHEMA",
            "DOMAIN_NAME", "DESCRIPTION"
        ]
    }

    # Mock data for INFORMATION_SCHEMA.COLUMNS
    info_schema_data = [
        # IsIndoor column in Workouts table
        {
            "TABLE_NAME": "Workouts",
            "COLUMN_NAME": "IsIndoor",
            "DATA_TYPE": "bit",
            "IS_NULLABLE": "YES"
        }
    ]

    # Function to handle SQL queries
    def execute_mock(query, params=None):
        # Handle information schema query for IsIndoor column
        if "INFORMATION_SCHEMA.COLUMNS" in query and "IsIndoor" in query:
            mock_cursor.fetchone.return_value = info_schema_data[0]

        # Mock empty result for most queries
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        # When checking for today's workout
        if "Workouts" in query and "WorkoutDate" in query:
            # Mock a workout row: WorkoutID, Location, IsIndoor
            mock_cursor.fetchone.return_value = (1003, "Cluj-Napoca", 0)

    # Configure the mock cursor
    mock_cursor.execute.side_effect = execute_mock
    mock_cursor.description = [("column",)]

    # Create the mock connection
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    return mock_conn, mock_cursor


if __name__ == "__main__":
    print("This module is intended to be imported, not run directly.")