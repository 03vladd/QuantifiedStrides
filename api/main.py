"""
QuantifiedStrides FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000

API docs:
    http://localhost:8000/docs
    http://localhost:8000/redoc
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.settings import settings
from api.routers.v1 import dashboard, training, sleep, strength, checkin, running

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

app.include_router(dashboard.router, prefix=_V1)
app.include_router(training.router,  prefix=_V1)
app.include_router(sleep.router,     prefix=_V1)
app.include_router(strength.router,  prefix=_V1)
app.include_router(checkin.router,   prefix=_V1)
app.include_router(running.router,   prefix=_V1)


@app.get("/health")
async def health():
    return {"status": "ok"}
