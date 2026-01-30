"""Database access for Samsung Health Connect data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from .config import EXERCISE_TYPES, SLEEP_STAGES, get_config


class HealthDatabase:
    """Access layer for Health Connect SQLite database."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database. Defaults to configured path.
        """
        self.db_path = db_path or get_config().db_path

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. Run 'shealth sync' first."
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # Allowed table names (whitelist for SQL safety)
    KNOWN_TABLES = frozenset([
        "sleep_session_record_table",
        "sleep_stages_table",
        "steps_record_table",
        "heart_rate_record_table",
        "heart_rate_record_series_table",
        "heart_rate_variability_rmssd_record_table",
        "resting_heart_rate_record_table",
        "exercise_session_record_table",
        "weight_record_table",
        "oxygen_saturation_record_table",
    ])

    def get_table_counts(self) -> dict[str, int]:
        """Get record counts for all main tables."""
        counts = {}
        with self.connection() as conn:
            for table in self.KNOWN_TABLES:
                try:
                    # Table name is from KNOWN_TABLES whitelist, safe to interpolate
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    counts[table] = 0
        return counts

    def get_date_range(self) -> tuple[datetime | None, datetime | None]:
        """Get the date range of available data."""
        with self.connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    MIN(start_time) as min_time,
                    MAX(start_time) as max_time
                FROM (
                    SELECT start_time FROM sleep_session_record_table
                    UNION ALL
                    SELECT start_time FROM steps_record_table
                    UNION ALL
                    SELECT start_time FROM heart_rate_record_table
                    UNION ALL
                    SELECT start_time FROM exercise_session_record_table
                )
            """)
            row = cursor.fetchone()
            if row and row["min_time"] and row["max_time"]:
                return (
                    datetime.fromtimestamp(row["min_time"] / 1000),
                    datetime.fromtimestamp(row["max_time"] / 1000),
                )
        return None, None

    def get_sleep_sessions(
        self, days: int = 7, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """Get sleep sessions for the specified period.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            DataFrame with sleep sessions
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    row_id,
                    datetime(start_time/1000, 'unixepoch', 'localtime') as start_time,
                    datetime(end_time/1000, 'unixepoch', 'localtime') as end_time,
                    (end_time - start_time) / 60000.0 as duration_minutes,
                    title,
                    notes
                FROM sleep_session_record_table
                WHERE start_time >= ? AND start_time <= ?
                ORDER BY start_time DESC
            """
            df = pd.read_sql_query(query, conn, params=(start_ms, end_ms))
        return df

    def get_sleep_stages(self, session_id: int) -> pd.DataFrame:
        """Get sleep stages for a specific session.

        Args:
            session_id: Sleep session row_id

        Returns:
            DataFrame with sleep stages
        """
        with self.connection() as conn:
            query = """
                SELECT 
                    stage_type,
                    datetime(stage_start_time/1000, 'unixepoch', 'localtime') as start_time,
                    datetime(stage_end_time/1000, 'unixepoch', 'localtime') as end_time,
                    (stage_end_time - stage_start_time) / 60000.0 as duration_minutes
                FROM sleep_stages_table
                WHERE parent_key = ?
                ORDER BY stage_start_time
            """
            df = pd.read_sql_query(query, conn, params=(session_id,))

        if not df.empty:
            df["stage_name"] = df["stage_type"].map(SLEEP_STAGES)
        return df

    def get_sleep_stage_summary(self, session_id: int) -> dict[str, float]:
        """Get summary of sleep stages for a session.

        Args:
            session_id: Sleep session row_id

        Returns:
            Dict with stage names and total minutes
        """
        stages = self.get_sleep_stages(session_id)
        if stages.empty:
            return {}

        summary = {}
        for stage_type, group in stages.groupby("stage_type"):
            stage_name = SLEEP_STAGES.get(stage_type, f"Unknown ({stage_type})")
            summary[stage_name] = group["duration_minutes"].sum()
        return summary

    def get_daily_steps(
        self, days: int = 7, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """Get daily step counts.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            DataFrame with daily step totals
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    date(local_date_time_start_time/1000, 'unixepoch') as date,
                    SUM(count) as steps
                FROM steps_record_table
                WHERE local_date_time_start_time >= ? AND local_date_time_start_time <= ?
                GROUP BY date
                ORDER BY date DESC
            """
            df = pd.read_sql_query(query, conn, params=(start_ms, end_ms))
        return df

    def get_heart_rate_stats(
        self, days: int = 7, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """Get heart rate statistics for the period.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            Dict with HR statistics
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    AVG(s.beats_per_minute) as avg_hr,
                    MIN(s.beats_per_minute) as min_hr,
                    MAX(s.beats_per_minute) as max_hr,
                    COUNT(*) as sample_count
                FROM heart_rate_record_series_table s
                JOIN heart_rate_record_table h ON s.parent_key = h.row_id
                WHERE h.start_time >= ? AND h.start_time <= ?
            """
            cursor = conn.execute(query, (start_ms, end_ms))
            row = cursor.fetchone()

            if row and row["sample_count"] > 0:
                return {
                    "avg_hr": round(row["avg_hr"], 1),
                    "min_hr": row["min_hr"],
                    "max_hr": row["max_hr"],
                    "sample_count": row["sample_count"],
                }
        return {"avg_hr": 0, "min_hr": 0, "max_hr": 0, "sample_count": 0}

    def get_daily_heart_rate(
        self, days: int = 7, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """Get daily heart rate statistics.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            DataFrame with daily HR stats
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    date(h.start_time/1000, 'unixepoch', 'localtime') as date,
                    ROUND(AVG(s.beats_per_minute), 1) as avg_hr,
                    MIN(s.beats_per_minute) as min_hr,
                    MAX(s.beats_per_minute) as max_hr,
                    COUNT(*) as samples
                FROM heart_rate_record_series_table s
                JOIN heart_rate_record_table h ON s.parent_key = h.row_id
                WHERE h.start_time >= ? AND h.start_time <= ?
                GROUP BY date
                ORDER BY date DESC
            """
            df = pd.read_sql_query(query, conn, params=(start_ms, end_ms))
        return df

    def get_workouts(
        self, days: int = 30, end_date: datetime | None = None, exercise_type: int | None = None
    ) -> pd.DataFrame:
        """Get workout sessions.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)
            exercise_type: Filter by exercise type code

        Returns:
            DataFrame with workout sessions
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    row_id,
                    datetime(start_time/1000, 'unixepoch', 'localtime') as start_time,
                    datetime(end_time/1000, 'unixepoch', 'localtime') as end_time,
                    (end_time - start_time) / 60000.0 as duration_minutes,
                    exercise_type,
                    title,
                    notes
                FROM exercise_session_record_table
                WHERE start_time >= ? AND start_time <= ?
            """
            params: list[Any] = [start_ms, end_ms]

            if exercise_type is not None:
                query += " AND exercise_type = ?"
                params.append(exercise_type)

            query += " ORDER BY start_time DESC"
            df = pd.read_sql_query(query, conn, params=params)

        if not df.empty:
            df["exercise_name"] = df["exercise_type"].map(
                lambda x: EXERCISE_TYPES.get(x, f"Unknown ({x})")
            )
        return df

    def get_workout_summary(
        self, days: int = 30, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """Get workout summary statistics.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            Dict with workout statistics
        """
        workouts = self.get_workouts(days, end_date)
        if workouts.empty:
            return {
                "total_workouts": 0,
                "total_minutes": 0,
                "by_type": {},
            }

        by_type = {}
        for exercise_type, group in workouts.groupby("exercise_type"):
            exercise_name = EXERCISE_TYPES.get(exercise_type, f"Unknown ({exercise_type})")
            by_type[exercise_name] = {
                "count": len(group),
                "total_minutes": round(group["duration_minutes"].sum(), 1),
                "avg_minutes": round(group["duration_minutes"].mean(), 1),
            }

        return {
            "total_workouts": len(workouts),
            "total_minutes": round(workouts["duration_minutes"].sum(), 1),
            "by_type": by_type,
        }


    def get_spo2_readings(
        self, days: int = 7, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """Get SpO2 (oxygen saturation) readings.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            DataFrame with SpO2 readings
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        with self.connection() as conn:
            query = """
                SELECT 
                    datetime(time/1000, 'unixepoch', 'localtime') as time,
                    date(time/1000, 'unixepoch', 'localtime') as date,
                    percentage as spo2
                FROM oxygen_saturation_record_table
                WHERE time >= ? AND time <= ?
                ORDER BY time DESC
            """
            df = pd.read_sql_query(query, conn, params=(start_ms, end_ms))
        return df

    def get_spo2_stats(
        self, days: int = 7, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """Get SpO2 statistics for the period.

        Args:
            days: Number of days to look back
            end_date: End date for the query (defaults to now)

        Returns:
            Dict with SpO2 statistics
        """
        readings = self.get_spo2_readings(days, end_date)
        if readings.empty:
            return {"avg_spo2": 0, "min_spo2": 0, "max_spo2": 0, "count": 0}

        return {
            "avg_spo2": round(readings["spo2"].mean(), 1),
            "min_spo2": int(readings["spo2"].min()),
            "max_spo2": int(readings["spo2"].max()),
            "count": len(readings),
        }

    def get_today_summary(self) -> dict[str, Any]:
        """Get quick summary for today.

        Returns:
            Dict with today's health metrics
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        today_ms = int(today.timestamp() * 1000)
        tomorrow_ms = int(tomorrow.timestamp() * 1000)

        summary = {
            "date": today.strftime("%Y-%m-%d"),
            "steps": 0,
            "sleep_hours": 0,
            "avg_hr": 0,
            "workouts": 0,
            "spo2": None,
        }

        with self.connection() as conn:
            # Steps today
            cursor = conn.execute("""
                SELECT SUM(count) as steps FROM steps_record_table
                WHERE local_date_time_start_time >= ? AND local_date_time_start_time < ?
            """, (today_ms, tomorrow_ms))
            row = cursor.fetchone()
            if row and row["steps"]:
                summary["steps"] = int(row["steps"])

            # Last night's sleep (ended today or yesterday evening start)
            yesterday = today - timedelta(days=1)
            yesterday_ms = int(yesterday.timestamp() * 1000)
            cursor = conn.execute("""
                SELECT (end_time - start_time) / 3600000.0 as hours
                FROM sleep_session_record_table
                WHERE end_time >= ? AND end_time < ?
                ORDER BY end_time DESC LIMIT 1
            """, (today_ms, tomorrow_ms))
            row = cursor.fetchone()
            if row and row["hours"]:
                summary["sleep_hours"] = round(row["hours"], 1)

            # Heart rate today
            cursor = conn.execute("""
                SELECT AVG(s.beats_per_minute) as avg_hr
                FROM heart_rate_record_series_table s
                JOIN heart_rate_record_table h ON s.parent_key = h.row_id
                WHERE h.start_time >= ? AND h.start_time < ?
            """, (today_ms, tomorrow_ms))
            row = cursor.fetchone()
            if row and row["avg_hr"]:
                summary["avg_hr"] = round(row["avg_hr"], 1)

            # Workouts today
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM exercise_session_record_table
                WHERE start_time >= ? AND start_time < ?
            """, (today_ms, tomorrow_ms))
            row = cursor.fetchone()
            if row:
                summary["workouts"] = row["count"]

            # Latest SpO2
            cursor = conn.execute("""
                SELECT percentage as spo2 FROM oxygen_saturation_record_table
                WHERE time >= ? AND time < ?
                ORDER BY time DESC LIMIT 1
            """, (today_ms, tomorrow_ms))
            row = cursor.fetchone()
            if row and row["spo2"]:
                summary["spo2"] = int(row["spo2"])

        return summary


# Global database instance
_db: HealthDatabase | None = None


def get_db() -> HealthDatabase:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = HealthDatabase()
    return _db
