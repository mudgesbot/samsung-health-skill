"""Samsung Health Connect CLI tool."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("samsung-health-skill")
except PackageNotFoundError:
    __version__ = "0.1.0"  # Fallback for dev installs
