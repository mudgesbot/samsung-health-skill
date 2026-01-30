"""Configuration management for Samsung Health CLI."""

import os
from pathlib import Path
from typing import Any

import yaml

# Default paths
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "samsung-health"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "samsung-health"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "health.db"
DEFAULT_CACHE_DIR = DEFAULT_DATA_DIR / "cache"

# Default configuration
DEFAULT_CONFIG = {
    "google_drive": {
        "folder_id": "YOUR_FOLDER_ID",
        "account": "your.email@gmail.com",
        "file_name": "Health Connect.zip",
    },
    "goals": {
        "daily_steps": 10000,
        "sleep_hours": 8,
    },
    "timezone": "Europe/Copenhagen",
}

# Sleep stage mapping
SLEEP_STAGES = {
    1: "Light",
    4: "Deep",
    5: "Awake",
    6: "REM",
}

# Exercise type mapping (Health Connect standard types)
EXERCISE_TYPES = {
    0: "Unknown",
    2: "Badminton",
    4: "Weightlifting",
    8: "Boxing",
    10: "Cricket",
    12: "Dancing",
    14: "Elliptical",
    16: "Fencing",
    18: "Football (American)",
    20: "Frisbee",
    21: "Cycling",
    22: "Golf",
    24: "Gymnastics",
    26: "Handball",
    28: "HIIT",
    30: "Hiking",
    32: "Hockey",
    33: "Running",
    34: "Skating (Ice)",
    36: "Martial Arts",
    38: "Pilates",
    40: "Racquetball",
    42: "Rock Climbing",
    44: "Rowing",
    46: "Sailing",
    48: "Skating",
    50: "Skiing",
    52: "Snowboarding",
    53: "Walking",
    54: "Soccer",
    56: "Squash",
    58: "Swimming",
    60: "Table Tennis",
    61: "Hiking",
    62: "Tennis",
    64: "Volleyball",
    66: "Yoga",
    68: "Stretching",
}


class Config:
    """Configuration manager for Samsung Health CLI."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration.

        Args:
            config_path: Optional path to config file. Defaults to ~/.config/samsung-health/config.yaml
        """
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

        # Merge with defaults
        self._config = self._merge_defaults(DEFAULT_CONFIG, self._config)

    def _merge_defaults(self, defaults: dict, config: dict) -> dict:
        """Recursively merge config with defaults."""
        result = defaults.copy()
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_defaults(result[key], value)
            else:
                result[key] = value
        return result

    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., "google_drive.folder_id")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        parts = key.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-separated key.

        Args:
            key: Dot-separated key
            value: Value to set
        """
        parts = key.split(".")
        config = self._config
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return DEFAULT_DATA_DIR

    @property
    def db_path(self) -> Path:
        """Get database path."""
        return DEFAULT_DB_PATH

    @property
    def cache_dir(self) -> Path:
        """Get cache directory path."""
        return DEFAULT_CACHE_DIR

    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
