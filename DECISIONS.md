# QuantifiedStrides — Design Decisions

This document records every significant decision made about how the recommendation engine, exercise selection, formulas, and data models work. Written so that future-me (or Claude) can understand *why* things are the way they are.

---

## Training Load Model

### Formula: TRIMP (Edwards 5-zone model)

Each workout contributes a training stress score calculated as:

```
TRIMP = Σ (time_in_zone_minutes × zone_weight)
```

Zone weights (Edwards model):
| Zone | Weight |
|------|--------|
| 1 | 1.0 |
| 2 | 1.5 |
| 3 | 2.0 |
| 4 | 3.0 |
| 5 | 4.0 |

Time in zones comes from Garmin (`time_in_hr_zone_1..5` stored in seconds).

**Fallback for strength sessions without Garmin HR data:**
`TRIMP = total_sets × 2.5`
Calibrated so a typical 16-set session ≈ 40 TRIMP, roughly equivalent to a moderate aerobic effort.

### ATL / CTL / TSB

Exponentially weighted averages (EWA) of daily TRIMP:

```
CTL = CTL_prev × (1 - 1/42) + load × (1/42)   # 42-day constant → fitness
ATL = ATL_prev × (1 - 1/7)  + load × (1/7)    # 7-day constant  → fatigue
TSB = CTL - ATL                                 # form / freshness
```

TSB interpretation:
- `> +10`: very fresh — peak performance window
- `+5..+10`: fresh — lean toward the harder end
- `-5..+5`: neutral — fitness and fatigue in balance
- `-15..-5`: productive fatigue — building fitness, train as planned
- `< -15`: overreached — back off

### Ramp Rate

`ramp_rate = CTL_today - CTL_7_days_ago`

Safe ceiling: ~5–7 CTL/week. Above 8 triggers a warning alert.

### ACWR (Acute:Chronic Workload Ratio)

`ACWR = ATL / CTL` (only computed when CTL > 5)

Optimal range: 0.8–1.3
- `> 1.5`: high injury risk (critical alert)
- `> 1.3`: above safe zone (warning)
- `< 0.8`: detraining risk

---

## HRV Analysis

### Baseline and Deviation

7-day rolling mean and SD of overnight HRV from sleep sessions:

```
deviation = (last_hrv - baseline_mean) / baseline_sd
```

SD floored at 1.0 to avoid division-by-zero for very consistent sleepers.

Status thresholds:
- `deviation > +0.5 SD`: elevated (good recovery signal)
- `deviation < -1.0 SD`: suppressed (parasympathetic withdrawal)

### Trend

3-day mean vs 7-day mean:
- `+3 ms`: rising
- `-3 ms`: falling
- Otherwise: stable

---

## Muscle Fatigue Decay Model

Models residual fatigue per muscle as exponential decay:

```
fatigue(t) = peak_load × e^(−λ × t_days)
where λ = ln(2) / half_life
```

Peak load per exercise: `systemic_fatigue × num_sets`

Secondary muscle contribution: 40% of primary load.

**Half-lives by muscle group (days):**
| Muscle | Half-life |
|--------|-----------|
| lower_back, hip_flexors | 3.0 |
| lats, upper_back, rhomboids, traps | 2.5 |
| chest, quads, hamstrings, glutes, hip_abductors, hip_adductors | 2.0 |
| Everything else (delts, biceps, triceps, calves, etc.) | 1.5 |

Rationale: slow-twitch dominant / postural muscles (back, glutes) recover slower than fast-twitch / smaller muscles (delts, biceps).

**Freshness score:**
```
freshness = 1 - min(1, accumulated_fatigue / 50)
```

Calibration cap of 50: one hard session (e.g. 3 chest exercises × 4 sets × systemic_fatigue 3 = 36 primary + secondary contributions ≈ 50).

Freshness is used as a multiplier in exercise ranking — prefer muscles that have recovered more.

---

## Exercise Selection Algorithm

### Exercise Pool

~797 exercises: 36 custom + 761 imported from wger API, labeled with Claude Haiku (batch=20).

Each exercise has:
- `movement_pattern`: the structural slot it fills (e.g. `horizontal_push`, `hinge`, `vertical_pull`)
- `quality_focus`: `power` | `strength` | `hypertrophy` | `stability` | `endurance`
- `contraction_type`: `explosive` | `concentric` | `isometric`
- `primary_muscles`, `secondary_muscles`: JSONB arrays
- `systemic_fatigue`, `cns_load`: 1–5 scale
- `bilateral`: bool

### Session Type → Allowed Muscles

Upper sessions: pushing muscles (chest, front/side delt, triceps) + pulling muscles (lats, upper_back, rhomboids, traps, rear_delt, biceps) + upper accessories.

Lower sessions: quads, hamstrings, glutes, hip flexors, calves, lower_back, abs, obliques, hip abductors/adductors.

### Ranking Formula

