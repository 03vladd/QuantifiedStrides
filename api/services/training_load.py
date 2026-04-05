"""
TrainingLoadService

Wraps the sync training_load.py intelligence module.
Today: rule-based TRIMP/ATL/CTL/TSB computation via psycopg2.
Tomorrow: swap the _sync implementation for a learned load model
          without touching DashboardService.
"""

import asyncio
from datetime import date

from api.schemas.dashboard import TrainingLoadSchema

from db import get_connection
from training_load import get_metrics, tsb_intensity_hint


class TrainingLoadService:

    async def get_metrics(self, today: date, user_id: int = 1) -> tuple[dict, TrainingLoadSchema]:
        """
        Returns the raw metrics dict (passed to AlertsService) and the
        mapped TrainingLoadSchema (used by DashboardService directly).
        """
        raw = await asyncio.to_thread(self._compute, today, user_id)
        freshness_label, intensity_modifier = tsb_intensity_hint(raw["tsb"])
        schema = TrainingLoadSchema(
            ctl=raw["ctl"],
            atl=raw["atl"],
            tsb=raw["tsb"],
            today_load=raw["today_load"],
            ramp_rate=raw["ramp_rate"],
            freshness_label=freshness_label,
            intensity_modifier=intensity_modifier,
        )
        return raw, schema

    # ------------------------------------------------------------------
    # Sync implementation — runs in thread pool
    # ------------------------------------------------------------------

    def _compute(self, today: date, user_id: int = 1) -> dict:
        conn = get_connection()
        try:
            cur = conn.cursor()
            return get_metrics(cur, today, user_id=user_id)
        finally:
            conn.close()
