"""CLI smoke tests for Samsung Health tool."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from shealth.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text("""
google_drive:
  folder_id: "test_folder"
  account: "test@example.com"
goals:
  daily_steps: 10000
  sleep_hours: 8
timezone: "UTC"
""")
        yield config_path


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Samsung Health Connect CLI" in result.output
        assert "sync" in result.output
        assert "today" in result.output
        assert "sleep" in result.output

    def test_subcommand_help(self, runner):
        """Test help for subcommands."""
        for cmd in ["sync", "status", "sleep", "steps", "heart", "workout", "today", "spo2", "report"]:
            result = runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"Help failed for {cmd}: {result.output}"


class TestCLIWithoutData:
    """Test CLI behavior when no data is available."""

    def test_status_no_db(self, runner):
        """Test status command when database doesn't exist."""
        with patch("shealth.cli.get_db") as mock_get_db:
            mock_get_db.side_effect = FileNotFoundError("Database not found")
            result = runner.invoke(main, ["status"])
            assert "Database not found" in result.output or "sync" in result.output.lower()

    def test_today_no_db(self, runner):
        """Test today command when database doesn't exist."""
        with patch("shealth.cli.get_db") as mock_get_db:
            mock_get_db.side_effect = FileNotFoundError("Database not found")
            result = runner.invoke(main, ["today"])
            assert "not found" in result.output.lower() or "sync" in result.output.lower()


class TestCLIValidation:
    """Test input validation."""

    def test_days_validation_negative(self, runner):
        """Test that negative days are rejected."""
        result = runner.invoke(main, ["sleep", "--days", "-1"])
        assert result.exit_code != 0 or "at least" in result.output.lower()

    def test_days_validation_too_large(self, runner):
        """Test that extremely large days values are rejected."""
        result = runner.invoke(main, ["sleep", "--days", "9999"])
        assert result.exit_code != 0 or "exceed" in result.output.lower()

    def test_days_validation_valid(self, runner):
        """Test that valid days values are accepted."""
        with patch("shealth.cli.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_sleep_sessions.return_value = MagicMock(empty=True)
            mock_get_db.return_value = mock_db
            
            result = runner.invoke(main, ["sleep", "--days", "30"])
            # Should not fail on validation
            assert "at least" not in result.output.lower()
            assert "exceed" not in result.output.lower()


class TestJSONOutput:
    """Test JSON output mode."""

    def test_json_flag_status(self, runner):
        """Test --json flag on status command."""
        with patch("shealth.cli.get_db") as mock_get_db, \
             patch("shealth.cli.get_last_sync_time") as mock_sync_time, \
             patch("shealth.cli.get_config") as mock_config:
            
            from datetime import datetime
            
            mock_db = MagicMock()
            mock_db.get_table_counts.return_value = {"sleep_session_record_table": 10}
            mock_db.get_date_range.return_value = (datetime(2025, 1, 1), datetime(2025, 1, 30))
            mock_get_db.return_value = mock_db
            mock_sync_time.return_value = datetime.now()
            mock_config.return_value = MagicMock()
            
            result = runner.invoke(main, ["--json", "status"])
            
            # Should contain JSON structure
            assert "{" in result.output or "last_sync" in result.output

    def test_json_flag_today(self, runner):
        """Test --json flag on today command."""
        with patch("shealth.cli.get_db") as mock_get_db, \
             patch("shealth.cli.get_config") as mock_config:
            
            mock_db = MagicMock()
            mock_db.get_today_summary.return_value = {
                "date": "2025-01-30",
                "steps": 5000,
                "sleep_hours": 7.5,
                "avg_hr": 72,
                "workouts": 1,
                "spo2": 97,
            }
            mock_get_db.return_value = mock_db
            mock_config.return_value = MagicMock()
            mock_config.return_value.get.return_value = 10000
            
            result = runner.invoke(main, ["--json", "today"])
            
            # Should be valid JSON with expected fields
            assert "steps" in result.output
            assert "5000" in result.output


class TestSyncCommand:
    """Test sync command behavior."""

    def test_sync_no_config(self, runner):
        """Test sync when Google Drive is not configured."""
        with patch("shealth.cli.sync_data") as mock_sync:
            mock_sync.return_value = False
            result = runner.invoke(main, ["sync"])
            # Should indicate sync finished or failed
            assert result.exit_code == 0

    def test_sync_watch_not_implemented(self, runner):
        """Test that --watch flag shows not implemented message."""
        result = runner.invoke(main, ["sync", "--watch"])
        assert "not" in result.output.lower() and "implement" in result.output.lower()
