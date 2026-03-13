-- QuantifiedStrides PostgreSQL Schema
-- Run this once against a fresh database: psql -d quantifiedstrides -f schema.sql

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    name          VARCHAR(100),
    date_of_birth DATE
);

-- Default single athlete
INSERT INTO users (name) VALUES ('Athlete');

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
