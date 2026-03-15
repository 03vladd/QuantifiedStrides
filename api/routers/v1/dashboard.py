from datetime import date

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user_id
from api.schemas.dashboard import DashboardSchema
from api.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_svc = DashboardService()


@router.get("", response_model=DashboardSchema)
async def get_dashboard(
    today: date = Query(default_factory=date.today),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_dashboard(user_id, today)
