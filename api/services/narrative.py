"""
NarrativeService — Phase 4 of the recommendation stack.

Generates a personalised 2-3 sentence narrative grounded in RAG coaching
knowledge. Results are cached per user per day — Claude is only called when
the cache is empty or the underlying inputs have changed.
"""

import hashlib
from datetime import date

import anthropic
from sqlalchemy import text

from api.schemas.dashboard import RecommendationSchema
from api.services.rag import retrieve
from config import ANTHROPIC_API_KEY
from sqlalchemy.ext.asyncio import AsyncSession


_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SPORT_NAMES = {
    "trail_run":  "trail running",
    "xc_mtb":     "XC MTB",
    "climbing":   "climbing",
    "ski":        "skiing",
    "snowboard":  "snowboarding",
    "road_run":   "road running",
    "bike":       "cycling",
}


def _make_cache_key(rec: RecommendationSchema, context: dict, sports: str = "") -> str:
    """Hash the inputs that actually drive the narrative content."""
    parts = "|".join([
        rec.primary or "",
        rec.intensity or "",
        rec.why or "",
        str(round(context.get("tsb") or 0)),
        context.get("hrv_status") or "",
        str(context.get("sleep_score") or ""),
        str(context.get("readiness_overall") or ""),
        sports,  # sport preferences must be part of the key
    ])
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


async def _get_cached(user_id: int, today: date, cache_key: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        text("SELECT narrative FROM narrative_cache WHERE user_id = :uid AND date = :d AND cache_key = :k"),
        {"uid": user_id, "d": today, "k": cache_key},
    )
    row = result.fetchone()
    return row.narrative if row else None


async def _store_cache(user_id: int, today: date, cache_key: str, narrative: str, db: AsyncSession) -> None:
    await db.execute(
        text("""
            INSERT INTO narrative_cache (user_id, date, cache_key, narrative)
            VALUES (:uid, :d, :k, :n)
            ON CONFLICT (user_id, date) DO UPDATE
                SET cache_key = EXCLUDED.cache_key,
                    narrative  = EXCLUDED.narrative,
                    created_at = NOW()
        """),
        {"uid": user_id, "d": today, "k": cache_key, "n": narrative},
    )
    await db.commit()


async def _fetch_sports(user_id: int, db: AsyncSession) -> str:
    import json as _json
    try:
        result = await db.execute(
            text("SELECT primary_sports FROM user_profile WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return ""
        raw = row[0]
        # asyncpg returns JSONB as a dict; psycopg2 returns it as a string — handle both
        data = _json.loads(raw) if isinstance(raw, str) else raw
        if not data:
            return ""
        sports = sorted(data.items(), key=lambda x: x[1], reverse=True)
        names = [_SPORT_NAMES.get(k, k) for k, v in sports if v >= 1]
        return ", ".join(names)
    except Exception:
        return ""


def _build_rag_query(rec: RecommendationSchema, context: dict) -> str:
    parts = [rec.primary]
    if rec.intensity:
        parts.append(rec.intensity)
    if rec.why:
        parts.append(rec.why)
    hrv_status = context.get("hrv_status")
    if hrv_status and hrv_status != "normal":
        parts.append(f"HRV {hrv_status} training adaptation")
    tsb = context.get("tsb")
    if tsb is not None:
        if tsb < -10:
            parts.append("accumulated fatigue recovery")
        elif tsb > 10:
            parts.append("fresh legs performance readiness")
    return " ".join(parts)


def _build_system_prompt(chunks: list[dict], sports: str) -> str:
    knowledge = "\n\n".join(
        f"[{c['source_title']}]\n{c['content']}"
        for c in chunks
    )
    sports_line = f"whose primary sports are: {sports}" if sports else "who is a general athlete"
    return f"""You are a personal sports scientist writing for a serious athlete {sports_line}.

The training recommendation system has already decided what the athlete should do today based on their data. Your job is to explain *why* this makes physiological sense in 2-3 sentences — direct, specific, no filler.

When connecting training to sport performance, reference the athlete's actual sports (listed above) — don't default to generic trail running framing if it doesn't apply.

Ground your explanation in the coaching knowledge below. Reference it naturally — don't cite it explicitly.

--- COACHING KNOWLEDGE ---
{knowledge}
--- END ---

Rules:
- 2-3 sentences maximum
- No motivational fluff ("you've got this", "great job", etc.)
- Be specific about the physiology — name the adaptation, the system, the mechanism
- Write in second person ("Your aerobic system...", "At this TSB...")
- Never tell the athlete what to do — the plan is already set, just explain it"""


async def generate_narrative(
    rec: RecommendationSchema,
    context: dict,
    db: AsyncSession,
    user_id: int = 1,
    today: date | None = None,
) -> str | None:
    if today is None:
        today = date.today()
    try:
        # Sports must be fetched before cache check — they're part of the cache key
        sports = await _fetch_sports(user_id, db)
        cache_key = _make_cache_key(rec, context, sports)

        # Return cached narrative if inputs haven't changed
        cached = await _get_cached(user_id, today, cache_key, db)
        if cached:
            return cached

        # Generate fresh narrative
        query  = _build_rag_query(rec, context)
        chunks = await retrieve(query, db, k=4)
        system = _build_system_prompt(chunks, sports)

        notes_str = ""
        if rec.notes:
            notes_str = "\nNotes from the engine: " + "; ".join(rec.notes)

        user_msg = (
            f"Today's recommendation: {rec.primary}\n"
            f"Intensity: {rec.intensity or 'N/A'}\n"
            f"Duration: {rec.duration or 'N/A'}\n"
            f"Why (engine reasoning): {rec.why or 'N/A'}"
            f"{notes_str}\n\n"
            f"TSB (form): {context.get('tsb', 'unknown')}\n"
            f"HRV status: {context.get('hrv_status', 'unknown')}\n"
            f"Sleep score: {context.get('sleep_score', 'unknown')}\n"
            f"Overall readiness: {context.get('readiness_overall', 'unknown')}/10\n\n"
            f"Write the narrative."
        )

        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        narrative = response.content[0].text.strip()

        # Store in cache
        await _store_cache(user_id, today, cache_key, narrative, db)
        return narrative

    except Exception:
        return None
