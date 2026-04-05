from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db
from api.schemas.strength import (
    ExerciseCreateSchema,
    ExerciseSchema,
    OneRMPointSchema,
    StrengthSessionCreateSchema,
    StrengthSessionListItemSchema,
    StrengthSessionSchema,
    StrengthWorkoutSchema,
)
from api.services.strength import StrengthService

router = APIRouter(prefix="/strength", tags=["strength"])
_svc = StrengthService()


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------

@router.get("/workouts", response_model=list[StrengthWorkoutSchema])
async def list_garmin_sessions(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.list_garmin_sessions(db, user_id, days)


@router.get("/sessions", response_model=list[StrengthSessionListItemSchema])
async def list_sessions(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.list_sessions(db, user_id, days)


@router.post("/sessions", response_model=StrengthSessionSchema, status_code=201)
async def create_session(
    payload: StrengthSessionCreateSchema,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.create_session(db, user_id, payload)


@router.get("/sessions/{session_id}", response_model=StrengthSessionSchema)
async def get_session_detail(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_session_detail(db, user_id, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Strength session not found")
    return result


# ------------------------------------------------------------------
# 1RM progression
# ------------------------------------------------------------------

@router.get("/1rm", response_model=list[OneRMPointSchema])
async def get_1rm_history(
    exercise: str = Query(..., description="Exercise name (case-insensitive)"),
    days: int = Query(default=365, ge=30, le=730),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_1rm_history(db, user_id, exercise, days)


@router.get("/1rm/exercises", response_model=list[str])
async def get_tracked_exercises(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_tracked_exercises(db, user_id)


# ------------------------------------------------------------------
# Exercise library
# ------------------------------------------------------------------

@router.get("/exercises", response_model=list[ExerciseSchema])
async def list_exercises(
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.list_exercises(db, search)


@router.post("/exercises", response_model=ExerciseSchema, status_code=201)
async def create_exercise(
    payload: ExerciseCreateSchema,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.create_exercise(db, payload)
