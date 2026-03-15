from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Training load / history
# ---------------------------------------------------------------------------

class TrainingHistoryPointSchema(BaseModel):
    date: date
    load: float
    ctl: float
    atl: float
    tsb: float


class HRVHistoryPointSchema(BaseModel):
    date: date
    hrv: float
    baseline: float
    rhr: int | None
    sleep_score: float | None


class WeeklyVolumeSchema(BaseModel):
    week_start: date
    training_days: int
    total_sets: int


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

class WorkoutListItemSchema(BaseModel):
    workout_id: int
    workout_date: date
    sport: str
    workout_type: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_s: float | None                  # derived from end_time - start_time
    distance_m: float | None                  # training_volume column
    avg_hr: int | None
    max_hr: int | None
    calories: int | None
    tss: float | None                         # training_stress_score


class WorkoutMetricPointSchema(BaseModel):
    metric_timestamp: datetime | None
    heart_rate: int | None
    pace: float | None                        # min/km
    cadence: float | None
    vertical_oscillation: float | None        # mm
    vertical_ratio: float | None              # %
    ground_contact_time: float | None         # ms
    power: float | None                       # watts
    latitude: float | None
    longitude: float | None
    altitude: float | None                    # metres
    distance: float | None                    # cumulative metres
    gradient_pct: float | None


class WorkoutDetailSchema(BaseModel):
    workout_id: int
    workout_date: date
    sport: str
    workout_type: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_s: float | None
    distance_m: float | None                  # training_volume
    avg_hr: int | None
    max_hr: int | None
    calories: int | None
    vo2max: float | None                      # vo2max_estimate
    lactate_threshold: int | None             # lactate_threshold_bpm
    z1: int | None                            # time_in_hr_zone_1 (seconds)
    z2: int | None
    z3: int | None
    z4: int | None
    z5: int | None
    elev_gain: float | None                   # elevation_gain
    elev_loss: float | None                   # elevation_loss
    aerobic_te: float | None                  # aerobic_training_effect
    anaerobic_te: float | None                # anaerobic_training_effect
    tss: float | None                         # training_stress_score
    norm_power: float | None                  # normalized_power
    avg_power: float | None
    max_power: float | None
    avg_cadence: float | None                 # avg_running_cadence
    max_cadence: float | None                 # max_running_cadence
    avg_gct: float | None                     # avg_ground_contact_time
    avg_vo: float | None                      # avg_vertical_oscillation
    avg_stride: float | None                  # avg_stride_length
    avg_vr: float | None                      # avg_vertical_ratio
    total_steps: int | None
    location: str | None
    lat: float | None                         # start_latitude
    lon: float | None                         # start_longitude
    metrics: list[WorkoutMetricPointSchema]
