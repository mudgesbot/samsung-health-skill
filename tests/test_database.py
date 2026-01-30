"""Tests for database module."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from shealth.database import HealthDatabase


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        conn = sqlite3.connect(db_path)

        # Create tables
        conn.execute("""
            CREATE TABLE sleep_session_record_table (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time INTEGER,
                end_time INTEGER,
                title TEXT,
                notes TEXT,
                uuid BLOB NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE sleep_stages_table (
                parent_key INTEGER,
                stage_type INTEGER,
                stage_start_time INTEGER,
                stage_end_time INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE steps_record_table (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time INTEGER,
                end_time INTEGER,
                count INTEGER,
                local_date_time_start_time INTEGER,
                uuid BLOB NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE heart_rate_record_table (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time INTEGER,
                end_time INTEGER,
                uuid BLOB NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE heart_rate_record_series_table (
                parent_key INTEGER,
                beats_per_minute INTEGER,
                epoch_millis INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE exercise_session_record_table (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time INTEGER,
                end_time INTEGER,
                exercise_type INTEGER,
                title TEXT,
                notes TEXT,
                uuid BLOB NOT NULL UNIQUE
            )
        """)

        # Insert sample data
        now = datetime.now()
        now_ms = int(now.timestamp() * 1000)
        yesterday_ms = int((now - timedelta(days=1)).timestamp() * 1000)

        # Sleep session
        conn.execute("""
            INSERT INTO sleep_session_record_table (start_time, end_time, title, uuid)
            VALUES (?, ?, 'Sleep', x'0001')
        """, (yesterday_ms, yesterday_ms + 8 * 3600 * 1000))

        # Sleep stages
        conn.execute("""
            INSERT INTO sleep_stages_table (parent_key, stage_type, stage_start_time, stage_end_time)
            VALUES (1, 1, ?, ?)
        """, (yesterday_ms, yesterday_ms + 2 * 3600 * 1000))

        conn.execute("""
            INSERT INTO sleep_stages_table (parent_key, stage_type, stage_start_time, stage_end_time)
            VALUES (1, 4, ?, ?)
        """, (yesterday_ms + 2 * 3600 * 1000, yesterday_ms + 4 * 3600 * 1000))

        # Steps
        conn.execute("""
            INSERT INTO steps_record_table (start_time, end_time, count, local_date_time_start_time, uuid)
            VALUES (?, ?, 5000, ?, x'0002')
        """, (yesterday_ms, now_ms, yesterday_ms))

        conn.execute("""
            INSERT INTO steps_record_table (start_time, end_time, count, local_date_time_start_time, uuid)
            VALUES (?, ?, 3000, ?, x'0003')
        """, (yesterday_ms, now_ms, yesterday_ms))

        # Heart rate
        conn.execute("""
            INSERT INTO heart_rate_record_table (start_time, end_time, uuid)
            VALUES (?, ?, x'0004')
        """, (yesterday_ms, now_ms))

        conn.execute("""
            INSERT INTO heart_rate_record_series_table (parent_key, beats_per_minute, epoch_millis)
            VALUES (1, 70, ?)
        """, (yesterday_ms,))

        conn.execute("""
            INSERT INTO heart_rate_record_series_table (parent_key, beats_per_minute, epoch_millis)
            VALUES (1, 75, ?)
        """, (now_ms,))

        # Workout
        conn.execute("""
            INSERT INTO exercise_session_record_table (start_time, end_time, exercise_type, title, uuid)
            VALUES (?, ?, 53, 'Morning Walk', x'0005')
        """, (yesterday_ms, yesterday_ms + 30 * 60 * 1000))

        conn.commit()
        conn.close()

        yield HealthDatabase(db_path)


class TestHealthDatabase:
    """Test database access layer."""

    def test_get_table_counts(self, test_db):
        """Test getting record counts."""
        counts = test_db.get_table_counts()
        assert counts["sleep_session_record_table"] == 1
        assert counts["steps_record_table"] == 2
        assert counts["heart_rate_record_table"] == 1
        assert counts["exercise_session_record_table"] == 1

    def test_get_sleep_sessions(self, test_db):
        """Test getting sleep sessions."""
        sessions = test_db.get_sleep_sessions(days=7)
        assert len(sessions) == 1
        assert sessions.iloc[0]["duration_minutes"] == pytest.approx(8 * 60, rel=0.1)

    def test_get_sleep_stage_summary(self, test_db):
        """Test getting sleep stage summary."""
        summary = test_db.get_sleep_stage_summary(1)
        assert "Light" in summary
        assert "Deep" in summary
        assert summary["Light"] == pytest.approx(120, rel=0.1)  # 2 hours

    def test_get_daily_steps(self, test_db):
        """Test getting daily step counts."""
        steps = test_db.get_daily_steps(days=7)
        assert len(steps) >= 1
        assert steps["steps"].sum() == 8000

    def test_get_heart_rate_stats(self, test_db):
        """Test getting heart rate statistics."""
        stats = test_db.get_heart_rate_stats(days=7)
        assert stats["avg_hr"] == pytest.approx(72.5, rel=0.1)
        assert stats["min_hr"] == 70
        assert stats["max_hr"] == 75
        assert stats["sample_count"] == 2

    def test_get_workouts(self, test_db):
        """Test getting workout sessions."""
        workouts = test_db.get_workouts(days=7)
        assert len(workouts) == 1
        assert workouts.iloc[0]["exercise_type"] == 53
        assert workouts.iloc[0]["exercise_name"] == "Walking"

    def test_get_workout_summary(self, test_db):
        """Test getting workout summary."""
        summary = test_db.get_workout_summary(days=7)
        assert summary["total_workouts"] == 1
        assert "Walking" in summary["by_type"]
