-- QuantifiedStrides PostgreSQL Schema
-- Run this once against a fresh database: psql -d quantifiedstrides -f schema.sql

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    name          VARCHAR(100),
    date_of_birth DATE
);

-- Default single athlete
INSERT INTO users (name) VALUES ('Athlete');

CREATE TABLE user_profile (
    user_id        INT PRIMARY KEY REFERENCES users(user_id),
    goal           VARCHAR(20) NOT NULL CHECK (goal IN (
                       'athlete', 'strength', 'hypertrophy',
                       'bodybuilding', 'powerlifting')),
    gym_days_week  INT NOT NULL CHECK (
                       (goal NOT IN ('bodybuilding','powerlifting') AND gym_days_week BETWEEN 2 AND 4)
                       OR
                       (goal IN ('bodybuilding','powerlifting') AND gym_days_week BETWEEN 2 AND 6)
                   ),
    primary_sports JSONB DEFAULT '{}'   -- e.g. {"xc_mtb": 5, "trail_run": 5, "climbing": 4}
);

CREATE TABLE workouts (
    workout_id                SERIAL PRIMARY KEY,
    user_id                   INT NOT NULL REFERENCES users(user_id),
    sport                     VARCHAR(50),
    start_time                TIMESTAMP,
    end_time                  TIMESTAMP,
    workout_type              VARCHAR(100),
    calories_burned           INT,
    avg_heart_rate            INT,
    max_heart_rate            INT,
    vo2max_estimate           FLOAT,
    lactate_threshold_bpm     INT,
    time_in_hr_zone_1         INT,
    time_in_hr_zone_2         INT,
    time_in_hr_zone_3         INT,
    time_in_hr_zone_4         INT,
    time_in_hr_zone_5         INT,
    training_volume           FLOAT,
    avg_vertical_oscillation  FLOAT,
    avg_ground_contact_time   FLOAT,
    avg_stride_length         FLOAT,
    avg_vertical_ratio        FLOAT,
    avg_running_cadence       FLOAT,
    max_running_cadence       FLOAT,
    location                  VARCHAR(100),
    start_latitude            FLOAT,
    start_longitude           FLOAT,
    workout_date              DATE,
    UNIQUE (user_id, start_time)
);

CREATE TABLE sleep_sessions (
    sleep_id              SERIAL PRIMARY KEY,
    user_id               INT NOT NULL REFERENCES users(user_id),
    sleep_date            DATE,
    duration_minutes      INT,
    sleep_score           FLOAT,
    hrv                   FLOAT,
    rhr                   INT,
    time_in_deep          INT,
    time_in_light         INT,
    time_in_rem           INT,
    time_awake            INT,
    avg_sleep_stress      FLOAT,
    sleep_score_feedback  VARCHAR(100),
    sleep_score_insight   VARCHAR(100),
    overnight_hrv         FLOAT,
    hrv_status            VARCHAR(50),
    body_battery_change   INT,
    UNIQUE (user_id, sleep_date)
);

-- workout_id is nullable: NULL means a rest day (no linked workout)
CREATE TABLE environment_data (
    env_id            SERIAL PRIMARY KEY,
    workout_id        INT REFERENCES workouts(workout_id),
    record_datetime   TIMESTAMP,
    location          VARCHAR(100),
    temperature       FLOAT,
    wind_speed        FLOAT,
    wind_direction    FLOAT,
    humidity          FLOAT,
    precipitation     FLOAT,
    grass_pollen      FLOAT,
    tree_pollen       FLOAT,
    weed_pollen       FLOAT,
    uv_index          FLOAT,
    subjective_notes  TEXT
);

CREATE TABLE daily_subjective (
    subjective_id  SERIAL PRIMARY KEY,
    user_id        INT NOT NULL REFERENCES users(user_id),
    entry_date     DATE,
    energy_level   INT,
    mood           INT,
    hrv            FLOAT,
    soreness       INT,
    sleep_quality  INT,
    recovery       INT,
    reflection     TEXT,
    UNIQUE (user_id, entry_date)
);

CREATE TABLE workout_metrics (
    metric_id             SERIAL PRIMARY KEY,
    workout_id            INT NOT NULL REFERENCES workouts(workout_id),
    metric_timestamp      TIMESTAMP,
    heart_rate            INT,
    pace                  FLOAT,
    cadence               FLOAT,
    vertical_oscillation  FLOAT,
    vertical_ratio        FLOAT,
    ground_contact_time   FLOAT,
    power                 FLOAT
);

CREATE TABLE nutrition_log (
    nutrition_id    SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(user_id),
    ingestion_time  TIMESTAMP,
    food_type       VARCHAR(200),
    total_calories  INT,
    macros_carbs    FLOAT,
    macros_protein  FLOAT,
    macros_fat      FLOAT,
    supplements     VARCHAR(200)
);

CREATE TABLE injuries (
    injury_id   SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(user_id),
    start_date  DATE,
    end_date    DATE,
    injury_type VARCHAR(100),
    severity    VARCHAR(50),
    notes       TEXT
);

