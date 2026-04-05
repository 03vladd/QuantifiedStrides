# QuantifiedStrides

Personal sports scientist in an app. Production-grade athlete performance monitoring system — originally a UBB bachelor's thesis, now a real daily-use tool. Ingests multi-modal time-series data, runs an algorithmic intelligence layer, and surfaces actionable daily training recommendations.

## Collaboration Context

Vlad defines vision and direction. Claude handles implementation and consults on trade-offs before building. Vlad has deep exercise science knowledge (periodization, concurrent training, sport-specific programming) and ML fundamentals — the app encodes his knowledge, not generic rules. He's direct, won't accept lazy solutions, and will push back if something isn't good enough.

**LLM design philosophy:** Pattern detection and recommendations are algorithmic/ML. The Claude API handles only narrative — translating detected patterns into readable language. Not an LLM wrapper.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + asyncpg (PostgreSQL driver) |
| Database | PostgreSQL (`quantifiedstrides`) via Docker (`pgvector/pgvector:pg16`) |
| Frontend | React (Vite, port 5173) + shadcn/ui components |
| Auth | JWT (HS256, 30-day expiry) + email verification via SMTP |
| Narrative | Anthropic Claude API (`api/services/narrative.py`) |
| RAG | pgvector extension + `api/services/rag.py` |
| Config | `pydantic-settings` loading from `.env` |

## Running Locally

```bash
# Database (Docker)
docker compose up -d

# Backend
uvicorn api.main:app --reload --port 8000
# Docs: http://localhost:8000/docs

# Frontend
cd frontend && npm run dev
# App: http://localhost:5173

# Garmin sync (manual trigger)
python workout.py
python sleep.py
python environment.py
# or via API: POST /api/v1/sync/garmin
```

## Project Structure

### Backend — `api/`

```
api/
  main.py               # FastAPI app, CORS, router registration
  settings.py           # pydantic-settings config (DB, JWT, SMTP, Anthropic key)
  deps.py               # FastAPI Depends: get_db(), get_current_user()
  routers/v1/
    auth.py             # register, login, verify-email, me
    dashboard.py        # GET /dashboard — full daily summary
    training.py         # workout history, training load
    sleep.py            # sleep history
    strength.py         # strength sessions, exercises, sets
    checkin.py          # daily readiness + post-workout reflection
    running.py          # running biomechanics analytics
    sync.py             # POST /sync/garmin — triggers Garmin pipeline
  services/
    auth.py             # JWT issue/verify, password hash, email verification
    email.py            # SMTP email sending
    dashboard.py        # assembles full dashboard payload
    training_load.py    # TRIMP, ATL, CTL, TSB, ramp rate
    recovery.py         # HRV trend z-score, muscle fatigue decay model
    alerts.py           # anomaly detection, overtraining alerts
    recommendation.py   # daily training recommendation engine
    narrative.py        # Claude API call — narrative from detected patterns
    rag.py              # pgvector similarity search for knowledge injection
    checkin.py          # readiness + reflection CRUD
    strength.py         # strength session/exercise/set CRUD + 1RM
    running.py          # running biomechanics computations
    sleep.py            # sleep history queries
    training.py         # workout history queries
  schemas/
    auth.py, checkin.py, dashboard.py, strength.py, training.py,
    sleep.py, running.py
```

### Intelligence Layer — root-level modules

```
training_load.py        # TRIMP, ATL/CTL/TSB, ramp rate, load history
recovery.py             # HRV rolling z-score, muscle fatigue decay
alerts.py               # anomaly detection, overtraining alerts, interpretations
recommend.py            # daily training recommendation (integrates all signals)
```

### Analytics — `analytics/`

```
analytics/
  biomechanics.py       # fatigue signature, cadence-speed relationship,
                        # per-workout biomechanics summary, longitudinal trends
  running_economy.py    # running economy analysis
  terrain_response.py   # elevation vs HR response
```

### Data Pipeline — root-level scripts

```
workout.py              # Garmin → workouts table
sleep.py                # Garmin → sleep_sessions table
environment.py          # OpenWeatherMap + Ambee → environment_data table
main.py                 # orchestrator (subprocess calls)
checkin.py              # morning readiness + post-workout reflection
strength_log.py         # gym session logger (Streamlit-era, superseded by API)
```

### Frontend — `frontend/src/`

