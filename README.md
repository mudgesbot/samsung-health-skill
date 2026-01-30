# Samsung Health Connect Skill

A CLI tool for analyzing Samsung Health Connect data synced to Google Drive.

## Features

- 🔄 **Sync** - Download and extract Health Connect data from Google Drive
- 😴 **Sleep Analysis** - Duration, efficiency, stage breakdown (light/deep/REM)
- 🚶 **Step Tracking** - Daily counts, weekly/monthly totals, goal tracking
- ❤️ **Heart Rate** - Resting HR trends, average, max
- 💓 **HRV Analysis** - Heart rate variability and stress indicators
- 🏋️ **Workouts** - Exercise session history and stats
- 📊 **Reports** - Comprehensive health summaries

## Installation

```bash
# Clone the repository
git clone https://github.com/mudgesbot/samsung-health-skill.git
cd samsung-health-skill

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

## Prerequisites

- `gog` CLI installed and configured for Google Drive access
- Samsung Health Connect data exported to Google Drive folder `HealthData`

## Usage

```bash
# Sync latest data from Google Drive
shealth sync

# Check data status
shealth status

# Sleep analysis (last 7 days)
shealth sleep --days 7

# Step tracking
shealth steps --week
shealth steps --month

# Heart rate analysis
shealth heart --days 14

# Workout history
shealth workout --days 30

# Comprehensive report
shealth report --days 7
```

## Data Source

The tool expects a `Health Connect.zip` file in Google Drive folder `HealthData` containing:
- `health_connect_export.db` - SQLite database with all health records

Samsung Health Connect syncs this data daily.

## Configuration

Config stored at `~/.config/samsung-health/config.yaml`:

```yaml
google_drive:
  folder_id: "YOUR_FOLDER_ID"
  account: "your.email@gmail.com"

goals:
  daily_steps: 10000
  sleep_hours: 8

timezone: "Europe/Copenhagen"
```

## Sleep Stage Types

| Code | Stage |
|------|-------|
| 1 | Light Sleep |
| 4 | Deep Sleep |
| 5 | Awake |
| 6 | REM Sleep |

## Exercise Types

| Code | Type |
|------|------|
| 53 | Walking |
| 33 | Running |
| 61 | Hiking |
| 21 | Cycling |
| 58 | Swimming |
| 4 | Weight Training |

## License

MIT License - see [LICENSE](LICENSE)
