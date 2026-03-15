"""
RunningService

Wraps the three sync analytics modules:
  analytics/running_economy.py  — GAP, aerobic decoupling, REI
  analytics/biomechanics.py     — fatigue signature, cadence-speed, longitudinal trends
  analytics/terrain_response.py — HR-gradient curve, grade cost model, optimal gradient

All analytics functions are psycopg2-based and run in a thread pool via
asyncio.to_thread so they never block the async event loop.
"""

import asyncio
from typing import Literal

from api.schemas.running import (
    BiomechanicsTrendPointSchema,
    ElevationHRDecouplingSchema,
    ElevationQuartileSchema,
    GradientProfileBucketSchema,
    GradeCostModelSchema,
    GradientBandSchema,
    OptimalGradientSchema,
    RunningTrendPointSchema,
    TerrainSummarySchema,
    WorkoutGAPSchema,
)

from db import get_connection
from analytics.running_economy import (
    get_running_trends,
    get_workout_gap,
    get_aerobic_decoupling,
    get_running_economy_index,
)
from analytics.biomechanics import get_biomechanics_trends, get_fatigue_signature
from analytics.terrain_response import (
    get_terrain_summary,
    get_elevation_hr_decoupling,
)


class RunningService:

    # ------------------------------------------------------------------
    # Running economy trends (multi-workout)
    # ------------------------------------------------------------------

    async def get_running_trends(self, days: int = 365) -> list[RunningTrendPointSchema]:
        rows = await asyncio.to_thread(self._running_trends, days)
        return [
            RunningTrendPointSchema(
                workout_id=r["workout_id"],
                workout_date=r["workout_date"],
                sport=r["sport"],
                distance_km=r["distance_km"],
                avg_hr=r.get("avg_hr"),
                normalized_power=r.get("normalized_power"),
                avg_pace=r.get("avg_pace"),
                avg_gap=r.get("avg_gap"),
                gap_vs_pace_pct=r.get("gap_vs_pace_pct"),
                decoupling_pct=r.get("decoupling_pct"),
                decoupling_status=r.get("decoupling_status"),
                rei=r.get("rei"),
                rei_mode=r.get("rei_mode"),
            )
            for r in rows
        ]

    def _running_trends(self, days: int) -> list[dict]:
        conn = get_connection()
        try:
            return get_running_trends(days=days, conn=conn)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Single-workout: GAP
    # ------------------------------------------------------------------

    async def get_workout_gap(self, workout_id: int) -> WorkoutGAPSchema | None:
        raw = await asyncio.to_thread(self._workout_gap, workout_id)
        if not raw:
            return None
        return WorkoutGAPSchema(
            workout_id=raw["workout_id"],
            avg_pace=raw["avg_pace"],
            avg_gap=raw["avg_gap"],
            gap_vs_pace_pct=raw["gap_vs_pace_pct"],
            gradient_profile=[
                GradientProfileBucketSchema(
                    gradient_pct=b["gradient_pct"],
                    count=b["count"],
                )
                for b in raw["gradient_profile"]
            ],
            rows_used=raw["rows_used"],
        )

    def _workout_gap(self, workout_id: int) -> dict | None:
        conn = get_connection()
        try:
            return get_workout_gap(workout_id, conn)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Biomechanics trends (multi-workout)
    # ------------------------------------------------------------------

    async def get_biomechanics_trends(self, days: int = 365) -> list[BiomechanicsTrendPointSchema]:
        rows = await asyncio.to_thread(self._biomechanics_trends, days)
        return [
            BiomechanicsTrendPointSchema(
                workout_id=r["workout_id"],
                workout_date=r["workout_date"],
                sport=r["sport"],
                distance_km=r["distance_km"],
                avg_cadence=r.get("avg_cadence"),
                avg_gct=r.get("avg_gct"),
                avg_vo=r.get("avg_vo"),
                avg_vr=r.get("avg_vr"),
                avg_pace=r.get("avg_pace"),
                avg_hr=r.get("avg_hr"),
                fatigue_score=r.get("fatigue_score"),
                cadence_drift_pct=r.get("cadence_drift_pct"),
                gct_drift_pct=r.get("gct_drift_pct"),
                hr_drift_pct=r.get("hr_drift_pct"),
            )
            for r in rows
        ]

    def _biomechanics_trends(self, days: int) -> list[dict]:
        conn = get_connection()
        try:
            return get_biomechanics_trends(days=days, conn=conn)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Terrain response summary (multi-workout)
    # ------------------------------------------------------------------

    async def get_terrain_summary(
        self, days: int = 365, sport: str = "running"
    ) -> TerrainSummarySchema:
        raw = await asyncio.to_thread(self._terrain_summary, days, sport)
        return self._map_terrain(raw)

    def _terrain_summary(self, days: int, sport: str) -> dict:
        conn = get_connection()
        try:
            return get_terrain_summary(days=days, conn=conn)
        finally:
            conn.close()

    def _map_terrain(self, raw: dict) -> TerrainSummarySchema:
        curve = [
            GradientBandSchema(
                band=b["band"],
                gradient_mid=b["gradient_mid"],
                avg_hr=b["avg_hr"],
                avg_pace=b["avg_pace"],
                avg_gap=b["avg_gap"],
                efficiency=b["efficiency"],
                count=b["count"],
            )
            for b in (raw.get("hr_gradient_curve") or [])
        ]

        model_raw = raw.get("grade_cost_model")
        model = GradeCostModelSchema(
            slope_bpm_per_pct=model_raw["slope_bpm_per_pct"],
            intercept=model_raw["intercept"],
            r_squared=model_raw["r_squared"],
            n_points=model_raw["n_points"],
            minetti_expected=model_raw["minetti_expected"],
            mean_hr=model_raw["mean_hr"],
        ) if model_raw else None

        opt_raw = raw.get("optimal_gradient")
        optimal = OptimalGradientSchema(
            optimal_gradient=opt_raw["optimal_gradient"],
            optimal_efficiency=opt_raw["optimal_efficiency"],
        ) if opt_raw else None

        return TerrainSummarySchema(
            hr_gradient_curve=curve,
            grade_cost_model=model,
            optimal_gradient=optimal,
        )

    # ------------------------------------------------------------------
    # Single-workout: elevation HR decoupling
    # ------------------------------------------------------------------

    async def get_elevation_decoupling(
        self, workout_id: int
    ) -> ElevationHRDecouplingSchema | None:
        raw = await asyncio.to_thread(self._elevation_decoupling, workout_id)
        if not raw:
            return None
        return ElevationHRDecouplingSchema(
            workout_id=raw["workout_id"],
            total_gain_m=raw["total_gain_m"],
            quartiles=[
                ElevationQuartileSchema(
                    quartile=q["quartile"],
                    count=q["count"],
                    avg_hr=q.get("avg_hr"),
                    avg_pace=q.get("avg_pace"),
                    avg_gap=q.get("avg_gap"),
                    avg_gradient=q.get("avg_gradient"),
                )
                for q in raw["quartiles"]
            ],
        )

    def _elevation_decoupling(self, workout_id: int) -> dict | None:
        conn = get_connection()
        try:
            return get_elevation_hr_decoupling(workout_id, conn)
        finally:
            conn.close()
