"""
TrainingService

Handles training load history, HRV history, workout list, and workout detail.
CRUD queries use the async SQLAlchemy session directly.
Training load computations wrap the existing sync module via asyncio.to_thread.
"""

import asyncio
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.training import (
    HRVHistoryPointSchema,
    TrainingHistoryPointSchema,
    WeeklyVolumeSchema,
    WorkoutDetailSchema,
    WorkoutListItemSchema,
    WorkoutMetricPointSchema,
)

from db import get_connection
from training_load import get_history, get_hrv_history


class TrainingService:

    # ------------------------------------------------------------------
    # Training load history (wraps sync module)
    # ------------------------------------------------------------------

    async def get_training_history(
        self, today: date, days: int = 90
    ) -> list[TrainingHistoryPointSchema]:
        def _sync():
            conn = get_connection()
            try:
                cur = conn.cursor()
                return get_history(cur, today, days=days)
            finally:
                conn.close()

        rows = await asyncio.to_thread(_sync)
        return [
            TrainingHistoryPointSchema(
                date=r["date"],
                load=r["load"],
                ctl=r["ctl"],
                atl=r["atl"],
                tsb=r["tsb"],
            )
            for r in rows
        ]

    async def get_hrv_history(
        self, today: date, days: int = 30
    ) -> list[HRVHistoryPointSchema]:
        def _sync():
            conn = get_connection()
            try:
                cur = conn.cursor()
                return get_hrv_history(cur, today, days=days)
            finally:
                conn.close()

        rows = await asyncio.to_thread(_sync)
        return [
            HRVHistoryPointSchema(
                date=r["date"],
                hrv=r["hrv"],
                baseline=r["baseline"],
                rhr=r.get("rhr"),
                sleep_score=r.get("sleep_score"),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Weekly volume (async SQL)
    # ------------------------------------------------------------------

    async def get_weekly_volume(
        self, db: AsyncSession, user_id: int, weeks: int = 12
    ) -> list[WeeklyVolumeSchema]:
        result = await db.execute(text("""
            SELECT
                date_trunc('week', session_date)::date AS week_start,
                COUNT(DISTINCT session_date)           AS training_days,
                COUNT(st.set_id)                       AS total_sets
            FROM strength_sessions ss
            JOIN strength_exercises se ON se.session_id = ss.session_id
            JOIN strength_sets st      ON st.exercise_id = se.exercise_id
            WHERE ss.user_id = :user_id
              AND session_date >= CURRENT_DATE - (:weeks * INTERVAL '1 week')
            GROUP BY week_start
            ORDER BY week_start
        """), {"user_id": user_id, "weeks": weeks})

        return [
            WeeklyVolumeSchema(
                week_start=row.week_start,
                training_days=row.training_days,
                total_sets=row.total_sets,
            )
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # Workout list (async SQL)
    # ------------------------------------------------------------------

    async def list_workouts(
        self,
        db: AsyncSession,
        user_id: int,
        days: int = 90,
        sport: str | None = None,
    ) -> list[WorkoutListItemSchema]:
        query = """
            SELECT
                workout_id, workout_date, sport, workout_type,
                start_time, end_time,
                EXTRACT(EPOCH FROM (end_time - start_time)) AS duration_s,
                training_volume                              AS distance_m,
                avg_heart_rate, max_heart_rate,
                calories_burned,
                training_stress_score
            FROM workouts
            WHERE user_id = :user_id
              AND workout_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
        """
        params: dict = {"user_id": user_id, "days": days}

        if sport:
            query += " AND sport = :sport"
            params["sport"] = sport

        query += " ORDER BY workout_date DESC, start_time DESC"

        result = await db.execute(text(query), params)
        return [
            WorkoutListItemSchema(
                workout_id=row.workout_id,
                workout_date=row.workout_date,
                sport=row.sport,
                workout_type=row.workout_type,
                start_time=row.start_time,
                end_time=row.end_time,
                duration_s=row.duration_s,
                distance_m=row.distance_m,
                avg_hr=row.avg_heart_rate,
                max_hr=row.max_heart_rate,
                calories=row.calories_burned,
                tss=row.training_stress_score,
            )
            for row in result.fetchall()
        ]

    async def get_sport_options(
        self, db: AsyncSession, user_id: int
    ) -> list[str]:
        result = await db.execute(text("""
            SELECT DISTINCT sport FROM workouts
            WHERE user_id = :user_id AND sport IS NOT NULL
            ORDER BY sport
        """), {"user_id": user_id})
        return [row.sport for row in result.fetchall()]

    # ------------------------------------------------------------------
    # Workout detail (async SQL)
    # ------------------------------------------------------------------

    async def get_workout_detail(
        self, db: AsyncSession, user_id: int, workout_id: int
    ) -> WorkoutDetailSchema | None:
        result = await db.execute(text("""
            SELECT
                workout_id, workout_date, sport, workout_type,
                start_time, end_time,
                EXTRACT(EPOCH FROM (end_time - start_time)) AS duration_s,
                training_volume          AS distance_m,
                avg_heart_rate, max_heart_rate, calories_burned,
                vo2max_estimate, lactate_threshold_bpm,
                time_in_hr_zone_1, time_in_hr_zone_2, time_in_hr_zone_3,
                time_in_hr_zone_4, time_in_hr_zone_5,
                elevation_gain, elevation_loss,
                aerobic_training_effect, anaerobic_training_effect,
                training_stress_score, normalized_power,
                avg_power, max_power,
                avg_running_cadence, max_running_cadence,
                avg_ground_contact_time, avg_vertical_oscillation,
                avg_stride_length, avg_vertical_ratio,
                total_steps,
                location, start_latitude, start_longitude
            FROM workouts
            WHERE workout_id = :workout_id AND user_id = :user_id
        """), {"workout_id": workout_id, "user_id": user_id})

        row = result.fetchone()
        if not row:
            return None

        metrics = await self._get_workout_metrics(db, workout_id)

        return WorkoutDetailSchema(
            workout_id=row.workout_id,
            workout_date=row.workout_date,
            sport=row.sport,
            workout_type=row.workout_type,
            start_time=row.start_time,
            end_time=row.end_time,
            duration_s=row.duration_s,
            distance_m=row.distance_m,
            avg_hr=row.avg_heart_rate,
            max_hr=row.max_heart_rate,
            calories=row.calories_burned,
            vo2max=row.vo2max_estimate,
            lactate_threshold=row.lactate_threshold_bpm,
            z1=row.time_in_hr_zone_1,
            z2=row.time_in_hr_zone_2,
            z3=row.time_in_hr_zone_3,
            z4=row.time_in_hr_zone_4,
            z5=row.time_in_hr_zone_5,
            elev_gain=row.elevation_gain,
            elev_loss=row.elevation_loss,
            aerobic_te=row.aerobic_training_effect,
            anaerobic_te=row.anaerobic_training_effect,
            tss=row.training_stress_score,
            norm_power=row.normalized_power,
            avg_power=row.avg_power,
            max_power=row.max_power,
            avg_cadence=row.avg_running_cadence,
            max_cadence=row.max_running_cadence,
            avg_gct=row.avg_ground_contact_time,
            avg_vo=row.avg_vertical_oscillation,
            avg_stride=row.avg_stride_length,
            avg_vr=row.avg_vertical_ratio,
            total_steps=row.total_steps,
            location=row.location,
            lat=row.start_latitude,
            lon=row.start_longitude,
            metrics=metrics,
        )

    async def _get_workout_metrics(
        self, db: AsyncSession, workout_id: int
    ) -> list[WorkoutMetricPointSchema]:
        result = await db.execute(text("""
            SELECT
                metric_timestamp, heart_rate, pace, cadence,
                vertical_oscillation, vertical_ratio, ground_contact_time,
                power, latitude, longitude, altitude, distance, gradient_pct
            FROM workout_metrics
            WHERE workout_id = :workout_id
            ORDER BY metric_timestamp
        """), {"workout_id": workout_id})

        return [
            WorkoutMetricPointSchema(
                metric_timestamp=row.metric_timestamp,
                heart_rate=row.heart_rate,
                pace=row.pace,
                cadence=row.cadence,
                vertical_oscillation=row.vertical_oscillation,
                vertical_ratio=row.vertical_ratio,
                ground_contact_time=row.ground_contact_time,
                power=row.power,
                latitude=row.latitude,
                longitude=row.longitude,
                altitude=row.altitude,
                distance=row.distance,
                gradient_pct=row.gradient_pct,
            )
            for row in result.fetchall()
        ]
