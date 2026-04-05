"""
POST /api/v1/sync  — trigger Garmin + environment data collection.

Runs workout.py → workout_metrics.py → sleep.py → environment.py
sequentially as subprocesses and injects the user's Garmin credentials
as environment variables so multi-user sync works correctly.
"""

import asyncio
import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db

router = APIRouter(prefix="/sync", tags=["sync"])

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


async def _fetch_garmin_creds(user_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        text("SELECT garmin_email, garmin_password FROM user_profile WHERE user_id = :uid"),
        {"uid": user_id},
    )
    row = result.fetchone()
    if row and row.garmin_email and row.garmin_password:
        return {"GARMIN_EMAIL": row.garmin_email, "GARMIN_PASSWORD": row.garmin_password}
    # Fall back to .env values if not set on profile
    return {}


async def _run(script: str, extra_env: dict) -> dict:
    env = {**os.environ, **extra_env}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(_PROJECT_ROOT / script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(_PROJECT_ROOT),
        env=env,
    )
    stdout, stderr = await proc.communicate()
    return {
        "script": script,
        "ok":     proc.returncode == 0,
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
    }


@router.post("", status_code=200)
async def trigger_sync(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    creds = await _fetch_garmin_creds(user_id, db)
    results = []

    workout = await _run("workout.py", creds)
    results.append(workout)

    if workout["ok"]:
        results.append(await _run("workout_metrics.py", creds))

    results.append(await _run("sleep.py", creds))
    results.append(await _run("environment.py", creds))

    return {"ok": all(r["ok"] for r in results), "results": results}