```
pages/
  Dashboard.jsx         # home: alerts, today's plan, ATL/CTL/TSB, muscle freshness,
                        # narrative, weather, readiness summary
  CheckIn.jsx           # morning readiness + post-workout reflection forms
  Strength.jsx          # strength logging: session builder, exercise search
  Running.jsx           # running biomechanics analytics page
  Training.jsx          # training load history, workout log
  Sleep.jsx             # sleep history
  Journal.jsx           # workout reflections journal
  Profile.jsx           # sport picker, training goal, gym days, Garmin credentials
  Login.jsx / Register.jsx / Verify.jsx
components/
  SportPicker.jsx       # shared checkbox + select; used in Register and Profile
  layout/Sidebar.jsx
  ui/                   # shadcn: badge, button, card, separator, tabs
api/
  client.js             # axios instance with JWT bearer header
  auth.js, dashboard.js, checkin.js, strength.js, training.js,
  sleep.js, running.js, sync.js
```

### Supporting Scripts

```
db.py                   # psycopg2 connection helper (pipeline scripts)
config.py               # env var loader (.env) for pipeline scripts
ingest_knowledge.py     # one-time: embed coaching transcripts into pgvector
import_wger.py          # one-time: imported 761 exercises from wger API (Claude Haiku-labeled)
import_exercises.py     # one-time: imported 36 custom exercises
backfill_workouts.py    # one-time: backfilled historical Garmin data
backfill_sleep.py       # one-time: backfilled historical sleep data
migrate_cascade.py      # schema migration helper
schema.sql              # canonical PostgreSQL schema
dump.sql                # DB dump (loaded by Docker on first init)
```

## Database Schema (PostgreSQL)

```
users
  └─ user_profile          (FK: user_id — goal, gym_days_week, primary_sports JSONB)
  └─ workouts              (FK: user_id — sport, HR zones, VO2max, biomechanics, GPS)
       ├─ environment_data (FK: workout_id nullable — weather, UV, pollen per session)
       └─ workout_metrics  (FK: workout_id — time-series HR, pace, cadence, power)
  └─ sleep_sessions        (FK: user_id — duration, score, HRV, stages, Body Battery)
  └─ daily_readiness       (FK: user_id — overall/legs/upper/joint feel, time_available,
                                          going_out_tonight)
  └─ workout_reflection    (FK: user_id — session RPE, quality, load_feel, notes)
  └─ strength_sessions     (FK: user_id)
       └─ strength_exercises (FK: session_id)
            └─ strength_sets (FK: exercise_id — weight, reps, rpe)
  └─ nutrition_log         (FK: user_id — schema defined, not implemented)
  └─ injuries              (FK: user_id — schema defined, not implemented)
exercises                  (pool of ~797: 36 custom + 761 wger, movement pattern,
                            quality focus, primary/secondary muscles, equipment,
                            skill level — enables recommendation engine)
knowledge_chunks           (pgvector: coaching transcript embeddings for RAG)
```

