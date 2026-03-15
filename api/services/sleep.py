"""
SleepService

Sleep session list, detail with baseline comparisons, and trend data.
All queries are async SQLAlchemy.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.sleep import (
    SleepDetailSchema,
    SleepListItemSchema,
    SleepTrendPointSchema,
)


class SleepService:

    async def list_sleep(
        self, db: AsyncSession, user_id: int, days: int = 90
    ) -> list[SleepListItemSchema]:
        result = await db.execute(text("""
            SELECT
                sleep_id, sleep_date, duration_minutes, sleep_score,
                overnight_hrv, rhr, body_battery_change, hrv_status
            FROM sleep_sessions
            WHERE user_id = :user_id
              AND sleep_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            ORDER BY sleep_date DESC
        """), {"user_id": user_id, "days": days})

        return [
            SleepListItemSchema(
                sleep_id=row.sleep_id,
                sleep_date=row.sleep_date,
                duration_minutes=row.duration_minutes,
                sleep_score=row.sleep_score,
                overnight_hrv=row.overnight_hrv,
                rhr=row.rhr,
                body_battery_change=row.body_battery_change,
                hrv_status=row.hrv_status,
            )
            for row in result.fetchall()
        ]

    async def get_sleep_detail(
        self, db: AsyncSession, user_id: int, sleep_id: int
    ) -> SleepDetailSchema | None:
        result = await db.execute(text("""
            SELECT
                sleep_id, sleep_date, duration_minutes, sleep_score,
                overnight_hrv, hrv, rhr,
                time_in_deep, time_in_light, time_in_rem, time_awake,
                avg_sleep_stress, sleep_score_feedback, sleep_score_insight,
                hrv_status, body_battery_change
            FROM sleep_sessions
            WHERE sleep_id = :sleep_id AND user_id = :user_id
        """), {"sleep_id": sleep_id, "user_id": user_id})

        row = result.fetchone()
        if not row:
            return None

        baselines = await self._get_baselines(db, user_id, row.sleep_date)

        return SleepDetailSchema(
            sleep_id=row.sleep_id,
            sleep_date=row.sleep_date,
            duration_minutes=row.duration_minutes,
            sleep_score=row.sleep_score,
            overnight_hrv=row.overnight_hrv,
            hrv=row.hrv,
            rhr=row.rhr,
            time_in_deep=row.time_in_deep,
            time_in_light=row.time_in_light,
            time_in_rem=row.time_in_rem,
            time_awake=row.time_awake,
            avg_sleep_stress=row.avg_sleep_stress,
            sleep_score_feedback=row.sleep_score_feedback,
            sleep_score_insight=row.sleep_score_insight,
            hrv_status=row.hrv_status,
            body_battery_change=row.body_battery_change,
            baseline_hrv=baselines.get("hrv"),
            baseline_rhr=baselines.get("rhr"),
            baseline_score=baselines.get("score"),
            baseline_duration=baselines.get("duration"),
        )

    async def get_sleep_trends(
        self, db: AsyncSession, user_id: int, days: int = 90
    ) -> list[SleepTrendPointSchema]:
        result = await db.execute(text("""
            SELECT
                sleep_date, sleep_score, overnight_hrv,
                rhr, duration_minutes, body_battery_change
            FROM sleep_sessions
            WHERE user_id = :user_id
              AND sleep_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            ORDER BY sleep_date
        """), {"user_id": user_id, "days": days})

        return [
            SleepTrendPointSchema(
                sleep_date=row.sleep_date,
                sleep_score=row.sleep_score,
                overnight_hrv=row.overnight_hrv,
                rhr=row.rhr,
                duration_minutes=row.duration_minutes,
                body_battery_change=row.body_battery_change,
            )
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # 7-day rolling baselines for a given date
    # ------------------------------------------------------------------

    async def _get_baselines(
        self, db: AsyncSession, user_id: int, target_date: date
    ) -> dict:
        result = await db.execute(text("""
            SELECT
                AVG(overnight_hrv)    AS baseline_hrv,
                AVG(rhr)              AS baseline_rhr,
                AVG(sleep_score)      AS baseline_score,
                AVG(duration_minutes) AS baseline_duration
            FROM sleep_sessions
            WHERE user_id = :user_id
              AND sleep_date < :target_date
              AND sleep_date >= :target_date - INTERVAL '7 days'
        """), {"user_id": user_id, "target_date": target_date})

        row = result.fetchone()
        if not row:
            return {}
        return {
            "hrv":      float(row.baseline_hrv)      if row.baseline_hrv      else None,
            "rhr":      float(row.baseline_rhr)      if row.baseline_rhr      else None,
            "score":    float(row.baseline_score)    if row.baseline_score    else None,
            "duration": float(row.baseline_duration) if row.baseline_duration else None,
        }