```
score = deficit_score(muscles)
      × quality_fit(quality_focus)
      × avg_freshness(muscles)
      × familiar_factor(last_done)
      × recency_factor(last_done)
```

**deficit_score:** How urgently these muscles need training this week.
```
deficit = Σ max(0, target_freq[m] - weekly_freq[m]) × importance[m]
```
Target frequency derived from muscle importance scores (normalized from 1–10 ratings per muscle).

**quality_fit:** Matches exercise quality to day intensity.
| Quality | Heavy day | Light day |
|---------|-----------|-----------|
| power | 2 | 1 |
| strength | 2 | 2 |
| hypertrophy | 1 | 2 |
| stability | 0 | 1 |
| endurance | 0 | 1 |

**avg_freshness:** Mean freshness score across primary muscles (0–1). Deprioritises recently hammered muscles.

**familiar_factor:** Exercises never logged by the user score 0.1× — strongly deprioritised. Only surface novel exercises when no familiar alternative fits. This ensures the engine defaults to your training routine.

**recency_factor:** Avoids repeating the same exercise within a weekly cycle.
- Done ≤ 7 days ago: 0.2×
- Done 8–14 days ago: 0.8×
- Older / never done: 1.0×

Rationale: 7-day window matches a 4x/week split where each day occurs once per week.

### Selection Phases

**Phase 0 — Explosive opener:**
Guarantee one `contraction_type = 'explosive'` exercise opens every session. Primes the CNS, built on plyometrics research showing explosive work is best when fresh.

**Phase 1 — Pattern coverage:**
Guarantee one exercise per focus pattern (e.g. `vertical_pull`, `hinge`) — ensures no movement pattern goes unrepresented.

**Phase 2 — Fill to 5:**
Fill remaining slots with overlap check: no exercise added if it shares ≥ 2 primary muscles already in the session.

### TSB Overrides on Intensity