**Key schema notes:**
- `environment_data.workout_id` is nullable — NULL means a rest day (no placeholder workouts)
- `workouts` has `UNIQUE (user_id, start_time)` — duplicate detection on ingest
- `daily_readiness` captures `going_out_tonight` (social schedule affects tomorrow's training)
- `workout_reflection.load_feel` is a -2 to +2 scale (too easy → too hard) — used to calibrate future recommendations
- `user_profile.primary_sports` is JSONB — keys are sport slugs, values are priority weights

## Intelligence Layer — How It Works

### Training Load (TRIMP / ATL / CTL / TSB)

- **TRIMP**: exponential HR-zone-weighted training impulse per session
- **ATL** (Acute Training Load, "fatigue"): 7-day exponentially weighted moving average of TRIMP
- **CTL** (Chronic Training Load, "fitness"): 42-day EWMA of TRIMP
- **TSB** (Training Stress Balance, "form"): CTL − ATL
- **Ramp rate**: week-over-week CTL change — flags excessive load increases

### Recovery Scoring

- **HRV trend**: rolling z-score of overnight HRV against a personal 30-day baseline
  - z < −1.5: suppressed (flag rest or easy day)
  - z > +1.0: elevated (ready for quality work)
- **Muscle fatigue decay**: per-muscle-group exponential decay model
  - Each strength set adds fatigue proportional to volume (sets × reps × weight)
  - Decay constant calibrated per muscle group (fast-twitch vs slow-twitch recovery rates)
  - Freshness score surfaced on Dashboard as muscle group heatmap

### Recommendation Engine (`recommend.py`)

Integrates:
1. HRV status + TSB → readiness signal
2. Muscle freshness map → which movements are available
3. Weather → outdoor/indoor decision
4. `daily_readiness` inputs → time available, going out tonight, injury notes
5. User's sport priority weights from `user_profile.primary_sports`
6. Training goal (athlete / strength / hypertrophy) → modulates volume and intensity targets
7. Hard rules (e.g. upper gym yesterday → no climbing; rain → no threshold runs)

Output: recommended sport, session type, intensity zone, exercise suggestions.

### Narrative Layer (`api/services/narrative.py` + `api/services/rag.py`)

When the dashboard loads:
1. `rag.py` runs a pgvector cosine similarity search against `knowledge_chunks` using the current context (e.g. "Z2 base building, suppressed HRV, ankle rehab")
2. Top-k coaching transcript chunks are retrieved and injected into the system prompt
3. Claude API generates a narrative explanation of detected patterns — grounded in real sports science, not generic LLM output

Knowledge base sources: Steve Magness, Peter Attia, Mikael Eriksson (Scientific Triathlon), Kolie Moore, Jack Daniels content.

Narrative is **cached** keyed by sports preferences — cache busts when sport profile changes.

## Auth Flow

1. `POST /api/v1/register` — creates user, sends verification email
2. `GET /api/v1/verify-email?token=...` — marks email verified, issues JWT
3. `POST /api/v1/login` — returns JWT (30-day expiry)
4. All protected routes: `Authorization: Bearer <token>` → `get_current_user()` extracts `user_id`

**Critical:** `user_id` is always extracted from the JWT via `get_current_user()`. Never hardcoded. This applies to all routers and services — the app is multi-user from the start.

## Garmin Sync

Two paths:
1. **Manual scripts** (`workout.py`, `sleep.py`, `environment.py`) — run directly from terminal
2. **API trigger** (`POST /api/v1/sync/garmin`) — frontend "Sync" button calls this

Garmin credentials stored in `user_profile` table (per user), not in `.env`. The sync router fetches them at runtime.

**Deduplication**: `workouts` has `UNIQUE (user_id, start_time)` — re-running sync won't create duplicates.

## Environment Variables (`.env`)

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quantifiedstrides
DB_USER=quantified
DB_PASSWORD=2026

JWT_SECRET=<secret>
ANTHROPIC_API_KEY=<key>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<email>
SMTP_PASSWORD=<app password>
```

External API keys (OpenWeatherMap, Ambee) are fetched per-user from `user_profile`, not global env vars.

## What's Built and Working

- Auth: register / login / JWT / email verification, multi-user
- Garmin sync pipeline: workout + sleep + environment ingest
- Dashboard: ATL/CTL/TSB, HRV status, muscle freshness heatmap, alerts, Claude narrative, weather, sleep summary, readiness summary
- Strength logging: session builder, exercise search (797 exercises), sets with progressive overload tracking
- Morning check-in / readiness form (`daily_readiness`)
- Post-workout reflection form (`workout_reflection`)
- Profile: sport picker, training goal, gym days/week, Garmin credentials
- Narrative cache keyed by sports preferences
- pgvector RAG knowledge base scaffold (`knowledge_chunks` table + `rag.py`)

## What's Half-Built

- **Exercise suggestions on Dashboard** — recommendation engine outputs them, Dashboard UI doesn't display them yet
- **Goal-based recommendation differentiation** — athlete vs strength vs hypertrophy logic not fully separated
- **Running biomechanics page** — `analytics/biomechanics.py` is written, `api/services/running.py` exists, frontend `Running.jsx` exists — needs wiring end-to-end
- **workout_metrics time-series** — schema exists, `backfill_workout_metrics.py` exists, API ingestion not fully implemented

## What Doesn't Exist Yet

- Nutrition module (table exists, no UI or API)
- Injury tracking (table exists, no UI or API)
- Progress / trends page (longitudinal view over months — 1RM progression, VO2max trend, sleep patterns)
- Periodization planner (base → build → peak → taper blocks anchored to race date)
- Automatic Garmin sync scheduler
- Garmin credential encryption at rest
- Error boundaries on frontend
- Input validation (Zod on frontend, stricter Pydantic on backend)

## Vlad's Training Context (as of 2026-03-14)

**Goal:** All-around mountain athlete — XC MTB, trail running, bouldering/climbing, skiing, snowboarding, hiking.

**Current phase:** Base building post-ankle sprain (freak climbing accident). ~4 weeks from returning to trail running. Z2 bike primary, reintroducing flat running.

**Weekly structure:**
- Mon: Upper gym + 30 min Z2 bike
- Tue: Climbing + 30 min Z2 bike
- Wed: Lower gym + prehab (Copenhagen planks, tibialis raises, ankle mobility)
- Thu: Rest or climbing (fatigue-dependent)
- Fri: Run or XC MTB
- Sat: Upper gym 2 (if didn't go out Fri night) + flat run
- Sun: Lower gym 2

**Hard rules (non-negotiable constraints in recommendation engine):**
- Upper gym yesterday → no climbing today (elbow/shoulder overlap)
- Lower gym yesterday → no running, only easy Z2 bike
- Rain → no threshold runs, no outdoor intensity
- Short time window → stationary bike Z2
- Going out tonight → no hard session tomorrow planned

**Sport priority (base building phase):**
1. Bike (XC specific — outdoor or Z2 stationary)
2. Run (road before trail, flat before hills)
3. Climbing (maintenance only)
