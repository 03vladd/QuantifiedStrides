"""
AlertsService

Wraps the sync alerts.py intelligence module.
Today: rule-based anomaly detection (ACWR, HRV, RHR, sleep, TSB, consecutive days).
Tomorrow: extend or replace with learned anomaly detection
          without touching DashboardService.
"""

import asyncio
from datetime import date

from api.schemas.dashboard import AlertSchema

from db import get_connection
from alerts import get_alerts


class AlertsService:

    async def get_alerts(
        self,
        today: date,
        tl_metrics: dict,
        hrv_status: dict,
        readiness: dict | None = None,
    ) -> list[AlertSchema]:
        raw = await asyncio.to_thread(
            self._compute, today, tl_metrics, hrv_status, readiness
        )
        return [AlertSchema(severity=sev, message=msg) for sev, msg in raw]

    # ------------------------------------------------------------------
    # Sync implementation — runs in thread pool
    # ------------------------------------------------------------------

    def _compute(
        self,
        today: date,
        tl_metrics: dict,
        hrv_status: dict,
        readiness: dict | None,
    ) -> list[tuple[str, str]]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            return get_alerts(cur, today, tl_metrics, hrv_status, readiness)
        finally:
            conn.close()
