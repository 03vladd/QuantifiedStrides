from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Daily readiness — POST body
# ---------------------------------------------------------------------------

class DailyReadinessCreateSchema(BaseModel):
    entry_date: date
    overall_feel: int = Field(ge=1, le=10)
    legs_feel: int = Field(ge=1, le=10)
    upper_body_feel: int = Field(ge=1, le=10)
    joint_feel: int = Field(ge=1, le=10)
    injury_note: str | None = None
    time_available: Literal["short", "medium", "long"]
    going_out_tonight: bool = False


class DailyReadinessSchema(BaseModel):
    readiness_id: int
    user_id: int
    entry_date: date
    overall_feel: int
    legs_feel: int
    upper_body_feel: int
    joint_feel: int
    injury_note: str | None
    time_available: Literal["short", "medium", "long"] | None
    going_out_tonight: bool


# ---------------------------------------------------------------------------
# Workout reflection — POST body
# ---------------------------------------------------------------------------

class WorkoutReflectionCreateSchema(BaseModel):
    entry_date: date
    session_rpe: int = Field(ge=1, le=10)
    session_quality: int = Field(ge=1, le=10)
    notes: str | None = None


class WorkoutReflectionSchema(BaseModel):
    reflection_id: int
    user_id: int
    entry_date: date
    session_rpe: int
    session_quality: int
    notes: str | None


# ---------------------------------------------------------------------------
# Journal entry — POST body
# ---------------------------------------------------------------------------

class JournalEntryCreateSchema(BaseModel):
    entry_date: date
    content: str = Field(min_length=1)


class JournalEntrySchema(BaseModel):
    entry_id: int
    user_id: int
    entry_date: date
    content: str


# ---------------------------------------------------------------------------
# Journal history row (joined: readiness + reflection + journal)
# ---------------------------------------------------------------------------

class JournalHistoryRowSchema(BaseModel):
    entry_date: date
    overall: int | None
    legs: int | None
    upper: int | None
    joints: int | None
    injury_note: str | None
    time_available: Literal["short", "medium", "long"] | None
    going_out: bool | None
    rpe: int | None
    session_quality: int | None
    reflection_notes: str | None
    journal_note: str | None
