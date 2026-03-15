from datetime import date
from typing import Literal

from pydantic import BaseModel


class SleepListItemSchema(BaseModel):
    sleep_id: int
    sleep_date: date
    duration_minutes: int | None
    sleep_score: float | None
    overnight_hrv: float | None
    rhr: int | None
    body_battery_change: int | None
    hrv_status: str | None


class SleepDetailSchema(BaseModel):
    sleep_id: int
    sleep_date: date
    duration_minutes: int | None
    sleep_score: float | None
    overnight_hrv: float | None
    hrv: float | None                   # daytime HRV reading
    rhr: int | None
    time_in_deep: int | None            # minutes
    time_in_light: int | None           # minutes
    time_in_rem: int | None             # minutes
    time_awake: int | None              # minutes
    avg_sleep_stress: float | None
    sleep_score_feedback: str | None
    sleep_score_insight: str | None
    hrv_status: str | None
    body_battery_change: int | None
    # baseline comparisons (7-day rolling)
    baseline_hrv: float | None
    baseline_rhr: float | None
    baseline_score: float | None
    baseline_duration: float | None     # minutes


class SleepTrendPointSchema(BaseModel):
    sleep_date: date
    sleep_score: float | None
    overnight_hrv: float | None
    rhr: int | None
    duration_minutes: int | None
    body_battery_change: int | None
