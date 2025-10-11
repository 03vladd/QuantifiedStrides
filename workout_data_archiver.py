"""
Workout Data Archiver for QuantifiedStrides

Save this file as: workout_data_archiver.py in your project root directory

This module handles archiving raw JSON workout data from Garmin Connect
for future ML model training and analysis.
"""

from datetime import datetime, timedelta
import json
import os
import hashlib
import logging
import garminconnect
import config

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("workout_archiver")


class WorkoutArchiver:
    """Handles archiving of workout data in JSON format"""

    def __init__(self, base_path="data/workouts"):
        """
        Initialize the archiver

        Args:
            base_path: Base directory for storing workout data
        """
        self.base_path = base_path
        self.raw_path = os.path.join(base_path, "raw")
        self.processed_path = os.path.join(base_path, "processed")
        self.metadata_path = os.path.join(base_path, "metadata")

        # Create directory structure
        self._setup_directories()

    def _setup_directories(self):
        """Create necessary directory structure"""
        directories = [
            self.raw_path,
            self.processed_path,
            self.metadata_path,
            os.path.join(self.raw_path, "activities"),
            os.path.join(self.raw_path, "details"),
            os.path.join(self.raw_path, "metrics"),
            os.path.join(self.raw_path, "hr_zones")
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")

    def _generate_file_id(self, activity_id, data_type, timestamp=None):
        """
        Generate a unique file ID

        Args:
            activity_id: Garmin activity ID
            data_type: Type of data (activity, details, metrics, hr_zones)
            timestamp: Optional timestamp for versioning

        Returns:
            Unique file identifier
        """
        if timestamp is None:
            timestamp = datetime.now()

        date_str = timestamp.strftime("%Y%m%d")
        time_str = timestamp.strftime("%H%M%S")

        return f"{date_str}_{activity_id}_{data_type}_{time_str}"

    def _calculate_checksum(self, data):
        """Calculate MD5 checksum of data"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def save_activity(self, activity, timestamp=None):
        """
        Save raw activity data

        Args:
            activity: Activity dictionary from Garmin
            timestamp: Optional timestamp for file naming

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now()

        activity_id = activity.get("activityId")
        if not activity_id:
            logger.error("Activity missing activityId, cannot save")
            return None

        # Generate file path
        file_id = self._generate_file_id(activity_id, "activity", timestamp)
        file_path = os.path.join(self.raw_path, "activities", f"{file_id}.json")

        # Add metadata
        activity_with_meta = {
            "archived_at": timestamp.isoformat(),
            "activity_id": activity_id,
            "data_type": "activity",
            "checksum": self._calculate_checksum(activity),
            "data": activity
        }

        # Save to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(activity_with_meta, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved activity {activity_id} to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving activity {activity_id}: {e}")
            return None

    def save_activity_details(self, activity_id, details, timestamp=None):
        """Save detailed activity metrics"""
        if timestamp is None:
            timestamp = datetime.now()

        file_id = self._generate_file_id(activity_id, "details", timestamp)
        file_path = os.path.join(self.raw_path, "details", f"{file_id}.json")

        details_with_meta = {
            "archived_at": timestamp.isoformat(),
            "activity_id": activity_id,
            "data_type": "details",
            "checksum": self._calculate_checksum(details),
            "data": details
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(details_with_meta, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved details for activity {activity_id} to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving details for {activity_id}: {e}")
            return None

    def save_hr_zones(self, activity_id, hr_data, timestamp=None):
        """Save heart rate zone data"""
        if timestamp is None:
            timestamp = datetime.now()

        file_id = self._generate_file_id(activity_id, "hr_zones", timestamp)
        file_path = os.path.join(self.raw_path, "hr_zones", f"{file_id}.json")

        hr_with_meta = {
            "archived_at": timestamp.isoformat(),
            "activity_id": activity_id,
            "data_type": "hr_zones",
            "checksum": self._calculate_checksum(hr_data),
            "data": hr_data
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(hr_with_meta, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved HR zones for activity {activity_id} to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving HR zones for {activity_id}: {e}")
            return None

    def save_catalog_entry(self, activity_id, file_paths, activity_summary):
        """
        Save a catalog entry linking all files for an activity

        Args:
            activity_id: Garmin activity ID
            file_paths: Dictionary of file paths for this activity
            activity_summary: Summary info about the activity
        """
        catalog_file = os.path.join(self.metadata_path, "catalog.jsonl")

        entry = {
            "activity_id": activity_id,
            "cataloged_at": datetime.now().isoformat(),
            "files": file_paths,
            "summary": activity_summary
        }

        try:
            # Append to catalog (JSONL format - one JSON object per line)
            with open(catalog_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, default=str) + '\n')

            logger.info(f"Added catalog entry for activity {activity_id}")
        except Exception as e:
            logger.error(f"Error adding catalog entry: {e}")

    def archive_activity_complete(self, client, activity):
        """
        Archive complete activity data including all details

        Args:
            client: Garmin Connect client
            activity: Activity dictionary

        Returns:
            Dictionary with paths to all saved files
        """
        activity_id = activity.get("activityId")
        if not activity_id:
            logger.error("Activity missing activityId")
            return None

        timestamp = datetime.now()
        saved_files = {}

        # Save main activity data
        activity_path = self.save_activity(activity, timestamp)
        if activity_path:
            saved_files['activity'] = activity_path

        # Try to get and save detailed metrics
        try:
            details = client.get_activity_details(activity_id)
            if details:
                details_path = self.save_activity_details(activity_id, details, timestamp)
                if details_path:
                    saved_files['details'] = details_path
        except Exception as e:
            logger.warning(f"Could not fetch details for {activity_id}: {e}")

        # Try to get and save HR zones
        try:
            hr_data = client.get_activity_hr_in_timezones(activity_id)
            if hr_data:
                hr_path = self.save_hr_zones(activity_id, hr_data, timestamp)
                if hr_path:
                    saved_files['hr_zones'] = hr_path
        except Exception as e:
            logger.warning(f"Could not fetch HR zones for {activity_id}: {e}")

        # Create summary for catalog
        activity_summary = {
            "activity_name": activity.get("activityName"),
            "activity_type": activity.get("activityType", {}).get("typeKey") if isinstance(activity.get("activityType"),
                                                                                           dict) else activity.get(
                "activityType"),
            "start_time": activity.get("startTimeLocal"),
            "duration": activity.get("duration"),
            "distance": activity.get("distance"),
            "calories": activity.get("calories")
        }

        # Add to catalog
        self.save_catalog_entry(activity_id, saved_files, activity_summary)

        return saved_files

    def load_catalog(self):
        """Load the complete catalog of archived activities"""
        catalog_file = os.path.join(self.metadata_path, "catalog.jsonl")

        if not os.path.exists(catalog_file):
            return []

        catalog = []
        try:
            with open(catalog_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        catalog.append(json.loads(line))

            logger.info(f"Loaded catalog with {len(catalog)} entries")
            return catalog
        except Exception as e:
            logger.error(f"Error loading catalog: {e}")
            return []

    def get_archived_activity_ids(self):
        """Get set of all archived activity IDs"""
        catalog = self.load_catalog()
        return set(entry['activity_id'] for entry in catalog)


if __name__ == "__main__":
    print("This module should be imported, not run directly.")
    print("Example usage:")
    print("  from workout_data_archiver import WorkoutArchiver")
    print("  archiver = WorkoutArchiver()")