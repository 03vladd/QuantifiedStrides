from datetime import date
from typing import Literal

from pydantic import BaseModel


class TrainingLoadSchema(BaseModel):
    ctl: float
    atl: float
    tsb: float
    today_load: float
    ramp_rate: float
    freshness_label: str
    intensity_modifier: Literal["push", "normal", "back_off", "rest"]


class HRVStatusSchema(BaseModel):
    status: Literal["elevated", "normal", "suppressed", "no_data"]
    trend: Literal["rising", "stable", "falling"] | None
    last_hrv: float | None
    baseline: float | None
    baseline_sd: float | None
    deviation: float | None


class AlertSchema(BaseModel):
    severity: Literal["critical", "warning", "info"]
    message: str


class MuscleFreshnessSchema(BaseModel):
    muscles: dict[str, float]   # muscle → freshness 0.0–1.0


class ExerciseSuggestionSchema(BaseModel):
    name: str
    sets: int | None
    reps: int | str | None      # int or range string e.g. "8-10"
    duration: int | None        # seconds, for timed exercises
    weight_str: str | None
    note: str | None
    pattern: str | None
    quality: str | None
    last_done: str | None       # formatted string e.g. "3 days ago"


class GymRecSchema(BaseModel):
    intensity: str | None
    focus: str | None
    focus_label: str | None
    why: str | None
    session_type: Literal["upper", "lower"] | None


class RecommendationSchema(BaseModel):
    date: date
    primary: str                # e.g. "Upper Gym + Z2 Bike"
    intensity: str | None       # e.g. "moderate"
    duration: str | None        # e.g. "60-75 min"
    why: list[str]
    avoid: list[str]
    notes: list[str]
    blocks: dict[str, str]      # sport_key → reason blocked
    gym_rec: GymRecSchema | None
    exercises: list[ExerciseSuggestionSchema]
    narrative: str | None = None  # Claude API — populated later


class ReadinessSummarySchema(BaseModel):
    overall: int | None         # 1-10
    legs: int | None            # 1-10
    upper: int | None           # 1-10
    joints: int | None          # 1-10
    injury_note: str | None
    time: Literal["short", "medium", "long"] | None   # time_available from DB
    going_out: bool | None


class SleepSummarySchema(BaseModel):
    duration: float | None      # hours
    score: float | None         # sleep_score is FLOAT in DB
    hrv: float | None           # overnight HRV
    rhr: int | None
    hrv_status: str | None      # Garmin HRV status string
    body_battery: int | None    # body_battery_change overnight


class WeatherSchema(BaseModel):
    temp: float | None          # °C
    rain: bool | None           # precipitation > 0
    wind: float | None          # m/s


class RecentLoadSchema(BaseModel):
    run_km: float
    bike_min: float
    climb_sessions: int


class DashboardSchema(BaseModel):
    date: date
    alerts: list[AlertSchema]
    training_load: TrainingLoadSchema
    hrv_status: HRVStatusSchema
    muscle_freshness: MuscleFreshnessSchema
    recommendation: RecommendationSchema
    readiness: ReadinessSummarySchema | None
    sleep: SleepSummarySchema | None
    weather: WeatherSchema | None
    recent_load: RecentLoadSchema
