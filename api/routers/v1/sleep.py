from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db
from api.schemas.sleep import SleepDetailSchema, SleepListItemSchema, SleepTrendPointSchema
from api.services.sleep import SleepService

router = APIRouter(prefix="/sleep", tags=["sleep"])
_svc = SleepService()


@router.get("", response_model=list[SleepListItemSchema])
async def list_sleep(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.list_sleep(db, user_id, days)


@router.get("/trends", response_model=list[SleepTrendPointSchema])
async def get_sleep_trends(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_sleep_trends(db, user_id, days)


@router.get("/{sleep_id}", response_model=SleepDetailSchema)
async def get_sleep_detail(
    sleep_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_sleep_detail(db, user_id, sleep_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sleep session not found")
    return result
