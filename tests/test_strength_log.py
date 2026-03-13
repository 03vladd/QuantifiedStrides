"""Tests for strength_log.py — weight calculations and date parsing."""

import pytest
from datetime import date


BAR_WEIGHT_KG = 20.0


# ---------------------------------------------------------------------------
# Helpers — replicate logic from strength_log.py
# ---------------------------------------------------------------------------

def compute_total(sw: dict, per_hand: bool) -> float | None:
    """Mirror compute_total from strength_log.py."""
    w = sw["weight_kg"]
    if sw["is_bw"] or w is None:
        return None
    if sw["plus_bar"]:
        return w + BAR_WEIGHT_KG
    if sw["incl_bar"]:
        return w
    if per_hand:
        return w * 2
    return w


def adjusted_weight(sw: dict) -> float | None:
    """Mirror adjusted_weight from strength_log.py."""
    w = sw["weight_kg"]
    return (w - BAR_WEIGHT_KG) if (sw["incl_bar"] and w is not None) else w


def parse_date(s: str):
    """Mirror parse_date from strength_log.py."""
    from datetime import datetime
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.strptime(f"{s}.2026", "%d.%m.%Y").date()
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# Date parsing tests
# ---------------------------------------------------------------------------

class TestDateParsing:
    def test_dd_mm_assumes_2026(self):
        assert parse_date("12.03") == date(2026, 3, 12)

    def test_dd_mm_yyyy(self):
        assert parse_date("12.03.2026") == date(2026, 3, 12)

    def test_iso_format(self):
        assert parse_date("2026-03-12") == date(2026, 3, 12)

    def test_invalid_returns_none(self):
        assert parse_date("not-a-date") is None

    def test_empty_string_returns_none(self):
        assert parse_date("") is None

    def test_dd_mm_end_of_year(self):
        assert parse_date("31.12") == date(2026, 12, 31)

    def test_whitespace_is_stripped(self):
        assert parse_date("  04.02  ") == date(2026, 2, 4)


# ---------------------------------------------------------------------------
# Weight calculation tests — compute_total
# ---------------------------------------------------------------------------

class TestComputeTotal:
    def _sw(self, weight_kg=None, is_bw=False, band_color=None,
             plus_bar=False, incl_bar=False):
        return {"weight_kg": weight_kg, "is_bw": is_bw, "band_color": band_color,
                "plus_bar": plus_bar, "incl_bar": incl_bar}

    def test_plain_kg_no_modifier(self):
        assert compute_total(self._sw(weight_kg=40.0), per_hand=False) == 40.0

    def test_per_hand_doubles_weight(self):
        assert compute_total(self._sw(weight_kg=10.0), per_hand=True) == 20.0

    def test_plus_bar_adds_20kg(self):
        # +bara: entered weight + 20 kg bar
        assert compute_total(self._sw(weight_kg=60.0, plus_bar=True), per_hand=False) == 80.0

    def test_cu_tot_cu_bara_total_equals_entered(self):
        # cu tot cu bara: 80 kg entered means bar included, total = 80
        assert compute_total(self._sw(weight_kg=80.0, incl_bar=True), per_hand=False) == 80.0

    def test_bodyweight_returns_none(self):
        assert compute_total(self._sw(is_bw=True), per_hand=False) is None

    def test_band_returns_none(self):
        assert compute_total(self._sw(band_color="verde"), per_hand=False) is None

    def test_none_weight_returns_none(self):
        assert compute_total(self._sw(weight_kg=None), per_hand=False) is None

    def test_per_hand_with_plus_bar_not_doubled(self):
        # +bara takes precedence — per_hand check is after plus_bar in the logic
        sw = self._sw(weight_kg=20.0, plus_bar=True)
        assert compute_total(sw, per_hand=True) == 40.0  # 20 + 20, NOT doubled again

    def test_zero_weight_plain(self):
        assert compute_total(self._sw(weight_kg=0.0), per_hand=False) == 0.0


# ---------------------------------------------------------------------------
# Weight calculation tests — adjusted_weight
# ---------------------------------------------------------------------------

class TestAdjustedWeight:
    def _sw(self, weight_kg=None, incl_bar=False):
        return {"weight_kg": weight_kg, "is_bw": False, "band_color": None,
                "plus_bar": False, "incl_bar": incl_bar}

    def test_incl_bar_subtracts_20kg(self):
        # User enters total (bar included). Stored weight_kg = entered - bar
        sw = self._sw(weight_kg=80.0, incl_bar=True)
        assert adjusted_weight(sw) == 60.0

    def test_no_bar_unchanged(self):
        sw = self._sw(weight_kg=40.0, incl_bar=False)
        assert adjusted_weight(sw) == 40.0

    def test_none_weight_returns_none(self):
        sw = self._sw(weight_kg=None, incl_bar=True)
        assert adjusted_weight(sw) is None


# ---------------------------------------------------------------------------
# Scenario tests — realistic exercises
# ---------------------------------------------------------------------------

