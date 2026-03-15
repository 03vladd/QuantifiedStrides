from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db
from api.schemas.checkin import (
    DailyReadinessCreateSchema,
    DailyReadinessSchema,
    JournalEntryCreateSchema,
    JournalEntrySchema,
    JournalHistoryRowSchema,
    WorkoutReflectionCreateSchema,
    WorkoutReflectionSchema,
)
from api.services.checkin import CheckinService

router = APIRouter(prefix="/checkin", tags=["checkin"])
_svc = CheckinService()


# ------------------------------------------------------------------
# Daily readiness
# ------------------------------------------------------------------

@router.post("/readiness", response_model=DailyReadinessSchema, status_code=201)
async def create_readiness(
    payload: DailyReadinessCreateSchema,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.create_readiness(db, user_id, payload)


@router.get("/readiness/{entry_date}", response_model=DailyReadinessSchema)
async def get_readiness(
    entry_date: date,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_readiness(db, user_id, entry_date)
    if not result:
        raise HTTPException(status_code=404, detail="Readiness entry not found")
    return result


# ------------------------------------------------------------------
# Workout reflection
# ------------------------------------------------------------------

@router.post("/reflection", response_model=WorkoutReflectionSchema, status_code=201)
async def create_reflection(
    payload: WorkoutReflectionCreateSchema,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.create_reflection(db, user_id, payload)


@router.get("/reflection/{entry_date}", response_model=WorkoutReflectionSchema)
async def get_reflection(
    entry_date: date,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_reflection(db, user_id, entry_date)
    if not result:
        raise HTTPException(status_code=404, detail="Workout reflection not found")
    return result


# ------------------------------------------------------------------
# Journal
# ------------------------------------------------------------------

@router.post("/journal", response_model=JournalEntrySchema, status_code=201)
async def upsert_journal(
    payload: JournalEntryCreateSchema,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    await _svc.ensure_journal_table(db)
    return await _svc.upsert_journal(db, user_id, payload)


@router.get("/journal/{entry_date}", response_model=JournalEntrySchema)
async def get_journal(
    entry_date: date,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_journal(db, user_id, entry_date)
    if not result:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return result


# ------------------------------------------------------------------
# History (joined view)
# ------------------------------------------------------------------

@router.get("/history", response_model=list[JournalHistoryRowSchema])
async def get_history(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_history(db, user_id, days)
