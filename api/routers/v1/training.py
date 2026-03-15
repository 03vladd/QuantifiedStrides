from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_current_user_id, get_db
from api.schemas.training import (
    HRVHistoryPointSchema,
    TrainingHistoryPointSchema,
    WeeklyVolumeSchema,
    WorkoutDetailSchema,
    WorkoutListItemSchema,
)
from api.services.training import TrainingService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/training", tags=["training"])
_svc = TrainingService()


@router.get("/history", response_model=list[TrainingHistoryPointSchema])
async def get_training_history(
    today: date = Query(default_factory=date.today),
    days: int = Query(default=90, ge=7, le=365),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_training_history(today, days)


@router.get("/hrv-history", response_model=list[HRVHistoryPointSchema])
async def get_hrv_history(
    today: date = Query(default_factory=date.today),
    days: int = Query(default=30, ge=7, le=180),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_hrv_history(today, days)


@router.get("/weekly-volume", response_model=list[WeeklyVolumeSchema])
async def get_weekly_volume(
    weeks: int = Query(default=12, ge=4, le=52),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_weekly_volume(db, user_id, weeks)


@router.get("/workouts", response_model=list[WorkoutListItemSchema])
async def list_workouts(
    days: int = Query(default=90, ge=7, le=365),
    sport: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.list_workouts(db, user_id, days, sport)


@router.get("/workouts/sports", response_model=list[str])
async def get_sport_options(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_sport_options(db, user_id)


@router.get("/workouts/{workout_id}", response_model=WorkoutDetailSchema)
async def get_workout_detail(
    workout_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_workout_detail(db, user_id, workout_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workout not found")
    return result
