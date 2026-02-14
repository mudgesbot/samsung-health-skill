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
- 📈 **Charts** - Beautiful dark-themed visualizations (sleep, steps, heart rate, SpO2, workouts, overview dashboard)

## Installation

```bash
# Clone the repository
git clone https://github.com/mudgesbot/samsung-health-skill.git
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

1. **Samsung Galaxy Watch/Ring** with Samsung Health app
2. **Samsung Health Connect** app configured to back up data to Google Drive
3. **gog CLI** for Google Drive access
   - Part of [Clawdbot](https://github.com/clawdbot/clawdbot) ecosystem
   - Or use any tool that can download from Google Drive

### Setting Up Samsung Health Connect Backup

1. Install **Samsung Health Connect** from Galaxy Store
2. Open the app → Settings → **Backup and restore**
3. Enable **Back up to Google Drive**
4. Select backup frequency (daily recommended)
5. The app will create a `Health Connect.zip` file in your Drive

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

# Charts (generates PNG images)
shealth chart sleep --days 30          # Sleep stages stacked bar
shealth chart steps --days 30          # Daily steps with goal line
shealth chart heart --days 30          # Heart rate trend with min/max band
shealth chart spo2 --days 30           # Blood oxygen with normal range
shealth chart workouts --days 30       # Workout frequency by type
shealth chart overview --days 30       # 2x2 health dashboard

# Save chart to specific file
shealth chart overview -o dashboard.png
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

## Example Output

### Daily Snapshot
```
📅 Today (2026-01-30)

  🚶 Steps: 8,432 / 10,000 (84%) [████████░░]
  😴 Sleep: 7.2h ✅
  ❤️  Heart: 72 bpm avg
  🏋️  Workouts: 1
  🫁 SpO2: 96% ✅
```

### Sleep Analysis
```
😴 Sleep Analysis (7 days)

  Sessions: 7
  Average: 7.1h ✅ (goal: 8h)
  Trend: ▆▅▇█▆▇▅

  Stage Breakdown:
    Light:   22.0%  ████
    Deep:    45.0%  █████████
    REM:     25.0%  █████
    Awake:    8.0%  █
```

### Health Report
```
📊 Health Report (7 days)

  Energy Score: 82/100

  😴 Sleep
    Average: 7.1h (goal: 8h)
    Sessions: 7

  🚶 Activity
    Avg steps: 8,234 (goal: 10,000)
    Workouts: 12

  ❤️ Heart Rate
    Average: 74 bpm
    Range: 52 - 142 bpm
```

## Charts

Generate beautiful dark-themed charts for any health metric. All charts support `--days` and `--output` options.

| Command | Description |
|---------|-------------|
| `shealth chart sleep` | Sleep duration with stage breakdown (Deep/Light/REM/Awake) |
| `shealth chart steps` | Daily steps with goal line (green = goal met) |
| `shealth chart heart` | Heart rate trend with min/max band |
| `shealth chart spo2` | Blood oxygen with normal range overlay |
| `shealth chart workouts` | Workout frequency and duration by type |
| `shealth chart overview` | 2x2 dashboard combining all metrics |

Charts are saved as PNG files (150 DPI). By default they go to a temp directory; use `-o FILE` to specify the output path.

### Dependencies

Charts require `matplotlib` and `numpy`, which are installed automatically with the package.

## Troubleshooting

### "Database not found" error
Run `shealth sync` first to download data from Google Drive.

### "Google Drive not configured" error
Create config file at `~/.config/samsung-health/config.yaml` with your folder ID and account.

### No data after sync
1. Check if `Health Connect.zip` exists in your Google Drive folder
2. Verify the folder ID is correct (from the Drive URL)
3. Make sure Samsung Health Connect backup is enabled

### SpO2/HRV shows 0 records
Some metrics require specific Samsung devices (Galaxy Watch 4+, Galaxy Ring) and may need to be enabled in Samsung Health settings.

### Old data / not updating
- Samsung Health Connect syncs daily by default
- Run `shealth sync --force` to re-download

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License - see [LICENSE](LICENSE)
