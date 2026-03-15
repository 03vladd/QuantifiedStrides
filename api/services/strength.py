"""
StrengthService

Strength session list/detail, 1RM progression, and exercise library.
All queries are async SQLAlchemy.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.strength import (
    ExerciseCreateSchema,
    ExerciseSchema,
    OneRMPointSchema,
    StrengthExerciseSchema,
    StrengthSessionListItemSchema,
    StrengthSessionSchema,
    StrengthSetSchema,
)


class StrengthService:

    # ------------------------------------------------------------------
    # Session list
    # ------------------------------------------------------------------

    async def list_sessions(
        self, db: AsyncSession, user_id: int, days: int = 90
    ) -> list[StrengthSessionListItemSchema]:
        result = await db.execute(text("""
            SELECT
                ss.session_id,
                ss.session_date,
                ss.session_type,
                COUNT(DISTINCT se.exercise_id) AS total_exercises,
                COUNT(st.set_id)               AS total_sets
            FROM strength_sessions ss
            LEFT JOIN strength_exercises se ON se.session_id = ss.session_id
            LEFT JOIN strength_sets st      ON st.exercise_id = se.exercise_id
            WHERE ss.user_id = :user_id
              AND ss.session_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            GROUP BY ss.session_id, ss.session_date, ss.session_type
            ORDER BY ss.session_date DESC
        """), {"user_id": user_id, "days": days})

        return [
            StrengthSessionListItemSchema(
                session_id=row.session_id,
                session_date=row.session_date,
                session_type=row.session_type,
                total_exercises=row.total_exercises,
                total_sets=row.total_sets,
            )
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # Session detail
    # ------------------------------------------------------------------

    async def get_session_detail(
        self, db: AsyncSession, user_id: int, session_id: int
    ) -> StrengthSessionSchema | None:
        result = await db.execute(text("""
            SELECT session_id, session_date, session_type, raw_notes
            FROM strength_sessions
            WHERE session_id = :session_id AND user_id = :user_id
        """), {"session_id": session_id, "user_id": user_id})

        row = result.fetchone()
        if not row:
            return None

        exercises = await self._get_exercises(db, session_id)

        return StrengthSessionSchema(
            session_id=row.session_id,
            session_date=row.session_date,
            session_type=row.session_type,
            raw_notes=row.raw_notes,
            exercises=exercises,
        )

    async def _get_exercises(
        self, db: AsyncSession, session_id: int
    ) -> list[StrengthExerciseSchema]:
        result = await db.execute(text("""
            SELECT exercise_id, exercise_order, name, notes
            FROM strength_exercises
            WHERE session_id = :session_id
            ORDER BY exercise_order
        """), {"session_id": session_id})

        exercises = []
        for row in result.fetchall():
            sets = await self._get_sets(db, row.exercise_id)
            exercises.append(StrengthExerciseSchema(
                exercise_id=row.exercise_id,
                exercise_order=row.exercise_order,
                name=row.name,
                notes=row.notes,
                sets=sets,
            ))
        return exercises

    async def _get_sets(
        self, db: AsyncSession, exercise_id: int
    ) -> list[StrengthSetSchema]:
        result = await db.execute(text("""
            SELECT
                set_id, set_number, reps, reps_min, reps_max,
                duration_seconds, weight_kg, is_bodyweight, band_color,
                per_hand, per_side, plus_bar, weight_includes_bar, total_weight_kg
            FROM strength_sets
            WHERE exercise_id = :exercise_id
            ORDER BY set_number
        """), {"exercise_id": exercise_id})

        return [
            StrengthSetSchema(
                set_id=row.set_id,
                set_number=row.set_number,
                reps=row.reps,
                reps_min=row.reps_min,
                reps_max=row.reps_max,
                duration_seconds=row.duration_seconds,
                weight_kg=row.weight_kg,
                is_bodyweight=row.is_bodyweight or False,
                band_color=row.band_color,
                per_hand=row.per_hand or False,
                per_side=row.per_side or False,
                plus_bar=row.plus_bar or False,
                weight_includes_bar=row.weight_includes_bar or False,
                total_weight_kg=row.total_weight_kg,
            )
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # 1RM progression (Epley formula)
    # ------------------------------------------------------------------

    async def get_1rm_history(
        self,
        db: AsyncSession,
        user_id: int,
        exercise_name: str,
        days: int = 365,
    ) -> list[OneRMPointSchema]:
        result = await db.execute(text("""
            SELECT
                ss.session_date,
                MAX(
                    st.total_weight_kg * (1.0 + st.reps / 30.0)
                ) AS epley_1rm
            FROM strength_sessions ss
            JOIN strength_exercises se ON se.session_id = ss.session_id
            JOIN strength_sets st      ON st.exercise_id = se.exercise_id
            WHERE ss.user_id = :user_id
              AND LOWER(se.name) = LOWER(:exercise_name)
              AND st.reps IS NOT NULL AND st.reps > 0
              AND st.total_weight_kg IS NOT NULL AND st.total_weight_kg > 0
              AND ss.session_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            GROUP BY ss.session_date
            ORDER BY ss.session_date
        """), {"user_id": user_id, "exercise_name": exercise_name, "days": days})

        return [
            OneRMPointSchema(
                session_date=row.session_date,
                epley_1rm=round(float(row.epley_1rm), 1),
            )
            for row in result.fetchall()
        ]

    async def get_tracked_exercises(
        self, db: AsyncSession, user_id: int
    ) -> list[str]:
        result = await db.execute(text("""
            SELECT DISTINCT se.name
            FROM strength_exercises se
            JOIN strength_sessions ss ON ss.session_id = se.session_id
            WHERE ss.user_id = :user_id
            ORDER BY se.name
        """), {"user_id": user_id})
        return [row.name for row in result.fetchall()]

    # ------------------------------------------------------------------
    # Exercise library
    # ------------------------------------------------------------------

    async def list_exercises(
        self, db: AsyncSession, search: str | None = None
    ) -> list[ExerciseSchema]:
        query = """
            SELECT
                exercise_id, name, source, movement_pattern, quality_focus,
                primary_muscles, secondary_muscles, equipment,
                skill_level, bilateral, contraction_type,
                systemic_fatigue, cns_load,
                joint_stress, sport_carryover, goal_carryover, notes
            FROM exercises
        """
        params: dict = {}
        if search:
            query += " WHERE LOWER(name) LIKE LOWER(:search)"
            params["search"] = f"%{search}%"
        query += " ORDER BY name"

        result = await db.execute(text(query), params)
        return [self._map_exercise(row) for row in result.fetchall()]

    async def create_exercise(
        self, db: AsyncSession, payload: ExerciseCreateSchema
    ) -> ExerciseSchema:
        result = await db.execute(text("""
            INSERT INTO exercises (
                name, source, movement_pattern, quality_focus,
                primary_muscles, secondary_muscles, equipment,
                skill_level, bilateral, contraction_type,
                systemic_fatigue, cns_load,
                joint_stress, sport_carryover, goal_carryover, notes
            ) VALUES (
                :name, :source, :movement_pattern, :quality_focus,
                :primary_muscles, :secondary_muscles, :equipment,
                :skill_level, :bilateral, :contraction_type,
                :systemic_fatigue, :cns_load,
                :joint_stress, :sport_carryover, :goal_carryover, :notes
            )
            RETURNING
                exercise_id, name, source, movement_pattern, quality_focus,
                primary_muscles, secondary_muscles, equipment,
                skill_level, bilateral, contraction_type,
                systemic_fatigue, cns_load,
                joint_stress, sport_carryover, goal_carryover, notes
        """), {
            "name": payload.name,
            "source": payload.source,
            "movement_pattern": payload.movement_pattern,
            "quality_focus": payload.quality_focus,
            "primary_muscles": payload.primary_muscles,
            "secondary_muscles": payload.secondary_muscles,
            "equipment": payload.equipment,
            "skill_level": payload.skill_level,
            "bilateral": payload.bilateral,
            "contraction_type": payload.contraction_type,
            "systemic_fatigue": payload.systemic_fatigue,
            "cns_load": payload.cns_load,
            "joint_stress": payload.joint_stress,
            "sport_carryover": payload.sport_carryover,
            "goal_carryover": payload.goal_carryover,
            "notes": payload.notes,
        })
        await db.commit()
        return self._map_exercise(result.fetchone())

    def _map_exercise(self, row) -> ExerciseSchema:
        return ExerciseSchema(
            exercise_id=row.exercise_id,
            name=row.name,
            source=row.source,
            movement_pattern=row.movement_pattern,
            quality_focus=row.quality_focus,
            primary_muscles=row.primary_muscles or [],
            secondary_muscles=row.secondary_muscles or [],
            equipment=row.equipment or [],
            skill_level=row.skill_level,
            bilateral=row.bilateral if row.bilateral is not None else True,
            contraction_type=row.contraction_type,
            systemic_fatigue=row.systemic_fatigue,
            cns_load=row.cns_load,
            joint_stress=row.joint_stress or {},
            sport_carryover=row.sport_carryover or {},
            goal_carryover=row.goal_carryover or {},
            notes=row.notes,
        )
