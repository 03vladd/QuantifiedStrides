"""
RecommendationService

THE key swappable service in the architecture.

Today:  rule-based engine from recommend.py (gated logic on readiness,
        sleep, weather, load, consecutive days, gym analysis).
Phase 2: replace _build_rec with an XGBoost model trained on accumulated data.
Phase 3: replace with SASRec transformer for multi-athlete sequential recommendations.
Phase 4: add Claude API narrative layer on top of whatever model runs below.

DashboardService calls this service — it never touches recommend.py directly.
"""

import asyncio
from datetime import date

from api.schemas.dashboard import ExerciseSuggestionSchema, GymRecSchema, RecommendationSchema

from db import get_connection
from recommend import (
    get_readiness,
    get_yesterdays_training,
    get_last_nights_sleep,
    get_recent_load,
    get_latest_weather,
    get_gym_analysis,
    build_recommendation,
    get_exercise_suggestions,
    get_consecutive_training_days,
)


class RecommendationService:

    async def get_recommendation(
        self,
        today: date,
        tl_metrics: dict,
    ) -> tuple[dict | None, RecommendationSchema]:
        """
        Returns (raw_readiness_dict, RecommendationSchema).

        raw_readiness_dict is passed to AlertsService so it can incorporate
        subjective signals (overall feel, energy, soreness, going_out) into alerts.
        """
        readiness_raw, rec_raw, exercises_raw = await asyncio.to_thread(
            self._build, today, tl_metrics
        )

        schema = RecommendationSchema(
            date=today,
            primary=rec_raw.get("primary", ""),
            intensity=rec_raw.get("intensity"),
            duration=rec_raw.get("duration"),
            why=rec_raw.get("why", []),
            avoid=rec_raw.get("avoid", []),
            notes=rec_raw.get("notes", []),
            blocks=rec_raw.get("blocks", {}),
            gym_rec=self._map_gym_rec(rec_raw.get("gym_rec")),
            exercises=[
                ExerciseSuggestionSchema(
                    name=ex["name"],
                    sets=ex.get("sets"),
                    reps=ex.get("reps"),
                    duration=ex.get("duration"),
                    weight_str=ex.get("weight_str"),
                    note=ex.get("note"),
                    pattern=ex.get("pattern"),
                    quality=ex.get("quality"),
                    last_done=ex.get("last_done"),
                )
                for ex in (exercises_raw or [])
            ],
            narrative=None,  # Phase 4: Claude API fills this in
        )
        return readiness_raw, schema

    # ------------------------------------------------------------------
    # Sync implementation — runs in thread pool
    # ------------------------------------------------------------------

    def _build(
        self, today: date, tl_metrics: dict
    ) -> tuple[dict | None, dict, list | None]:
        from datetime import timedelta

        conn = get_connection()
        try:
            cur = conn.cursor()
            yesterday = today - timedelta(days=1)

            readiness    = get_readiness(cur, today)
            yday         = get_yesterdays_training(cur, yesterday)
            sleep        = get_last_nights_sleep(cur, today)
            weather      = get_latest_weather(cur)
            load         = get_recent_load(cur, today)
            consec       = get_consecutive_training_days(cur, today)
            gym_analysis = get_gym_analysis(cur, today)

            rec_raw = build_recommendation(
                readiness, yday, sleep, weather, load,
                consec, gym_analysis, today, tl_metrics,
            )
            exercises_raw = get_exercise_suggestions(cur, rec_raw.get("gym_rec"), today)

        finally:
            conn.close()

        return readiness, rec_raw, exercises_raw

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _map_gym_rec(self, gym_rec: dict | None) -> GymRecSchema | None:
        if not gym_rec:
            return None
        return GymRecSchema(
            intensity=gym_rec.get("intensity"),
            focus=gym_rec.get("focus"),
            focus_label=gym_rec.get("focus_label"),
            why=gym_rec.get("why"),
            session_type=gym_rec.get("session_type"),
        )
