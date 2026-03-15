from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_current_user_id
from api.schemas.running import (
    BiomechanicsTrendPointSchema,
    ElevationHRDecouplingSchema,
    RunningTrendPointSchema,
    TerrainSummarySchema,
    WorkoutGAPSchema,
)
from api.services.running import RunningService

router = APIRouter(prefix="/running", tags=["running"])
_svc = RunningService()


@router.get("/trends", response_model=list[RunningTrendPointSchema])
async def get_running_trends(
    days: int = Query(default=365, ge=30, le=730),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_running_trends(days)


@router.get("/biomechanics", response_model=list[BiomechanicsTrendPointSchema])
async def get_biomechanics_trends(
    days: int = Query(default=365, ge=30, le=730),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_biomechanics_trends(days)


@router.get("/terrain", response_model=TerrainSummarySchema)
async def get_terrain_summary(
    days: int = Query(default=365, ge=30, le=730),
    sport: str = Query(default="running", pattern="^(running|trail_running)$"),
    user_id: int = Depends(get_current_user_id),
):
    return await _svc.get_terrain_summary(days, sport)


@router.get("/workouts/{workout_id}/gap", response_model=WorkoutGAPSchema)
async def get_workout_gap(
    workout_id: int,
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_workout_gap(workout_id)
    if not result:
        raise HTTPException(status_code=404, detail="No pace/gradient data for this workout")
    return result


@router.get("/workouts/{workout_id}/elevation-decoupling", response_model=ElevationHRDecouplingSchema)
async def get_elevation_decoupling(
    workout_id: int,
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.get_elevation_decoupling(workout_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Insufficient elevation data for this workout (need ≥50 points and ≥20m gain)"
        )
    return result
