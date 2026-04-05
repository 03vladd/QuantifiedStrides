# QuantifiedStrides

> Personal sports scientist in an app. Production-grade athlete performance monitoring — ingests multi-modal time-series data, runs an algorithmic intelligence layer, and surfaces actionable daily training recommendations.

QuantifiedStrides is a fusion of sports science, data engineering, and applied ML. It pulls from wearables, environmental APIs, and manual input to build a complete picture of athletic performance over time. The intelligence layer is fully algorithmic — Claude API handles only narrative translation, not decision-making.

---

## Architecture

```
Data Sources
  ├── Garmin Connect API    → workout.py / sleep.py / environment.py
  └── OpenWeatherMap API    → environment.py

FastAPI Backend (api/)
  ├── Auth                  JWT (HS256, 30-day) + email verification
  ├── Dashboard             ATL/CTL/TSB, HRV, muscle freshness, narrative
  ├── Training Load         TRIMP, ATL/CTL/TSB, ramp rate
  ├── Recovery              HRV z-score, muscle fatigue decay model
  ├── Alerts                Anomaly detection, overtraining flags
  ├── Recommendation        Daily session planner integrating all signals
  ├── Narrative             Claude API — pattern → language (RAG-grounded)
  └── RAG                   pgvector cosine similarity over coaching transcripts

PostgreSQL (Docker — pgvector/pgvector:pg16)
  ├── users / user_profile  (goal, gym_days, primary_sports JSONB, Garmin creds)
  ├── workouts              (HR zones, VO2max, biomechanics, GPS)
  ├── workout_metrics       (time-series HR/pace/cadence/power per workout)
  ├── sleep_sessions        (HRV, stages, body battery, sleep score)
  ├── daily_readiness       (morning feel, legs, joints, time available)
  ├── workout_reflection    (RPE, session quality, load feel)
  ├── strength_sessions / exercises / sets
  ├── exercises             (~797: 36 custom + 761 wger, full muscle/equipment taxonomy)
  └── knowledge_chunks      (pgvector embeddings — coaching transcripts for RAG)

React Frontend (Vite + shadcn/ui, port 5173)
  ├── Dashboard             Alerts, today's plan, ATL/CTL/TSB, muscle heatmap, narrative
  ├── Check-In              Morning readiness + post-workout reflection
  ├── Strength              Session builder, exercise search, progressive overload
  ├── Running               Biomechanics analytics
  ├── Training              Load history, workout log
  ├── Sleep                 Sleep history
  ├── Journal               Workout reflections timeline
  └── Profile               Sport picker, training goal, gym days, Garmin credentials
```

---

## Intelligence Layer

### Training Load (TRIMP / ATL / CTL / TSB)
- **TRIMP**: exponential HR-zone-weighted training impulse per session
- **ATL** (fatigue): 7-day EWMA of TRIMP
- **CTL** (fitness): 42-day EWMA of TRIMP
- **TSB** (form): CTL − ATL
- **Ramp rate**: week-over-week CTL change — flags excessive load increases

### Recovery Scoring
- **HRV trend**: rolling z-score against personal 30-day baseline
  - z < −1.5: suppressed → flag rest or easy day
  - z > +1.0: elevated → ready for quality work
- **Muscle fatigue decay**: `fatigue(t) = peak_load × e^(−λ × t)`, per muscle group, calibrated to fast/slow-twitch recovery rates

### Recommendation Engine
Integrates HRV status, TSB, muscle freshness map, weather, readiness inputs, sport priority weights, and training goal to output: recommended sport, session type, intensity zone, and exercise suggestions.

### Narrative (Claude API + RAG)
On dashboard load, pgvector similarity search retrieves top-k coaching transcript chunks (Steve Magness, Peter Attia, Jack Daniels, Mikael Eriksson, Kolie Moore) and injects them into the Claude API prompt. Output is a grounded narrative explanation of detected patterns — not generic LLM output. Cached by sport profile.

---

## Running Locally

### Prerequisites
- Docker
- Python 3.11+
- Node.js 18+

### Setup

```bash
git clone https://github.com/03vladd/QuantifiedStrides.git
cd QuantifiedStrides

# Environment
cp .env.example .env
# Fill in: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#          JWT_SECRET, ANTHROPIC_API_KEY
#          SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Database (Docker — starts PostgreSQL with pgvector)
docker compose up -d

# Backend dependencies
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

### Run

```bash
# Backend — http://localhost:8000/docs
uvicorn api.main:app --reload --port 8000

# Frontend — http://localhost:5173
cd frontend && npm run dev

# Garmin sync (manual — or trigger via UI Sync button)
python workout.py
python sleep.py
python environment.py
```

---

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

Garmin credentials and external API keys (OpenWeatherMap) are stored per-user in `user_profile`, not in `.env`.

---

## Auth Flow

1. `POST /api/v1/register` — creates user, sends verification email
2. `GET /api/v1/verify-email?token=...` — marks email verified, issues JWT
3. `POST /api/v1/login` — returns JWT (30-day expiry)
4. All protected routes: `Authorization: Bearer <token>`

Multi-user from the start — `user_id` is always extracted from the JWT, never hardcoded.

---

## Sports Tracked

Running · Trail Running · Mountain Biking · Cycling · Indoor Cycling · Bouldering · Climbing · Hiking · Resort Skiing · Snowboarding · Swimming

---

## What's Built

- Auth: register / login / JWT / email verification, multi-user
- Garmin sync: workout + sleep + environment ingest, deduplication via `UNIQUE (user_id, start_time)`
- Dashboard: ATL/CTL/TSB, HRV status, muscle freshness heatmap, alerts, Claude narrative, weather, sleep and readiness summaries
- Strength logging: session builder, 797-exercise search, sets with progressive overload tracking
- Morning check-in / post-workout reflection
- Profile: sport picker, training goal, gym days/week, Garmin credentials
- pgvector RAG knowledge base with coaching transcript embeddings

## What's In Progress

- Exercise suggestions on Dashboard (engine outputs them, UI doesn't display yet)
- Goal-based recommendation differentiation (athlete / strength / hypertrophy)
- Running biomechanics page (analytics written, needs end-to-end wiring)
- `workout_metrics` time-series ingestion

## Planned

- Nutrition module (table exists, no API or UI)
- Injury tracking (table exists, no API or UI)
- Progress / trends page (1RM progression, VO2max trend, sleep patterns)
- Periodization planner (base → build → peak → taper anchored to race date)
- Automatic Garmin sync scheduler
- Garmin credential encryption at rest
