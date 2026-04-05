from datetime import date
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sets / Exercises / Sessions
# ---------------------------------------------------------------------------

class StrengthSetSchema(BaseModel):
    set_id: int
    set_number: int
    reps: int | None
    reps_min: int | None
    reps_max: int | None
    duration_seconds: int | None
    weight_kg: float | None
    is_bodyweight: bool
    band_color: str | None
    per_hand: bool
    per_side: bool
    plus_bar: bool
    weight_includes_bar: bool
    total_weight_kg: float | None


class StrengthExerciseSchema(BaseModel):
    exercise_id: int
    exercise_order: int
    name: str
    notes: str | None
    sets: list[StrengthSetSchema]


class StrengthSessionSchema(BaseModel):
    session_id: int
    session_date: date
    session_type: Literal["upper", "lower"] | None
    raw_notes: str | None
    exercises: list[StrengthExerciseSchema]


class StrengthSessionListItemSchema(BaseModel):
    session_id: int
    session_date: date
    session_type: Literal["upper", "lower"] | None
    total_sets: int
    total_exercises: int


# ---------------------------------------------------------------------------
# 1RM progression
# ---------------------------------------------------------------------------

class OneRMPointSchema(BaseModel):
    session_date: date
    epley_1rm: float             # Epley estimate: weight × (1 + reps/30)


# ---------------------------------------------------------------------------
# Exercise library
# ---------------------------------------------------------------------------

class ExerciseSchema(BaseModel):
    exercise_id: int
    name: str
    source: Literal["wger", "custom"]
    movement_pattern: Literal[
        "push_h", "push_v", "pull_h", "pull_v",
        "hinge", "squat", "carry", "rotation",
        "plyo", "isolation", "stability"
    ] | None
    quality_focus: Literal[
        "power", "strength", "hypertrophy", "endurance", "stability"
    ] | None
    primary_muscles: list[str]
    secondary_muscles: list[str]
    equipment: list[str]
    skill_level: Literal["beginner", "intermediate", "advanced"] | None
    bilateral: bool
    contraction_type: Literal["explosive", "controlled", "isometric", "mixed"] | None
    systemic_fatigue: int | None    # 1-5
    cns_load: int | None            # 1-5
    joint_stress: dict              # JSONB {"shoulder": 2, ...}
    sport_carryover: dict           # JSONB {"xc_mtb": 3, ...}
    goal_carryover: dict            # JSONB {"strength": 4, ...}
    notes: str | None


# ---------------------------------------------------------------------------
# Merged Garmin workout + logged session view
# ---------------------------------------------------------------------------

class StrengthWorkoutSchema(BaseModel):
    workout_id: int
    workout_date: date
    duration_min: float | None          # derived from start/end time
    calories: int | None
    session_id: int | None              # None = not yet logged
    session_type: Literal["upper", "lower"] | None
    total_exercises: int
    total_sets: int


# ---------------------------------------------------------------------------
# Session creation (manual log)
# ---------------------------------------------------------------------------

class SetCreateSchema(BaseModel):
    set_number: int
    reps: int | None = None
    duration_seconds: int | None = None
    weight_kg: float | None = None
    is_bodyweight: bool = False
    band_color: str | None = None
    per_hand: bool = False
    per_side: bool = False
    plus_bar: bool = False
    weight_includes_bar: bool = False
    total_weight_kg: float | None = None


class ExerciseCreateInSessionSchema(BaseModel):
    exercise_order: int
    name: str
    notes: str | None = None
    sets: list[SetCreateSchema]


class StrengthSessionCreateSchema(BaseModel):
    session_date: date
    session_type: Literal["upper", "lower"] | None = None
    raw_notes: str | None = None
    exercises: list[ExerciseCreateInSessionSchema]


class ExerciseCreateSchema(BaseModel):
    name: str
    source: Literal["wger", "custom"] = "custom"
    movement_pattern: Literal[
        "push_h", "push_v", "pull_h", "pull_v",
        "hinge", "squat", "carry", "rotation",
        "plyo", "isolation", "stability"
    ] | None = None
    quality_focus: Literal[
        "power", "strength", "hypertrophy", "endurance", "stability"
    ] | None = None
    primary_muscles: list[str] = []
    secondary_muscles: list[str] = []
    equipment: list[str] = []
    skill_level: Literal["beginner", "intermediate", "advanced"] | None = None
    bilateral: bool = True
    contraction_type: Literal["explosive", "controlled", "isometric", "mixed"] | None = None
    systemic_fatigue: int | None = None
    cns_load: int | None = None
    joint_stress: dict = {}
    sport_carryover: dict = {}
    goal_carryover: dict = {}
    notes: str | None = None
