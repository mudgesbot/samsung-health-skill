# Samsung Health Connect CLI

A command-line tool for analyzing Samsung Health Connect data synced to Google Drive.

## Features

- 🔄 **Sync** - Download and extract Health Connect data from Google Drive
- 😴 **Sleep Analysis** - Duration, efficiency, stage breakdown (light/deep/REM/awake)
- 🚶 **Step Tracking** - Daily counts, weekly/monthly totals, goal tracking
- ❤️ **Heart Rate** - Average, min/max, daily trends
- 🫁 **SpO2** - Blood oxygen saturation tracking
- 🏋️ **Workouts** - Exercise session history and stats
- 📊 **Reports** - Comprehensive health summaries
- 📅 **Today** - Quick daily snapshot

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/samsung-health-skill.git
cd samsung-health-skill

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# For development
pip install -e ".[dev]"
```

## Prerequisites

1. **Samsung Health Connect** app configured to export data to Google Drive
2. **gog CLI** installed and authenticated with your Google account
   - Install: `npm install -g gogcli` or see [gog documentation](https://github.com/drgsn/gog)
   - Authenticate: `gog auth login`

## Setup

1. Find your Google Drive folder ID:
   - Open Google Drive in your browser
   - Navigate to the folder containing `Health Connect.zip`
   - Copy the ID from the URL: `drive.google.com/drive/folders/YOUR_FOLDER_ID`

2. Create config file at `~/.config/samsung-health/config.yaml`:

```yaml
google_drive:
  folder_id: "YOUR_GOOGLE_DRIVE_FOLDER_ID"
  account: "your.email@gmail.com"
  file_name: "Health Connect.zip"

goals:
  daily_steps: 10000
  sleep_hours: 8

timezone: "Europe/Copenhagen"  # Your timezone
```

3. Test the connection:
```bash
shealth sync
```

## Usage

```bash
# Sync latest data from Google Drive
shealth sync

# Quick daily snapshot
shealth today

# Check data status
shealth status

# Sleep analysis (last 7 days)
shealth sleep --days 7

# Step tracking
shealth steps --week
shealth steps --month

# Heart rate analysis
shealth heart --days 14

# Blood oxygen
shealth spo2 --days 7

# Workout history
shealth workout --days 30

# Comprehensive report
shealth report --days 7

# JSON output (for scripting)
shealth --json status
shealth --json sleep --days 7
```

## Data Source

The tool expects Samsung Health Connect to sync a `Health Connect.zip` file to Google Drive containing:
- `health_connect_export.db` - SQLite database with all health records

Samsung Health Connect can be configured to sync this data daily.

## Health Metrics

### Sleep Stages

| Code | Stage |
|------|-------|
| 1 | Light Sleep |
| 4 | Deep Sleep |
| 5 | Awake |
| 6 | REM Sleep |

### Exercise Types

| Code | Type |
|------|------|
| 53 | Walking |
| 33 | Running |
| 61 | Hiking |
| 21 | Cycling |
| 58 | Swimming |
| 4 | Weight Training |
| 66 | Yoga |
| 28 | HIIT |

## Local Storage

- **Database:** `~/.local/share/samsung-health/health.db`
- **Config:** `~/.config/samsung-health/config.yaml`
- **Cache:** `~/.local/share/samsung-health/cache/`

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License - see [LICENSE](LICENSE)
