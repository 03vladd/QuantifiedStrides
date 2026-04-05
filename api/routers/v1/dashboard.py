from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db
from api.schemas.dashboard import DashboardSchema
from api.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_svc = DashboardService()


@router.get("", response_model=DashboardSchema)
async def get_dashboard(
    today: date = Query(default_factory=date.today),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _svc.get_dashboard(user_id, today, db=db)
