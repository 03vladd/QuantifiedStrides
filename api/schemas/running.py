from datetime import date
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Running economy trends (per workout)
# ---------------------------------------------------------------------------

class RunningTrendPointSchema(BaseModel):
    workout_id: int
    workout_date: date
    sport: Literal["running", "trail_running"]
    distance_km: float
    avg_hr: int | None
    normalized_power: float | None
    # Grade-Adjusted Pace
    avg_pace: float | None          # min/km
    avg_gap: float | None           # grade-adjusted pace, min/km
    gap_vs_pace_pct: float | None   # how much harder terrain made it
    # Aerobic decoupling
    decoupling_pct: float | None
    decoupling_status: Literal["efficient", "moderate_drift", "cardiac_drift"] | None
    # Running Economy Index
    rei: float | None
    rei_mode: Literal["power", "hr"] | None


# ---------------------------------------------------------------------------
# Biomechanics trends (per workout)
# ---------------------------------------------------------------------------

class BiomechanicsTrendPointSchema(BaseModel):
    workout_id: int
    workout_date: date
    sport: str
    distance_km: float
    avg_cadence: float | None       # steps/min
    avg_gct: float | None           # ground contact time ms
    avg_vo: float | None            # vertical oscillation mm
    avg_vr: float | None            # vertical ratio %
    avg_pace: float | None          # min/km
    avg_hr: float | None
    fatigue_score: float | None     # 0-100, higher = more fatigued
    cadence_drift_pct: float | None
    gct_drift_pct: float | None
    hr_drift_pct: float | None


# ---------------------------------------------------------------------------
# Terrain response
# ---------------------------------------------------------------------------

class GradientBandSchema(BaseModel):
    band: str                       # e.g. "slight_up", "flat", "steep_down"
    gradient_mid: float             # representative gradient for band
    avg_hr: float
    avg_pace: float                 # min/km
    avg_gap: float                  # grade-adjusted pace
    efficiency: float               # speed_ms / HR
    count: int


class GradeCostModelSchema(BaseModel):
    slope_bpm_per_pct: float        # HR cost per 1% gradient
    intercept: float
    r_squared: float
    n_points: int
    minetti_expected: float         # theoretical value from Minetti model
    mean_hr: float


class OptimalGradientSchema(BaseModel):
    optimal_gradient: float         # gradient % with best speed:HR ratio
    optimal_efficiency: float


class TerrainSummarySchema(BaseModel):
    hr_gradient_curve: list[GradientBandSchema]
    grade_cost_model: GradeCostModelSchema | None
    optimal_gradient: OptimalGradientSchema | None


# ---------------------------------------------------------------------------
# Single-workout detail analytics
# ---------------------------------------------------------------------------

class GradientProfileBucketSchema(BaseModel):
    gradient_pct: float
    count: int


class WorkoutGAPSchema(BaseModel):
    workout_id: int
    avg_pace: float
    avg_gap: float
    gap_vs_pace_pct: float
    gradient_profile: list[GradientProfileBucketSchema]
    rows_used: int


class ElevationQuartileSchema(BaseModel):
    quartile: int
    count: int
    avg_hr: float | None
    avg_pace: float | None
    avg_gap: float | None
    avg_gradient: float | None


class ElevationHRDecouplingSchema(BaseModel):
    workout_id: int
    total_gain_m: float
    quartiles: list[ElevationQuartileSchema]