-- Morning readiness check-in (informs today's decision)
CREATE TABLE daily_readiness (
    readiness_id      SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(user_id),
    entry_date        DATE NOT NULL,
    overall_feel      INT CHECK (overall_feel BETWEEN 1 AND 10),
    legs_feel         INT CHECK (legs_feel BETWEEN 1 AND 10),
    upper_body_feel   INT CHECK (upper_body_feel BETWEEN 1 AND 10),
    joint_feel        INT CHECK (joint_feel BETWEEN 1 AND 10),
    injury_note       TEXT,
    time_available    VARCHAR(10) CHECK (time_available IN ('short', 'medium', 'long')),
    going_out_tonight BOOLEAN,
    UNIQUE (user_id, entry_date)
);

-- Post-workout reflection (informs tomorrow's decision + trains the model)
CREATE TABLE workout_reflection (
    reflection_id   SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(user_id),
    entry_date      DATE NOT NULL,
    session_rpe     INT CHECK (session_rpe BETWEEN 1 AND 10),
    session_quality INT CHECK (session_quality BETWEEN 1 AND 10),
    notes           TEXT,
    UNIQUE (user_id, entry_date)
);

-- ---------------------------------------------------------------------------
-- Exercise knowledge base
-- ---------------------------------------------------------------------------

CREATE TABLE exercises (
    exercise_id       SERIAL PRIMARY KEY,
    name              VARCHAR(200) NOT NULL UNIQUE,
    source            VARCHAR(20)  DEFAULT 'wger' CHECK (source IN ('wger', 'custom')),

    -- Movement taxonomy
    movement_pattern  VARCHAR(20) CHECK (movement_pattern IN (
                          'push_h', 'push_v', 'pull_h', 'pull_v',
                          'hinge', 'squat', 'carry', 'rotation',
                          'plyo', 'isolation', 'stability')),
    quality_focus     VARCHAR(20) CHECK (quality_focus IN (
                          'power', 'strength', 'hypertrophy',
                          'endurance', 'stability')),

    -- Muscles (controlled vocabulary as arrays)
    primary_muscles   TEXT[],
    secondary_muscles TEXT[],

    -- Equipment
    equipment         TEXT[],

    -- Difficulty
    skill_level       VARCHAR(15) CHECK (skill_level IN ('beginner', 'intermediate', 'advanced')),
    bilateral         BOOLEAN DEFAULT TRUE,
    contraction_type  VARCHAR(15) CHECK (contraction_type IN ('explosive', 'controlled', 'isometric', 'mixed')),

    -- Fatigue profile
    systemic_fatigue  INT CHECK (systemic_fatigue BETWEEN 1 AND 5),
    cns_load          INT CHECK (cns_load BETWEEN 1 AND 5),

    -- Joint stress per joint (1-5, stored as JSONB)
    -- e.g. {"shoulder": 2, "elbow": 1, "wrist": 1, "knee": 1, "hip": 2, "lower_back": 3, "ankle": 1}
    joint_stress      JSONB DEFAULT '{}',

    -- Sport carryover (1-5 per sport)
    -- e.g. {"xc_mtb": 3, "trail_run": 4, "climbing": 2, "ski": 3, "snowboard": 2}
    sport_carryover   JSONB DEFAULT '{}',

    -- Goal carryover (1-5 per goal)
    -- e.g. {"power": 2, "strength": 4, "hypertrophy": 3, "endurance": 1, "stability": 2}
    goal_carryover    JSONB DEFAULT '{}',

    notes             TEXT
);

-- Progression chains (branching tree — one exercise can progress multiple ways)
CREATE TABLE exercise_progressions (
    progression_id    SERIAL PRIMARY KEY,
    from_exercise_id  INT NOT NULL REFERENCES exercises(exercise_id),
    to_exercise_id    INT NOT NULL REFERENCES exercises(exercise_id),
    progression_type  VARCHAR(10) CHECK (progression_type IN ('harder', 'easier', 'lateral')),
    goal_branch       VARCHAR(20) CHECK (goal_branch IN (
                          'power', 'strength', 'hypertrophy',
                          'endurance', 'stability')),
    notes             TEXT,
    UNIQUE (from_exercise_id, to_exercise_id, goal_branch)
);

-- ---------------------------------------------------------------------------
-- Strength training (manually logged from Apple Notes)
CREATE TABLE strength_sessions (
    session_id   SERIAL PRIMARY KEY,
    user_id      INT NOT NULL REFERENCES users(user_id),
    session_date DATE NOT NULL,
    session_type VARCHAR(10) CHECK (session_type IN ('upper', 'lower')),
    raw_notes    TEXT,
    UNIQUE (user_id, session_date)
);

CREATE TABLE strength_exercises (
    exercise_id    SERIAL PRIMARY KEY,
    session_id     INT NOT NULL REFERENCES strength_sessions(session_id),
    exercise_order INT NOT NULL,
    name           VARCHAR(200) NOT NULL,
    notes          TEXT
);

CREATE TABLE strength_sets (
    set_id               SERIAL PRIMARY KEY,
    exercise_id          INT NOT NULL REFERENCES strength_exercises(exercise_id),
    set_number           INT NOT NULL,
    reps                 INT,
    reps_min             INT,
    reps_max             INT,
    duration_seconds     INT,
    weight_kg            FLOAT,
    is_bodyweight        BOOLEAN DEFAULT FALSE,
    band_color           VARCHAR(50),
    per_hand             BOOLEAN DEFAULT FALSE,
    per_side             BOOLEAN DEFAULT FALSE,
    plus_bar             BOOLEAN DEFAULT FALSE,
    weight_includes_bar  BOOLEAN DEFAULT FALSE,
    total_weight_kg      FLOAT
);
