"""
CheckinService

CRUD for the three daily check-in tables:
  daily_readiness   — morning readiness (overall feel, legs, joints, time, going_out)
  workout_reflection — post-workout RPE + quality
  journal_entries   — free-text daily journal (created via CREATE TABLE IF NOT EXISTS)

All queries are async SQLAlchemy.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.checkin import (
    DailyReadinessCreateSchema,
    DailyReadinessSchema,
    JournalEntryCreateSchema,
    JournalEntrySchema,
    JournalHistoryRowSchema,
    WorkoutReflectionCreateSchema,
    WorkoutReflectionSchema,
)


class CheckinService:

    # ------------------------------------------------------------------
    # Ensure journal_entries table exists (created at runtime if absent)
    # ------------------------------------------------------------------

    async def ensure_journal_table(self, db: AsyncSession) -> None:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                entry_id   SERIAL PRIMARY KEY,
                user_id    INT  NOT NULL,
                entry_date DATE NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (user_id, entry_date)
            )
        """))
        await db.commit()

    # ------------------------------------------------------------------
    # Daily readiness
    # ------------------------------------------------------------------

    async def create_readiness(
        self, db: AsyncSession, user_id: int, payload: DailyReadinessCreateSchema
    ) -> DailyReadinessSchema:
        result = await db.execute(text("""
            INSERT INTO daily_readiness (
                user_id, entry_date, overall_feel, legs_feel,
                upper_body_feel, joint_feel, injury_note,
                time_available, going_out_tonight
            ) VALUES (
                :user_id, :entry_date, :overall_feel, :legs_feel,
                :upper_body_feel, :joint_feel, :injury_note,
                :time_available, :going_out_tonight
            )
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                overall_feel     = EXCLUDED.overall_feel,
                legs_feel        = EXCLUDED.legs_feel,
                upper_body_feel  = EXCLUDED.upper_body_feel,
                joint_feel       = EXCLUDED.joint_feel,
                injury_note      = EXCLUDED.injury_note,
                time_available   = EXCLUDED.time_available,
                going_out_tonight = EXCLUDED.going_out_tonight
            RETURNING
                readiness_id, user_id, entry_date, overall_feel, legs_feel,
                upper_body_feel, joint_feel, injury_note,
                time_available, going_out_tonight
        """), {
            "user_id":          user_id,
            "entry_date":       payload.entry_date,
            "overall_feel":     payload.overall_feel,
            "legs_feel":        payload.legs_feel,
            "upper_body_feel":  payload.upper_body_feel,
            "joint_feel":       payload.joint_feel,
            "injury_note":      payload.injury_note,
            "time_available":   payload.time_available,
            "going_out_tonight": payload.going_out_tonight,
        })
        await db.commit()
        row = result.fetchone()
        return self._map_readiness(row)

    async def get_readiness(
        self, db: AsyncSession, user_id: int, entry_date: date
    ) -> DailyReadinessSchema | None:
        result = await db.execute(text("""
            SELECT readiness_id, user_id, entry_date, overall_feel, legs_feel,
                   upper_body_feel, joint_feel, injury_note,
                   time_available, going_out_tonight
            FROM daily_readiness
            WHERE user_id = :user_id AND entry_date = :entry_date
        """), {"user_id": user_id, "entry_date": entry_date})
        row = result.fetchone()
        return self._map_readiness(row) if row else None

    def _map_readiness(self, row) -> DailyReadinessSchema:
        return DailyReadinessSchema(
            readiness_id=row.readiness_id,
            user_id=row.user_id,
            entry_date=row.entry_date,
            overall_feel=row.overall_feel,
            legs_feel=row.legs_feel,
            upper_body_feel=row.upper_body_feel,
            joint_feel=row.joint_feel,
            injury_note=row.injury_note,
            time_available=row.time_available,
            going_out_tonight=row.going_out_tonight or False,
        )

    # ------------------------------------------------------------------
    # Workout reflection
    # ------------------------------------------------------------------

    async def create_reflection(
        self, db: AsyncSession, user_id: int, payload: WorkoutReflectionCreateSchema
    ) -> WorkoutReflectionSchema:
        result = await db.execute(text("""
            INSERT INTO workout_reflection (
                user_id, entry_date, session_rpe, session_quality, notes, load_feel
            ) VALUES (
                :user_id, :entry_date, :session_rpe, :session_quality, :notes, :load_feel
            )
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                session_rpe     = EXCLUDED.session_rpe,
                session_quality = EXCLUDED.session_quality,
                notes           = EXCLUDED.notes,
                load_feel       = EXCLUDED.load_feel
            RETURNING reflection_id, user_id, entry_date, session_rpe, session_quality, notes, load_feel
        """), {
            "user_id":         user_id,
            "entry_date":      payload.entry_date,
            "session_rpe":     payload.session_rpe,
            "session_quality": payload.session_quality,
            "notes":           payload.notes,
            "load_feel":       payload.load_feel,
        })
        await db.commit()
        row = result.fetchone()
        return self._map_reflection(row)

    async def get_reflection(
        self, db: AsyncSession, user_id: int, entry_date: date
    ) -> WorkoutReflectionSchema | None:
        result = await db.execute(text("""
            SELECT reflection_id, user_id, entry_date, session_rpe, session_quality, notes, load_feel
            FROM workout_reflection
            WHERE user_id = :user_id AND entry_date = :entry_date
        """), {"user_id": user_id, "entry_date": entry_date})
        row = result.fetchone()
        return self._map_reflection(row) if row else None

    def _map_reflection(self, row) -> WorkoutReflectionSchema:
        return WorkoutReflectionSchema(
            reflection_id=row.reflection_id,
            user_id=row.user_id,
            entry_date=row.entry_date,
            session_rpe=row.session_rpe,
            session_quality=row.session_quality,
            notes=row.notes,
            load_feel=row.load_feel,
        )

    # ------------------------------------------------------------------
    # Journal entries
    # ------------------------------------------------------------------

    async def upsert_journal(
        self, db: AsyncSession, user_id: int, payload: JournalEntryCreateSchema
    ) -> JournalEntrySchema:
        result = await db.execute(text("""
            INSERT INTO journal_entries (user_id, entry_date, content)
            VALUES (:user_id, :entry_date, :content)
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                content    = EXCLUDED.content,
                created_at = now()
            RETURNING entry_id, user_id, entry_date, content
        """), {
            "user_id":    user_id,
            "entry_date": payload.entry_date,
            "content":    payload.content,
        })
        await db.commit()
        row = result.fetchone()
        return JournalEntrySchema(
            entry_id=row.entry_id,
            user_id=row.user_id,
            entry_date=row.entry_date,
            content=row.content,
        )

    async def get_journal(
        self, db: AsyncSession, user_id: int, entry_date: date
    ) -> JournalEntrySchema | None:
        result = await db.execute(text("""
            SELECT entry_id, user_id, entry_date, content
            FROM journal_entries
            WHERE user_id = :user_id AND entry_date = :entry_date
        """), {"user_id": user_id, "entry_date": entry_date})
        row = result.fetchone()
        if not row:
            return None
        return JournalEntrySchema(
            entry_id=row.entry_id,
            user_id=row.user_id,
            entry_date=row.entry_date,
            content=row.content,
        )

    # ------------------------------------------------------------------
    # History (joined view: readiness + reflection + journal)
    # ------------------------------------------------------------------

    async def get_history(
        self, db: AsyncSession, user_id: int, days: int = 90
    ) -> list[JournalHistoryRowSchema]:
        result = await db.execute(text("""
            SELECT
                d.entry_date,
                r.overall_feel, r.legs_feel, r.upper_body_feel, r.joint_feel,
                r.injury_note, r.time_available, r.going_out_tonight,
                wr.session_rpe, wr.session_quality, wr.load_feel, wr.notes AS reflection_notes,
                je.content AS journal_note
            FROM (
                SELECT entry_date FROM daily_readiness
                WHERE user_id = :uid AND entry_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                UNION
                SELECT entry_date FROM workout_reflection
                WHERE user_id = :uid AND entry_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                UNION
                SELECT entry_date FROM journal_entries
                WHERE user_id = :uid AND entry_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            ) d
            LEFT JOIN daily_readiness r
                ON r.entry_date = d.entry_date AND r.user_id = :uid
            LEFT JOIN workout_reflection wr
                ON wr.entry_date = d.entry_date AND wr.user_id = :uid
            LEFT JOIN journal_entries je
                ON je.entry_date = d.entry_date AND je.user_id = :uid
            ORDER BY d.entry_date DESC
        """), {"uid": user_id, "days": days})

        return [
            JournalHistoryRowSchema(
                entry_date=row.entry_date,
                overall=row.overall_feel,
                legs=row.legs_feel,
                upper=row.upper_body_feel,
                joints=row.joint_feel,
                injury_note=row.injury_note,
                time_available=row.time_available,
                going_out=row.going_out_tonight,
                rpe=row.session_rpe,
                session_quality=row.session_quality,
                load_feel=row.load_feel,
                reflection_notes=row.reflection_notes,
                journal_note=row.journal_note,
            )
            for row in result.fetchall()
        ]
