# QuantifiedStrides

Athlete performance monitoring system (UBB bachelor's thesis). Collects data from Garmin wearables and external APIs, storing it in a local SQL Server database for analysis.

## What It Does

The system is a **daily data pipeline** that pulls from three sources and stores everything in a local SQL Server database:

1. **Garmin Connect** → Latest workout activity + sleep session metrics
2. **OpenWeatherMap + Ambee** → Weather conditions, UV index, and pollen levels tied to each day's workout
3. **Manual CLI input** → Subjective wellness check-in (energy, mood, soreness, recovery, etc.)

## Data Storage

**Microsoft SQL Server** (`localhost`, database: `QuantifiedStridesDB`)
Connected via `pyodbc` with ODBC Driver 17 and Windows Trusted Connection (no SQL auth).

### Database Schema

```
Users
  └─ Workouts          (FK: UserID)
       ├─ EnvironmentData   (FK: WorkoutID)
       └─ WorkoutMetrics    (FK: WorkoutID — time-series per-workout data)
  └─ SleepSessions     (FK: UserID)
  └─ DailySubjective   (FK: UserID)
  └─ NutritionLog      (FK: UserID — schema defined, not yet implemented)
  └─ Injuries          (FK: UserID — schema defined, not yet implemented)
```

**Workouts** — sport, start/end time, calories, HR zones 1-5, VO2max, lactate threshold, running biomechanics (cadence, stride length, vertical oscillation, ground contact time), training volume (meters), location, date

**SleepSessions** — duration, sleep score, HRV, RHR, time in each sleep stage (deep/light/REM/awake), sleep stress, HRV status, Garmin Body Battery change

**EnvironmentData** — temperature, wind speed/direction, humidity, precipitation, pollen index (average of grass+tree+weed), UV index, linked to a WorkoutID

**DailySubjective** — energy level, mood, soreness, sleep quality, recovery (all 1–10), free-text reflection

**WorkoutMetrics** — time-series HR, pace, cadence, power per workout (schema defined, not yet populated)

## Architecture

No API layer. The system is a set of **standalone scripts run sequentially** by the orchestrator:

```
main.py
  ├── subprocess → workout.py         # Pull latest Garmin activity → Workouts table
  ├── subprocess → sleep.py           # Pull Garmin sleep data → SleepSessions table
  └── subprocess → environment.py     # Pull weather/pollen → EnvironmentData table

daily_subjective.py                   # Run separately (interactive CLI, requires terminal input)
```

Each data-collection script:
1. Opens its own DB connection
2. Fetches data from its source
3. Inserts into the relevant table
4. Closes the DB connection

Logs written to `quantified_strides.log` by `main.py`.

## External Dependencies

| Library | Purpose |
|---|---|
| `garminconnect` | Garmin Connect API client |
| `pyodbc` | SQL Server connectivity |
| `requests` | HTTP calls to weather/pollen APIs |

APIs used:
- **OpenWeatherMap** — current weather (`/data/2.5/weather`) and UV index (`/data/2.5/onecall`)
- **Ambee** — pollen data by lat/lng (`/latest/pollen/by-lat-lng`)

Location hardcoded to **Cluj-Napoca** (lat: 46.7667, lon: 23.6000).

## Running the Pipeline

```bash
# Run automated data collection (workout + sleep + environment)
python main.py

# Run the interactive daily check-in separately (requires terminal)
python daily_subjective.py

# Run individual scripts directly
python workout.py
python sleep.py
python enviroment.py   # note: filename has a typo (missing 'n')
```

## Known Bugs

### 1. Filename typo breaks `main.py`
- The file is named `enviroment.py` (missing 'n')
- `main.py:62` calls `run_script("environment.py")` (correct spelling)
- **Result:** environment data collection always fails silently when run via `main.py`
- **Fix:** rename the file to `environment.py`

### 2. `daily_subjective.py` SQL mismatch (runtime error)
- The INSERT statement lists **8 columns** but the VALUES clause has **9 `?` placeholders**
- **9 values** are passed, with `hrv` occupying the `Soreness` column slot
- The extra 9th value (`reflection`) has no matching column and will cause a SQL error
- The `HRV` column (present in the DB schema per `DailySubjective.plantuml`) is never inserted
- **Fix:** add `HRV` to the column list and align the values

### 3. `daily_subjective.py` cannot run via subprocess
- It uses `input()` for interactive prompts
- `main.py` runs scripts via `subprocess.run(..., capture_output=True)` which captures stdin
- **Result:** running `daily_subjective.py` through `main.py` would hang or fail
- **Current workaround:** run it directly in terminal

### 4. `workout.py` only fetches the most recent activity
- `client.get_activities(0, 1)` — fetches exactly 1 activity
- If two workouts happen on the same day, only one is captured

### 5. Hardcoded `UserID = 1` everywhere
- All scripts hardcode `UserID = 1` — the system only supports a single athlete

### 6. Placeholder workouts pollute the Workouts table
- Both `enviroment.py` and `daily_subjective.py` create fake "placeholder" workouts when no real workout exists for today
- These appear in analytics alongside real training sessions

## Security Issues (Must Fix Before Any Sharing)

**Credentials are hardcoded in source files:**
- `sleep.py:8` and `workout.py:8` — Garmin email and password in plaintext
- `enviroment.py:7-8` — OpenWeatherMap and Ambee API keys in plaintext

Move all secrets to environment variables or a `.env` file (use `python-dotenv`):

```python
import os
from dotenv import load_dotenv
load_dotenv()

GARMIN_EMAIL = os.environ["GARMIN_EMAIL"]
GARMIN_PASSWORD = os.environ["GARMIN_PASSWORD"]
OPENWEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]
AMBEE_API_KEY = os.environ["AMBEE_API_KEY"]
```

Add a `.env` file (never commit it) and add `.env` to `.gitignore`.

**Note:** Since these credentials are already in git history, you should rotate the Garmin password and regenerate the API keys regardless.

## Suggested Improvements

### Near-term (fix correctness)
1. Rename `enviroment.py` → `environment.py`
2. Fix the SQL column/value mismatch in `daily_subjective.py`
3. Move all credentials to environment variables
4. Add `.gitignore` (currently none exists) with `.env`, `*.log`, `.venv/`, `.idea/`

### Medium-term (improve reliability)
5. Share a single DB connection helper instead of opening/closing in each script
6. Add duplicate detection in `workout.py` — check if an activity with the same start time already exists before inserting
7. Replace placeholder workout creation with a nullable FK — `EnvironmentData.WorkoutID` could be NULL on rest days
8. Add `sleep.py` guard: check if a sleep record for today already exists before inserting

### Longer-term (thesis scope)
9. Add a REST API layer (FastAPI) to expose the collected data for a frontend or analytics dashboard
10. Implement the `WorkoutMetrics` time-series collection (lap/split data from Garmin)
11. Implement `NutritionLog` and `Injuries` modules (schema already designed)
12. Add a scheduler (e.g., Windows Task Scheduler or `APScheduler`) to run `main.py` automatically each morning
13. Multi-user support — remove hardcoded `UserID = 1`
