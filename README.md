# QuantifiedStrides

> A personal athlete data intelligence platform — built to track, analyze, and visualize every aspect of training, sleep, recovery, and lifestyle in one centralized system.

QuantifiedStrides is a fusion of sports science, data engineering, and self-optimization. It pulls from wearables, environmental APIs, and manual input to build a complete picture of athletic performance over time. The real power isn't just storing data — it's the analysis and visibility layer on top of it.

---

## What It Does

### Data Collection Pipeline
Automated daily ingestion from multiple sources:

| Source | Data |
|---|---|
| **Garmin Connect** | Workouts (HR zones, VO2max, cadence, power, GPS), sleep sessions (HRV, stages, body battery), workout time-series metrics |
| **OpenWeatherMap** | Temperature, wind, precipitation, UV index |
| **Ambee** | Pollen levels (grass, tree, weed) |
| **Manual input** | Morning readiness check-in, post-workout reflection, free-text journal |

### Streamlit Dashboard
A multi-page interactive web app running locally:

| Page | Purpose |
|---|---|
| **Home** | Daily recommendation engine, fitness snapshot (CTL/ATL/TSB), HRV status, muscle freshness, alerts |
| **Check-In** | Morning readiness form + post-workout RPE/quality reflection |
| **Strength Log** | Session builder with per-set editing, custom exercise library with full tagging |
| **Analytics** | Training load history, HRV/sleep trends, 1RM progression, weekly volume |
| **Running Analytics** | Grade-adjusted pace, aerobic decoupling, biomechanics trends, terrain response |
| **Workout History** | Per-activity deep-dive: HR zones, time-series charts, GPS route, running analytics, strength exercise list |
| **Sleep History** | Per-night detail: stages breakdown, HRV context, quality flags, trend charts |
| **Journal** | Free-text daily entries + history timeline combining readiness, reflections, and notes |

---

## Architecture

```
Data Sources
  ├── Garmin Connect API    → workout.py / sleep.py / workout_metrics.py
  ├── OpenWeatherMap API    → environment.py
  └── Ambee Pollen API     → environment.py

Orchestrator: main.py (runs pipeline scripts sequentially)

PostgreSQL Database
  ├── workouts              (GPS, HR zones, VO2max, biomechanics, power)
  ├── workout_metrics       (time-series HR/pace/cadence/altitude per workout)
  ├── sleep_sessions        (HRV, stages, body battery, sleep score)
  ├── daily_readiness       (morning feel, legs, joints, time available)
  ├── workout_reflection    (RPE, session quality, notes)
  ├── journal_entries       (free-text daily notes)
  ├── strength_sessions     (date, session type)
  ├── strength_exercises    (exercise order, name, notes)
  ├── strength_sets         (reps/duration, weight, modifiers)
  └── exercises             (full taxonomy: muscles, equipment, joint stress, sport carryover)

Analytics Layer (analytics/)
  ├── running_economy.py    (Grade-Adjusted Pace, aerobic decoupling, REI)
  ├── biomechanics.py       (fatigue signature, cadence-speed profile)
  └── terrain_response.py   (HR-gradient curve, grade cost model, optimal gradient)

Supporting Modules
  ├── recovery.py           (muscle fatigue decay model, HRV trend)
  ├── training_load.py      (CTL/ATL/TSB via impulse-response model)
  ├── recommend.py          (daily training recommendation engine)
  ├── alerts.py             (threshold-based training/recovery alerts)
  ├── options.py            (DB-backed dropdown options for all UI forms)
  └── session.py            (user identity — single swap point for future auth)

Streamlit Dashboard (app.py + pages/)
```

---

## Key Analytics

### Training Load (Performance Management Chart)
CTL (chronic), ATL (acute), and TSB (form) computed via the Banister impulse-response model. Ramp rate tracked for overreaching detection.

### Running Economy
- **Grade-Adjusted Pace (GAP)** — Minetti et al. (2002) metabolic cost polynomial, converts hilly paces to flat equivalents
- **Aerobic Decoupling** — Pa:HR ratio drift between first and second halves of a run; <5% = good aerobic base
- **Running Economy Index (REI)** — power-to-speed ratio (falls back to HR-to-speed if power not available)

### Muscle Freshness Model
Per-muscle fatigue modeled as exponential decay: `fatigue(t) = peak_load × e^(−λ × t_days)`, where λ = ln(2) / half_life.

Fatigue accumulates from two sources:
- **Strength sessions** — scaled by systemic fatigue rating × number of sets
- **Endurance workouts** — sport-specific muscle load per hour (running loads quads/calves differently than cycling or bouldering), scaled by TSS intensity factor when available

### Terrain Response
HR response by gradient band, grade cost model (linear regression HR ~ gradient), optimal gradient identification.

---

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (local)
- Garmin Connect account
- OpenWeatherMap API key
- Ambee API key

### Install
```bash
git clone https://github.com/your-username/QuantifiedStrides.git
cd QuantifiedStrides
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# Fill in: GARMIN_EMAIL, GARMIN_PASSWORD, OPENWEATHER_API_KEY, AMBEE_API_KEY
#          DB_USER, DB_PASSWORD, ANTHROPIC_API_KEY
```

### Database
```bash
psql -U your_user -d your_db -f schema.sql
```

### Run
```bash
# Pull today's data from Garmin + weather
python main.py

# Launch the dashboard
streamlit run app.py
```

The dashboard also has a **⬇️ Sync** button that triggers the pipeline without leaving the browser.

---

## Sports Tracked

Running · Trail Running · Mountain Biking · Cycling · Indoor Cycling · Bouldering · Climbing · Hiking · Resort Skiing · Snowboarding · Swimming

---

## Vision

This is the foundation for an end-to-end self-tracking engine — building not just performance, but awareness, resilience, and informed decision-making.

Planned directions:
- **Lifestyle correlations** — linking poor sleep to slower intervals, weather to perceived effort, nutrition to recovery
- **Injury forecasting** — detecting overreaching patterns before they become injuries
- **Weekly automated reports** — shareable summaries of training load, energy trends, and recovery
- **Investigative analysis** — Jupyter notebooks for correlation mining across metrics
- **Multi-user / open-source** — framework others can fork and adapt for their own performance stack
