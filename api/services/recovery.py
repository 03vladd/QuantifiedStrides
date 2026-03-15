"""
RecoveryService

Wraps the sync recovery.py intelligence module.
Today: rule-based HRV deviation + exponential muscle fatigue decay.
Tomorrow: swap _compute_hrv / _compute_freshness for learned models
          without touching DashboardService.
"""

import asyncio
from datetime import date

from api.schemas.dashboard import HRVStatusSchema, MuscleFreshnessSchema

from db import get_connection
from recovery import get_hrv_status, get_muscle_freshness


class RecoveryService:

    async def get_hrv_status(self, today: date) -> tuple[dict, HRVStatusSchema]:
        """
        Returns the raw HRV dict (passed to AlertsService) and the mapped schema.
        """
        raw = await asyncio.to_thread(self._compute_hrv, today)
        schema = HRVStatusSchema(
            status=raw["status"],
            trend=raw.get("trend"),
            last_hrv=raw.get("last_hrv"),
            baseline=raw.get("baseline"),
            baseline_sd=raw.get("baseline_sd"),
            deviation=raw.get("deviation"),
        )
        return raw, schema

    async def get_muscle_freshness(self, today: date) -> MuscleFreshnessSchema:
        muscles = await asyncio.to_thread(self._compute_freshness, today)
        return MuscleFreshnessSchema(muscles=muscles)

    # ------------------------------------------------------------------
    # Sync implementations — run in thread pool
    # ------------------------------------------------------------------

    def _compute_hrv(self, today: date) -> dict:
        conn = get_connection()
        try:
            return get_hrv_status(conn.cursor(), today)
        finally:
            conn.close()

    def _compute_freshness(self, today: date) -> dict:
        conn = get_connection()
        try:
            return get_muscle_freshness(conn.cursor(), today)
        finally:
            conn.close()
