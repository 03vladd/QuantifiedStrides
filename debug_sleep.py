"""Print raw Garmin sleep response for one day so we can see the actual field names."""
import json
import garminconnect
from config import GARMIN_EMAIL, GARMIN_PASSWORD

client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

data = client.get_sleep_data("2026-03-12")
print(json.dumps(data, indent=2))
