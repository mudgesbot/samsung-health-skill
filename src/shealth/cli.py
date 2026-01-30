"""CLI entry point for Samsung Health tool."""

import json
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import EXERCISE_TYPES, SLEEP_STAGES, get_config
from .database import get_db
from .sync import get_last_sync_time, sync_data

console = Console()

# Input validation constants
MAX_DAYS = 3650  # 10 years max
MIN_DAYS = 1


def validate_days(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Validate days parameter is within reasonable range."""
    if value < MIN_DAYS:
        raise click.BadParameter(f"Must be at least {MIN_DAYS}")
    if value > MAX_DAYS:
        raise click.BadParameter(f"Cannot exceed {MAX_DAYS} days (10 years)")
    return value


def make_sparkline(values: list[float], width: int = 10) -> str:
    """Create a simple sparkline from values."""
    if not values:
        return ""

    # Normalize to 0-7 range for sparkline characters
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val or 1

    chars = "▁▂▃▄▅▆▇█"
    sparkline = ""
    for v in values[-width:]:
        idx = int((v - min_val) / range_val * 7)
        sparkline += chars[idx]
    return sparkline


@click.group()
@click.version_option(version=__version__)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def main(ctx: click.Context, json_output: bool) -> None:
    """Samsung Health Connect CLI - Analyze your health data."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


@main.command()
@click.option("--force", "-f", is_flag=True, help="Force re-download")
@click.option("--watch", "-w", is_flag=True, help="Watch for changes (not implemented)")
def sync(force: bool, watch: bool) -> None:
    """Sync data from Google Drive."""
    if watch:
        console.print("[yellow]Watch mode not yet implemented[/yellow]")
        return

    success = sync_data(force=force)
    if success:
        console.print("\n[green]✓ Sync complete![/green]")
    else:
        console.print("\n[yellow]Sync finished (no new data)[/yellow]")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show data status and statistics."""
    json_output = ctx.obj.get("json", False)
    config = get_config()

    try:
        db = get_db()
        counts = db.get_table_counts()
        date_range = db.get_date_range()
        last_sync = get_last_sync_time()

        if json_output:
            output = {
                "last_sync": last_sync.isoformat() if last_sync else None,
                "date_range": {
                    "start": date_range[0].isoformat() if date_range[0] else None,
                    "end": date_range[1].isoformat() if date_range[1] else None,
                },
                "record_counts": counts,
            }
            click.echo(json.dumps(output, indent=2))
            return

        console.print("\n[bold]📊 Samsung Health Data Status[/bold]\n")

        # Last sync
        if last_sync:
            age = datetime.now() - last_sync
            age_str = f"{age.seconds // 3600}h {(age.seconds % 3600) // 60}m ago" if age.days == 0 else f"{age.days}d ago"
            console.print(f"  Last sync: {last_sync.strftime('%Y-%m-%d %H:%M')} ({age_str})")
        else:
            console.print("  [red]No data synced yet. Run 'shealth sync' first.[/red]")
            return

        # Date range
        if date_range[0] and date_range[1]:
            days = (date_range[1] - date_range[0]).days
            console.print(f"  Data range: {date_range[0].strftime('%Y-%m-%d')} → {date_range[1].strftime('%Y-%m-%d')} ({days} days)")

        console.print()

        # Record counts table
        table = Table(title="Record Counts", show_header=True)
        table.add_column("Data Type", style="cyan")
        table.add_column("Records", justify="right", style="green")

        display_names = {
            "sleep_session_record_table": "😴 Sleep Sessions",
            "sleep_stages_table": "   └─ Sleep Stages",
            "steps_record_table": "🚶 Step Records",
            "heart_rate_record_table": "❤️  Heart Rate Sessions",
            "heart_rate_record_series_table": "   └─ HR Samples",
            "heart_rate_variability_rmssd_record_table": "💓 HRV Records",
            "resting_heart_rate_record_table": "🛋️  Resting HR",
            "exercise_session_record_table": "🏋️  Workouts",
            "weight_record_table": "⚖️  Weight Records",
            "oxygen_saturation_record_table": "🫁 SpO2 Records",
        }

        for table_name, count in counts.items():
            display = display_names.get(table_name, table_name)
            table.add_row(display, f"{count:,}")

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=7, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.option("--date", "target_date", type=str, help="Specific date (YYYY-MM-DD)")
@click.pass_context
def sleep(ctx: click.Context, days: int, target_date: str | None) -> None:
    """Analyze sleep patterns."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()
        config = get_config()
        goal_hours = config.get("goals.sleep_hours", 8)

        end_date = datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.now()
        sessions = db.get_sleep_sessions(days=days, end_date=end_date)

        if sessions.empty:
            console.print("[yellow]No sleep data found for this period[/yellow]")
            return

        # Calculate summary stats
        sessions["duration_hours"] = sessions["duration_minutes"] / 60
        avg_duration = sessions["duration_hours"].mean()
        total_sessions = len(sessions)

        # Get stage breakdown for each session
        all_stages = {"Light": 0, "Deep": 0, "REM": 0, "Awake": 0}
        for _, session in sessions.iterrows():
            stages = db.get_sleep_stage_summary(session["row_id"])
            for stage, minutes in stages.items():
                if stage in all_stages:
                    all_stages[stage] += minutes

        total_stage_minutes = sum(all_stages.values())
        stage_pcts = {k: (v / total_stage_minutes * 100) if total_stage_minutes > 0 else 0 for k, v in all_stages.items()}

        if json_output:
            output = {
                "period_days": days,
                "sessions": total_sessions,
                "avg_duration_hours": round(avg_duration, 2),
                "goal_hours": goal_hours,
                "stage_percentages": {k: round(v, 1) for k, v in stage_pcts.items()},
                "sessions_data": sessions.to_dict(orient="records"),
            }
            click.echo(json.dumps(output, indent=2, default=str))
            return

        console.print(f"\n[bold]😴 Sleep Analysis ({days} days)[/bold]\n")

        # Summary stats
        goal_diff = avg_duration - goal_hours
        goal_emoji = "✅" if goal_diff >= 0 else "⚠️"
        console.print(f"  Sessions: {total_sessions}")
        console.print(f"  Average: {avg_duration:.1f}h {goal_emoji} (goal: {goal_hours}h)")

        # Sparkline of recent sleep
        durations = sessions["duration_hours"].tolist()[::-1]  # Oldest to newest
        console.print(f"  Trend: {make_sparkline(durations, 14)}")

        console.print(f"\n  [bold]Stage Breakdown:[/bold]")
        console.print(f"    Light:  {stage_pcts['Light']:5.1f}%  {'█' * int(stage_pcts['Light'] / 5)}")
        console.print(f"    Deep:   {stage_pcts['Deep']:5.1f}%  {'█' * int(stage_pcts['Deep'] / 5)}")
        console.print(f"    REM:    {stage_pcts['REM']:5.1f}%  {'█' * int(stage_pcts['REM'] / 5)}")
        console.print(f"    Awake:  {stage_pcts['Awake']:5.1f}%  {'█' * int(stage_pcts['Awake'] / 5)}")

        # Recent sessions table
        console.print()
        table = Table(title="Recent Sleep Sessions", show_header=True)
        table.add_column("Date", style="cyan")
        table.add_column("Duration", justify="right")
        table.add_column("Bedtime", justify="center")
        table.add_column("Wake", justify="center")

        for _, row in sessions.head(7).iterrows():
            date_str = row["start_time"].split()[0] if isinstance(row["start_time"], str) else str(row["start_time"])[:10]
            duration = f"{row['duration_hours']:.1f}h"
            bedtime = row["start_time"].split()[1][:5] if isinstance(row["start_time"], str) else "?"
            wake = row["end_time"].split()[1][:5] if isinstance(row["end_time"], str) else "?"
            table.add_row(date_str, duration, bedtime, wake)

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=7, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.option("--week", "-w", is_flag=True, help="Show weekly summary")
@click.option("--month", "-m", is_flag=True, help="Show monthly summary")
@click.pass_context
def steps(ctx: click.Context, days: int, week: bool, month: bool) -> None:
    """Track daily steps."""
    json_output = ctx.obj.get("json", False)

    if week:
        days = 7
    elif month:
        days = 30

    try:
        db = get_db()
        config = get_config()
        goal = config.get("goals.daily_steps", 10000)

        daily_steps = db.get_daily_steps(days=days)

        if daily_steps.empty:
            console.print("[yellow]No step data found for this period[/yellow]")
            return

        total = daily_steps["steps"].sum()
        avg = daily_steps["steps"].mean()
        max_day = daily_steps.loc[daily_steps["steps"].idxmax()]
        days_over_goal = (daily_steps["steps"] >= goal).sum()

        if json_output:
            output = {
                "period_days": days,
                "total_steps": int(total),
                "daily_average": round(avg),
                "goal": goal,
                "days_over_goal": int(days_over_goal),
                "max_day": {"date": max_day["date"], "steps": int(max_day["steps"])},
                "daily_data": daily_steps.to_dict(orient="records"),
            }
            click.echo(json.dumps(output, indent=2))
            return

        console.print(f"\n[bold]🚶 Step Tracking ({days} days)[/bold]\n")

        # Summary
        goal_pct = (avg / goal * 100) if goal > 0 else 0
        console.print(f"  Total: {total:,.0f} steps")
        console.print(f"  Daily avg: {avg:,.0f} ({goal_pct:.0f}% of goal)")
        console.print(f"  Best day: {max_day['date']} ({max_day['steps']:,.0f})")
        console.print(f"  Goal days: {days_over_goal}/{len(daily_steps)} ({days_over_goal/len(daily_steps)*100:.0f}%)")

        # Sparkline
        step_values = daily_steps["steps"].tolist()[::-1]
        console.print(f"  Trend: {make_sparkline(step_values, 14)}")

        # Daily breakdown table
        console.print()
        table = Table(title="Daily Steps", show_header=True)
        table.add_column("Date", style="cyan")
        table.add_column("Steps", justify="right")
        table.add_column("Goal", justify="center")
        table.add_column("Progress", style="dim")

        for _, row in daily_steps.head(14).iterrows():
            steps_val = int(row["steps"])
            goal_emoji = "✅" if steps_val >= goal else "  "
            pct = steps_val / goal if goal > 0 else 0
            bar = "█" * min(int(pct * 10), 10) + "░" * max(10 - int(pct * 10), 0)
            table.add_row(row["date"], f"{steps_val:,}", goal_emoji, bar)

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=7, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.pass_context
def heart(ctx: click.Context, days: int) -> None:
    """Analyze heart rate data."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()

        stats = db.get_heart_rate_stats(days=days)
        daily = db.get_daily_heart_rate(days=days)

        if stats["sample_count"] == 0:
            console.print("[yellow]No heart rate data found for this period[/yellow]")
            return

        if json_output:
            output = {
                "period_days": days,
                "statistics": stats,
                "daily_data": daily.to_dict(orient="records") if not daily.empty else [],
            }
            click.echo(json.dumps(output, indent=2))
            return

        console.print(f"\n[bold]❤️ Heart Rate Analysis ({days} days)[/bold]\n")

        # Summary stats
        console.print(f"  Average: {stats['avg_hr']} bpm")
        console.print(f"  Range: {stats['min_hr']} - {stats['max_hr']} bpm")
        console.print(f"  Samples: {stats['sample_count']:,}")

        # Sparkline
        if not daily.empty:
            hr_values = daily["avg_hr"].tolist()[::-1]
            console.print(f"  Trend: {make_sparkline(hr_values, 14)}")

        # Daily breakdown
        if not daily.empty:
            console.print()
            table = Table(title="Daily Heart Rate", show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Avg", justify="right")
            table.add_column("Min", justify="right", style="green")
            table.add_column("Max", justify="right", style="red")
            table.add_column("Samples", justify="right", style="dim")

            for _, row in daily.head(14).iterrows():
                table.add_row(
                    row["date"],
                    f"{row['avg_hr']}",
                    f"{row['min_hr']}",
                    f"{row['max_hr']}",
                    f"{row['samples']:,}",
                )

            console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=30, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.option("--type", "workout_type", type=str, help="Filter by workout type")
@click.pass_context
def workout(ctx: click.Context, days: int, workout_type: str | None) -> None:
    """View workout history."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()

        # Map type name to code if provided
        type_code = None
        if workout_type:
            workout_type_lower = workout_type.lower()
            for code, name in EXERCISE_TYPES.items():
                if name.lower() == workout_type_lower:
                    type_code = code
                    break

        summary = db.get_workout_summary(days=days)
        workouts = db.get_workouts(days=days, exercise_type=type_code)

        if summary["total_workouts"] == 0:
            console.print("[yellow]No workouts found for this period[/yellow]")
            return

        if json_output:
            output = {
                "period_days": days,
                "summary": summary,
                "workouts": workouts.to_dict(orient="records") if not workouts.empty else [],
            }
            click.echo(json.dumps(output, indent=2, default=str))
            return

        console.print(f"\n[bold]🏋️ Workout Analysis ({days} days)[/bold]\n")

        # Summary
        console.print(f"  Total workouts: {summary['total_workouts']}")
        console.print(f"  Total time: {summary['total_minutes']:.0f} min ({summary['total_minutes']/60:.1f} h)")
        console.print(f"  Per week: {summary['total_workouts'] / (days/7):.1f} workouts")

        # By type breakdown
        console.print(f"\n  [bold]By Type:[/bold]")
        for name, stats in sorted(summary["by_type"].items(), key=lambda x: -x[1]["count"]):
            console.print(f"    {name}: {stats['count']}x ({stats['total_minutes']:.0f} min, avg {stats['avg_minutes']:.0f} min)")

        # Recent workouts table
        if not workouts.empty:
            console.print()
            table = Table(title="Recent Workouts", show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Type")
            table.add_column("Duration", justify="right")
            table.add_column("Title", style="dim")

            for _, row in workouts.head(10).iterrows():
                date_str = row["start_time"].split()[0] if isinstance(row["start_time"], str) else str(row["start_time"])[:10]
                duration = f"{row['duration_minutes']:.0f} min"
                title = (row["title"] or "")[:30]
                table.add_row(date_str, row["exercise_name"], duration, title)

            console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.pass_context
def today(ctx: click.Context) -> None:
    """Quick view of today's health metrics."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()
        config = get_config()
        summary = db.get_today_summary()

        step_goal = config.get("goals.daily_steps", 10000)
        sleep_goal = config.get("goals.sleep_hours", 8)

        if json_output:
            click.echo(json.dumps(summary, indent=2))
            return

        console.print(f"\n[bold]📅 Today ({summary['date']})[/bold]\n")

        # Steps
        step_pct = (summary["steps"] / step_goal * 100) if step_goal > 0 else 0
        step_bar = "█" * min(int(step_pct / 10), 10) + "░" * max(10 - int(step_pct / 10), 0)
        console.print(f"  🚶 Steps: {summary['steps']:,} / {step_goal:,} ({step_pct:.0f}%) [{step_bar}]")

        # Sleep
        if summary["sleep_hours"] > 0:
            sleep_emoji = "✅" if summary["sleep_hours"] >= sleep_goal else "⚠️"
            console.print(f"  😴 Sleep: {summary['sleep_hours']:.1f}h {sleep_emoji}")
        else:
            console.print("  😴 Sleep: No data")

        # Heart rate
        if summary["avg_hr"] > 0:
            console.print(f"  ❤️  Heart: {summary['avg_hr']:.0f} bpm avg")
        else:
            console.print("  ❤️  Heart: No data yet")

        # Workouts
        if summary["workouts"] > 0:
            console.print(f"  🏋️  Workouts: {summary['workouts']}")
        else:
            console.print("  🏋️  Workouts: None yet")

        # SpO2
        if summary["spo2"]:
            spo2_emoji = "✅" if summary["spo2"] >= 95 else "⚠️" if summary["spo2"] >= 90 else "🔴"
            console.print(f"  🫁 SpO2: {summary['spo2']}% {spo2_emoji}")

        console.print()

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=7, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.pass_context
def spo2(ctx: click.Context, days: int) -> None:
    """Analyze blood oxygen saturation."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()

        stats = db.get_spo2_stats(days=days)
        readings = db.get_spo2_readings(days=days)

        if stats["count"] == 0:
            console.print("[yellow]No SpO2 data found for this period[/yellow]")
            return

        if json_output:
            output = {
                "period_days": days,
                "statistics": stats,
                "readings": readings.to_dict(orient="records") if not readings.empty else [],
            }
            click.echo(json.dumps(output, indent=2))
            return

        console.print(f"\n[bold]🫁 Blood Oxygen Analysis ({days} days)[/bold]\n")

        # Summary
        avg_emoji = "✅" if stats["avg_spo2"] >= 95 else "⚠️" if stats["avg_spo2"] >= 90 else "🔴"
        console.print(f"  Average: {stats['avg_spo2']}% {avg_emoji}")
        console.print(f"  Range: {stats['min_spo2']}% - {stats['max_spo2']}%")
        console.print(f"  Readings: {stats['count']}")

        # Sparkline
        if not readings.empty:
            spo2_values = readings["spo2"].tolist()[::-1]
            console.print(f"  Trend: {make_sparkline(spo2_values, 14)}")

        # Daily breakdown
        if not readings.empty:
            daily = readings.groupby("date").agg({
                "spo2": ["mean", "min", "max", "count"]
            }).round(1)
            daily.columns = ["avg", "min", "max", "count"]
            daily = daily.reset_index().sort_values("date", ascending=False)

            console.print()
            table = Table(title="Daily SpO2", show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Avg", justify="right")
            table.add_column("Min", justify="right")
            table.add_column("Max", justify="right")
            table.add_column("Readings", justify="right", style="dim")

            for _, row in daily.head(10).iterrows():
                avg_color = "green" if row["avg"] >= 95 else "yellow" if row["avg"] >= 90 else "red"
                table.add_row(
                    row["date"],
                    f"[{avg_color}]{row['avg']:.0f}%[/{avg_color}]",
                    f"{row['min']:.0f}%",
                    f"{row['max']:.0f}%",
                    f"{int(row['count'])}",
                )

            console.print(table)

        console.print()
        console.print("  [dim]Normal SpO2: 95-100% | Below 90% = concerning[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--days", "-d", default=7, callback=validate_days, help="Number of days to analyze (1-3650)")
@click.pass_context
def report(ctx: click.Context, days: int) -> None:
    """Generate comprehensive health report."""
    json_output = ctx.obj.get("json", False)

    try:
        db = get_db()
        config = get_config()

        # Gather all data
        sleep_sessions = db.get_sleep_sessions(days=days)
        daily_steps = db.get_daily_steps(days=days)
        hr_stats = db.get_heart_rate_stats(days=days)
        workout_summary = db.get_workout_summary(days=days)

        # Calculate metrics
        sleep_avg = sleep_sessions["duration_minutes"].mean() / 60 if not sleep_sessions.empty else 0
        steps_avg = daily_steps["steps"].mean() if not daily_steps.empty else 0
        step_goal = config.get("goals.daily_steps", 10000)
        sleep_goal = config.get("goals.sleep_hours", 8)

        # Simple energy score (0-100)
        sleep_score = min(100, (sleep_avg / sleep_goal) * 100) if sleep_goal > 0 else 0
        steps_score = min(100, (steps_avg / step_goal) * 100) if step_goal > 0 else 0
        workout_score = min(100, (workout_summary["total_workouts"] / (days / 7 * 3)) * 100)  # 3x/week baseline
        energy_score = (sleep_score * 0.4 + steps_score * 0.3 + workout_score * 0.3)

        if json_output:
            output = {
                "period_days": days,
                "energy_score": round(energy_score, 1),
                "sleep": {
                    "avg_hours": round(sleep_avg, 2),
                    "sessions": len(sleep_sessions),
                    "score": round(sleep_score, 1),
                },
                "activity": {
                    "avg_steps": round(steps_avg),
                    "total_workouts": workout_summary["total_workouts"],
                    "steps_score": round(steps_score, 1),
                    "workout_score": round(workout_score, 1),
                },
                "heart": hr_stats,
            }
            click.echo(json.dumps(output, indent=2))
            return

        console.print(f"\n[bold]📊 Health Report ({days} days)[/bold]\n")

        # Energy Score
        score_color = "green" if energy_score >= 70 else "yellow" if energy_score >= 50 else "red"
        console.print(f"  [bold {score_color}]Energy Score: {energy_score:.0f}/100[/bold {score_color}]")
        console.print()

        # Sleep summary
        console.print("  [bold]😴 Sleep[/bold]")
        console.print(f"    Average: {sleep_avg:.1f}h (goal: {sleep_goal}h)")
        console.print(f"    Sessions: {len(sleep_sessions)}")
        console.print()

        # Activity summary
        console.print("  [bold]🚶 Activity[/bold]")
        console.print(f"    Avg steps: {steps_avg:,.0f} (goal: {step_goal:,})")
        console.print(f"    Workouts: {workout_summary['total_workouts']}")
        console.print()

        # Heart summary
        if hr_stats["sample_count"] > 0:
            console.print("  [bold]❤️ Heart Rate[/bold]")
            console.print(f"    Average: {hr_stats['avg_hr']} bpm")
            console.print(f"    Range: {hr_stats['min_hr']} - {hr_stats['max_hr']} bpm")

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")


if __name__ == "__main__":
    main()