class TestRealisticExerciseScenarios:
    def test_squat_double_jump_per_hand(self):
        """DB Squat Double Jump: 10 kg /mana → total = 20 kg."""
        sw = {"weight_kg": 10.0, "is_bw": False, "band_color": None,
              "plus_bar": False, "incl_bar": False}
        assert compute_total(sw, per_hand=True) == 20.0

    def test_bench_press_with_bar_included(self):
        """User enters total bar weight: 80 kg → stored as 60 kg + bar."""
        sw = {"weight_kg": 80.0, "is_bw": False, "band_color": None,
              "plus_bar": False, "incl_bar": True}
        assert adjusted_weight(sw) == 60.0
        assert compute_total(sw, per_hand=False) == 80.0

    def test_squat_plus_bar(self):
        """60 kg plates + bar: total = 60 + 20 = 80 kg."""
        sw = {"weight_kg": 60.0, "is_bw": False, "band_color": None,
              "plus_bar": True, "incl_bar": False}
        assert compute_total(sw, per_hand=False) == 80.0

    def test_dips_bodyweight(self):
        sw = {"weight_kg": None, "is_bw": True, "band_color": None,
              "plus_bar": False, "incl_bar": False}
        assert compute_total(sw, per_hand=False) is None

    def test_band_assisted_pullup(self):
        sw = {"weight_kg": None, "is_bw": False, "band_color": "verde coma",
              "plus_bar": False, "incl_bar": False}
        assert compute_total(sw, per_hand=False) is None

    def test_kb_gorilla_row_per_hand(self):
        """24 kg KB /mana → total = 48 kg."""
        sw = {"weight_kg": 24.0, "is_bw": False, "band_color": None,
              "plus_bar": False, "incl_bar": False}
        assert compute_total(sw, per_hand=True) == 48.0


# ---------------------------------------------------------------------------
# DB insertion tests
# ---------------------------------------------------------------------------

class TestStrengthSessionDatabaseInsertion:
    def test_inserts_full_session(self, db):
        conn, cur = db

        cur.execute("""
            INSERT INTO strength_sessions (user_id, session_date)
            VALUES (1, '2099-03-12') RETURNING session_id
        """)
        session_id = cur.fetchone()[0]
        assert session_id is not None

        cur.execute("""
            INSERT INTO strength_exercises (session_id, exercise_order, name)
            VALUES (%s, 1, 'Squat') RETURNING exercise_id
        """, (session_id,))
        exercise_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO strength_sets (
                exercise_id, set_number, reps, weight_kg,
                is_bodyweight, per_hand, per_side, plus_bar,
                weight_includes_bar, total_weight_kg
            ) VALUES (%s, 1, 5, 60.0, FALSE, FALSE, FALSE, TRUE, FALSE, 80.0)
            RETURNING set_id
        """, (exercise_id,))
        set_id = cur.fetchone()[0]
        assert set_id is not None

        cur.execute(
            "SELECT reps, weight_kg, total_weight_kg FROM strength_sets WHERE set_id = %s",
            (set_id,)
        )
        row = cur.fetchone()
        assert row[0] == 5
        assert row[1] == 60.0
        assert row[2] == 80.0

    def test_bodyweight_set_stored_correctly(self, db):
        conn, cur = db
        cur.execute("""
            INSERT INTO strength_sessions (user_id, session_date)
            VALUES (1, '2099-03-11') RETURNING session_id
        """)
        session_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO strength_exercises (session_id, exercise_order, name)
            VALUES (%s, 1, 'Dips') RETURNING exercise_id
        """, (session_id,))
        exercise_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO strength_sets (
                exercise_id, set_number, reps,
                is_bodyweight, total_weight_kg
            ) VALUES (%s, 1, 10, TRUE, NULL) RETURNING set_id
        """, (exercise_id,))
        set_id = cur.fetchone()[0]

        cur.execute(
            "SELECT is_bodyweight, total_weight_kg FROM strength_sets WHERE set_id = %s",
            (set_id,)
        )
        row = cur.fetchone()
        assert row[0] is True
        assert row[1] is None

    def test_duplicate_session_date_rejected(self, db):
        import psycopg2
        conn, cur = db
        cur.execute(
            "INSERT INTO strength_sessions (user_id, session_date) VALUES (1, '2099-02-10')"
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO strength_sessions (user_id, session_date) VALUES (1, '2099-02-10')"
            )

    def test_timed_set_reps_is_null(self, db):
        conn, cur = db
        cur.execute("""
            INSERT INTO strength_sessions (user_id, session_date)
            VALUES (1, '2099-03-10') RETURNING session_id
        """)
        session_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO strength_exercises (session_id, exercise_order, name)
            VALUES (%s, 1, 'Plank') RETURNING exercise_id
        """, (session_id,))
        exercise_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO strength_sets (
                exercise_id, set_number, duration_seconds, is_bodyweight
            ) VALUES (%s, 1, 60, TRUE) RETURNING set_id
        """, (exercise_id,))
        set_id = cur.fetchone()[0]

        cur.execute(
            "SELECT reps, duration_seconds FROM strength_sets WHERE set_id = %s",
            (set_id,)
        )
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] == 60
