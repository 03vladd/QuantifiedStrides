"""
QuantifiedStrides FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000

API docs:
    http://localhost:8000/docs
    http://localhost:8000/redoc
"""

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.settings import settings
from api.routers.v1 import auth, dashboard, training, sleep, strength, checkin, running, sync

app = FastAPI(
    title="QuantifiedStrides API",
    version="1.0.0",
    description="Athlete performance monitoring — training load, recovery, strength, and AI recommendations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# v1 routers
# ------------------------------------------------------------------

_V1 = "/api/v1"

app.include_router(auth.router,      prefix=_V1)
app.include_router(dashboard.router, prefix=_V1)
app.include_router(training.router,  prefix=_V1)
app.include_router(sleep.router,     prefix=_V1)
app.include_router(strength.router,  prefix=_V1)
app.include_router(checkin.router,   prefix=_V1)
app.include_router(running.router,   prefix=_V1)
app.include_router(sync.router,      prefix=_V1)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc), "traceback": traceback.format_exc()},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/db-test")
async def db_test():
    try:
        import asyncpg
        from api.settings import settings
        conn = await asyncpg.connect(settings.database_url.replace("postgresql+asyncpg", "postgresql"))
        row = await conn.fetchrow("SELECT COUNT(*) AS n FROM sleep_sessions")
        await conn.close()
        return {"status": "connected", "sleep_sessions": row["n"]}
    except Exception as exc:
        return {"status": "failed", "error": type(exc).__name__, "detail": str(exc)}
