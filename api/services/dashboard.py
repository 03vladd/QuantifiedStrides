"""
DashboardService

Aggregates all data needed for the home screen in one call.
Each concern is delegated to its own swappable service:

    TrainingLoadService   — ATL/CTL/TSB (rule-based today, learned model tomorrow)
    RecoveryService       — HRV status + muscle freshness
    AlertsService         — anomaly detection alerts
    RecommendationService — what to do today (rule-based → XGBoost → SASRec → Claude)

DashboardService itself contains NO intelligence logic — only orchestration.
"""

import asyncio
from datetime import date, timedelta

from api.schemas.dashboard import (
    DashboardSchema,
    RecentLoadSchema,
    SleepSummarySchema,
    WeatherSchema,
    ReadinessSummarySchema,
)
from api.services.training_load import TrainingLoadService
from api.services.recovery import RecoveryService
from api.services.alerts import AlertsService
from api.services.recommendation import RecommendationService

from db import get_connection
from recommend import get_last_nights_sleep, get_latest_weather, get_recent_load


class DashboardService:

    def __init__(self):
        self._training_load  = TrainingLoadService()
        self._recovery       = RecoveryService()
        self._alerts         = AlertsService()
        self._recommendation = RecommendationService()

    async def get_dashboard(self, user_id: int, today: date) -> DashboardSchema:
        # ── 1. Training load (needed by alerts + recommendation) ──────────────
        tl_raw, tl_schema = await self._training_load.get_metrics(today)

        # ── 2. Recovery (HRV + muscle freshness) — independent of load ────────
        (hrv_raw, hrv_schema), freshness_schema = await asyncio.gather(
            self._recovery.get_hrv_status(today),
            self._recovery.get_muscle_freshness(today),
        )

        # ── 3. Recommendation (also surfaces readiness for alerts) ─────────────
        readiness_raw, rec_schema = await self._recommendation.get_recommendation(
            today, tl_raw
        )

        # ── 4. Alerts (needs tl, hrv, and readiness from step 3) ──────────────
        alerts = await self._alerts.get_alerts(today, tl_raw, hrv_raw, readiness_raw)

        # ── 5. Contextual data (sleep summary, weather, recent load) ──────────
        sleep_schema, weather_schema, recent_load_schema = await asyncio.to_thread(
            self._get_context, today
        )

        return DashboardSchema(
            date=today,
            alerts=alerts,
            training_load=tl_schema,
            hrv_status=hrv_schema,
            muscle_freshness=freshness_schema,
            recommendation=rec_schema,
            readiness=self._map_readiness(readiness_raw),
            sleep=sleep_schema,
            weather=weather_schema,
            recent_load=recent_load_schema,
        )

    # ------------------------------------------------------------------
    # Contextual data — sleep summary, weather, recent load
    # ------------------------------------------------------------------

    def _get_context(
        self, today: date
    ) -> tuple[SleepSummarySchema | None, WeatherSchema | None, RecentLoadSchema]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            sleep   = get_last_nights_sleep(cur, today)
            weather = get_latest_weather(cur)
            load    = get_recent_load(cur, today)
        finally:
            conn.close()

        return (
            self._map_sleep(sleep),
            self._map_weather(weather),
            RecentLoadSchema(
                run_km=load.get("run_km", 0.0),
                bike_min=load.get("bike_min", 0.0),
                climb_sessions=load.get("climb_sessions", 0),
            ),
        )

    # ------------------------------------------------------------------
    # Schema mappers
    # ------------------------------------------------------------------

    def _map_readiness(self, r: dict | None) -> ReadinessSummarySchema | None:
        if not r:
            return None
        return ReadinessSummarySchema(
            overall=r.get("overall"),
            legs=r.get("legs"),
            upper=r.get("upper"),
            joints=r.get("joints"),
            injury_note=r.get("injury_note"),
            time=r.get("time"),
            going_out=r.get("going_out"),
        )

    def _map_sleep(self, s: dict | None) -> SleepSummarySchema | None:
        if not s:
            return None
        return SleepSummarySchema(
            duration=s.get("duration"),
            score=s.get("score"),
            hrv=s.get("hrv"),
            rhr=s.get("rhr"),
            hrv_status=s.get("hrv_status"),
            body_battery=s.get("body_battery"),
        )

    def _map_weather(self, w: dict | None) -> WeatherSchema | None:
        if not w:
            return None
        return WeatherSchema(
            temp=w.get("temp"),
            rain=w.get("rain"),
            wind=w.get("wind"),
        )
