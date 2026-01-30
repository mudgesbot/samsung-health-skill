"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest

from shealth.config import Config, DEFAULT_CONFIG, SLEEP_STAGES, EXERCISE_TYPES


class TestConfig:
    """Test configuration management."""

    def test_default_values(self):
        """Test that default configuration is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config(config_path)

            assert config.get("google_drive.folder_id") == DEFAULT_CONFIG["google_drive"]["folder_id"]
            assert config.get("goals.daily_steps") == 10000
            assert config.get("goals.sleep_hours") == 8

    def test_get_nested_key(self):
        """Test getting nested configuration keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config(config_path)

            assert config.get("google_drive.account") == "your.email@gmail.com"
            assert config.get("nonexistent.key", "default") == "default"

    def test_set_and_save(self):
        """Test setting and saving configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config(config_path)

            config.set("goals.daily_steps", 15000)
            config.save()

            # Reload and verify
            config2 = Config(config_path)
            assert config2.get("goals.daily_steps") == 15000


class TestSleepStages:
    """Test sleep stage mappings."""

    def test_all_stages_defined(self):
        """Test that common sleep stages are defined."""
        assert SLEEP_STAGES[1] == "Light"
        assert SLEEP_STAGES[4] == "Deep"
        assert SLEEP_STAGES[5] == "Awake"
        assert SLEEP_STAGES[6] == "REM"


class TestExerciseTypes:
    """Test exercise type mappings."""

    def test_common_types_defined(self):
        """Test that common exercise types are defined."""
        assert EXERCISE_TYPES[53] == "Walking"
        assert EXERCISE_TYPES[33] == "Running"
        assert EXERCISE_TYPES[21] == "Cycling"
        assert EXERCISE_TYPES[58] == "Swimming"