TSB directly overrides the heavy/light day decision:
- `TSB > +10`: force heavy (CNS is fresh, use it)
- `TSB < -15`: force light (accumulated fatigue, don't dig deeper)

---

## Progression Logic

### Power exercises (bodyweight / plyometric)
Never add weight. Cue: focus on quality — height, distance, reactive contact time.

### Power exercises (weighted)
Same reps, increase weight when 5 reps feels consistently easy (RPE ≤ 7).

### Strength / hypertrophy (bodyweight)
Reps → 15, then add weight.

### Strength / hypertrophy (weighted)
6–10 rep scheme. Progress: +2.5 kg when all sets ≥ 8 reps (last set not ≤ 6).

### Stability / endurance
Maintain reps/duration — progression only when technique is solid.

---

## Alert System

### Severity Levels
- `critical`: Act now, do not train hard today
- `warning`: Take note, consider adjusting
- `info`: Noteworthy, no action required

### Alert Triggers

| Signal | Warning | Critical |
|--------|---------|----------|
| ACWR | > 1.3 | > 1.5 |
| TSB | < -15 | < -25 |
| Consecutive training days | ≥ 4 | ≥ 6 |
| CTL ramp rate | > 8/week | — |
| RHR above baseline | +5 bpm | +8 bpm |
| HRV deviation | < -1.0 SD | < -1.5 SD |
| Sleep score (3-day avg) | < 50 | — |
| Sleep hours (3-day avg) | < 6.5h | — |
| Overall feel | ≤ 5/10 | ≤ 3/10 |
| Energy level | ≤ 3/10 | — |
| Multi-metric illness (2+ of: RHR↑, HRV↓, sleep<55) | — | triggered |
| Soreness ≥7 + went out + HRV dip < -0.5 SD | — | triggered |

---

## Recommendation Engine Flow

```
1. Get today's readiness (morning check-in)
2. Get yesterday's training (gym session or Garmin workout)
3. Get last night's sleep
4. Get current weather
5. Get recent load (consecutive days, weekly volume)
6. Get gym analysis (last 2 upper + last 2 lower sessions)
7. Compute training load metrics (CTL/ATL/TSB/ACWR)
8. Check HRV status
9. Run alert system
10. Apply hard decision rules (injury, weather, time constraints)
11. Build recommendation:
    - Determine primary activity (run / bike / gym / rest / active recovery)
    - If gym: determine session type (upper/lower), intensity (heavy/light), focus patterns
    - TSB overrides intensity decision
    - Select 5 exercises via ranking formula
    - Build progressive set/weight suggestions per exercise
12. Output: primary recommendation + why + exercises with weights
```

---

## Data Sources

| Source | Data | Method |
|--------|------|--------|
| Garmin Connect | Workouts (HR zones, biomechanics, VO2max), sleep (HRV, RHR, stages, body battery) | `garminconnect` Python library |
| OpenWeatherMap | Temperature, wind, rain | REST API |
| Ambee | Pollen index (grass + tree + weed average) | REST API |
| Manual (Streamlit) | Morning readiness, post-workout reflection, strength sessions | Forms |
| wger | Exercise database (761 exercises) | REST API + Claude Haiku labeling |

Location: dynamic — uses Garmin GPS coordinates (`start_latitude`, `start_longitude`) from the day's workout when available; falls back to IP geolocation via `ipinfo.io` on rest days. No hardcoded coordinates.

---

## Running Analytics Module (`analytics/`)

### Grade-Adjusted Pace (GAP)

Uses Minetti et al. (2002) metabolic cost of running on slopes:

```
Cr(g) = 155.4g⁵ - 30.4g⁴ - 43.3g³ + 46.3g² + 19.5g + 3.6
```

Where `g` is gradient as a dimensionless fraction (not %).

```
GAP multiplier = Cr(0) / Cr(g)
GAP = actual_pace × GAP_multiplier
```

Clamped to ±45% gradient (beyond that the polynomial is unreliable for running).
`Cr(0) = 3.6 J/kg/m` is the flat-ground reference.

**Why Minetti over simpler models (e.g. Strava's +10s/km per 1%):**
Minetti is a 5th-degree polynomial calibrated from actual oxygen consumption measurements on treadmills at varying grades. The linear approximation breaks down above ~6% grade. Since Vlad does trail running with steep grades, the polynomial is worth the extra complexity.

### Aerobic Decoupling

Splits each run into two equal halves by data point count.
Computes `Pa:HR ratio = speed_per_hr = (1/pace) / heart_rate` for each half.

```
decoupling_pct = (ratio_first - ratio_second) / ratio_first × 100
```

Thresholds:
- `< 5%`: aerobically efficient
- `5–10%`: moderate cardiac drift
- `> 10%`: significant cardiac drift — aerobic base needs work

Requires ≥ 40 valid data points. Filters: pace 0–20 min/km, HR > 40 bpm.

**Why speed (not pace) in the ratio:**
Speed (m/s) is proportional to metabolic output. Pace (min/km) is inversely proportional, so speed gives a ratio where "higher = better" in both halves, making the comparison intuitive.

### Running Economy Index (REI)

Primary (power meter / Stryd available):
```
REI = avg_power (W) / avg_speed (m/s)
```
Lower = more economical. Comparable across different paces.

Fallback (no power):
```
REI = avg_HR / avg_speed (m/s)
```
A proxy. Less precise but still captures fitness trends.

Speed derived from pace: `speed_ms = 1000 / (pace_min_per_km × 60)`.

### Fatigue Signature

Compares first and last `window_pct` (default 20%) of a run's data points.

Per-metric drift:
- `drift = late_avg - early_avg`
- `drift_pct = (late - early) / early × 100`

Composite fatigue score (0–100):
```
score = mean(
    min(100, GCT_drift_pct × 5),
    min(100, HR_drift_pct  × 10),
    min(100, -cadence_drift_pct × 10)
)
```

Calibration: GCT and HR weights chosen so a 5% GCT rise contributes ~25 pts and a 5% HR rise contributes ~50 pts. Cadence drop penalised at same rate as HR rise.

Requires ≥ 50 data points. Window floor: 10 points.

### Terrain Response — HR-Gradient Curve

Seven gradient bands: steep_down (<-8%), down (-8 to -4%), slight_down (-4 to -1%), flat (-1 to 1%), slight_up (1–4%), up (4–8%), steep_up (>8%).

For each band: avg HR, avg pace, avg GAP, efficiency (speed_ms / avg_HR).

Requires ≥ 10 data points per band to include a band in results.

### Grade Cost Model

Linear regression across all (gradient_pct, heart_rate) data points:

```
HR = slope × gradient_pct + intercept
```

`slope` = your personal HR cost per 1% gradient increase.

Compared against Minetti theoretical:
```
minetti_expected = (Cr(0.01) / Cr(0.0) - 1.0) × mean_HR
```

Ratio interpretation:
- `> 1.2×`: paying more HR for gradient than theory predicts → uphill economy weak
- `< 0.8×`: paying less → strong uphill economy
- Otherwise: tracks model closely

Caveat: confounded by pace variation across gradients. The model is descriptive, not causal. Use the per-pace-band notebook analysis for a cleaner estimate.

### Optimal Gradient Finder

Groups (gradient_pct, HR, pace) into 2% buckets.
Metric: `speed_ms / HR` (speed per heartbeat — higher = better).
The bucket with the highest mean efficiency is the "optimal gradient."

Requires ≥ 20 data points per bucket. Gradient range: -20 to +20%.

---

## Analytics Architecture

Three tiers:

```
notebooks/  →  explore patterns, validate hypotheses, one-off analysis
analytics/  →  production functions, called by both Streamlit and notebooks
pages/      →  Streamlit charts, daily-use dashboards
```

**Why not put analytics logic directly in Streamlit pages:**
Keeps computation testable and reusable. Notebooks can call the same functions without going through Streamlit. Caching is applied at the Streamlit layer, not inside the analytics functions.

Investigative analysis is done ad hoc in Jupyter notebooks (not tracked in this repo) and findings are discussed before being encoded into the analytics module.
