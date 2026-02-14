"""Chart generation for Samsung Health data."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from .config import get_config
from .database import get_db

# Color palette - dark theme inspired
COLORS = {
    "background": "#1a1a2e",
    "surface": "#16213e",
    "text": "#e0e0e0",
    "text_dim": "#888888",
    "grid": "#333355",
    "accent": "#0f3460",
    "blue": "#4cc9f0",
    "purple": "#7b2cbf",
    "pink": "#f72585",
    "green": "#4ade80",
    "yellow": "#fbbf24",
    "red": "#ef4444",
    "orange": "#fb923c",
    "cyan": "#22d3ee",
    # Sleep stages
    "light": "#60a5fa",
    "deep": "#7c3aed",
    "rem": "#f472b6",
    "awake": "#fbbf24",
}

STAGE_COLORS = {
    "Light": COLORS["light"],
    "Deep": COLORS["deep"],
    "REM": COLORS["rem"],
    "Awake": COLORS["awake"],
}


def _apply_dark_theme(fig: plt.Figure, ax: plt.Axes) -> None:
    """Apply consistent dark theme to a chart."""
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.grid(axis="y", color=COLORS["grid"], alpha=0.3, linewidth=0.5)
    ax.title.set_color(COLORS["text"])
    ax.xaxis.label.set_color(COLORS["text_dim"])
    ax.yaxis.label.set_color(COLORS["text_dim"])


def _save_chart(fig: plt.Figure, output: Optional[str] = None) -> str:
    """Save chart to file and return the path."""
    if output:
        path = output
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="shealth_")
        path = tmp.name
        tmp.close()

    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def chart_sleep(days: int = 30, output: Optional[str] = None) -> str:
    """Generate sleep duration chart with stage breakdown.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()
    config = get_config()
    goal_hours = config.get("goals.sleep_hours", 8)

    sessions = db.get_sleep_sessions(days=days)
    if sessions.empty:
        raise ValueError("No sleep data found for this period")

    # Get stage data for each session
    chart_data = []
    for _, session in sessions.iterrows():
        stages = db.get_sleep_stage_summary(session["row_id"])
        date_str = session["start_time"].split()[0] if isinstance(session["start_time"], str) else str(session["start_time"])[:10]
        total_h = session["duration_minutes"] / 60
        total_stage_min = sum(stages.values()) or session["duration_minutes"]

        chart_data.append({
            "date": date_str,
            "total": total_h,
            "Light": stages.get("Light", 0) / 60,
            "Deep": stages.get("Deep", 0) / 60,
            "REM": stages.get("REM", 0) / 60,
            "Awake": stages.get("Awake", 0) / 60,
        })

    df = pd.DataFrame(chart_data).sort_values("date")

    # Limit to most recent entries for readability
    if len(df) > 45:
        df = df.tail(45)

    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(fig, ax)

    x = np.arange(len(df))
    width = 0.7

    # Stacked bars
    bottom = np.zeros(len(df))
    for stage in ["Deep", "Light", "REM", "Awake"]:
        values = df[stage].values
        ax.bar(x, values, width, bottom=bottom, label=stage,
               color=STAGE_COLORS[stage], alpha=0.9, edgecolor="none")
        bottom += values

    # Goal line
    ax.axhline(y=goal_hours, color=COLORS["green"], linestyle="--",
               alpha=0.7, linewidth=1.5, label=f"Goal ({goal_hours}h)")

    # Average line
    avg = df["total"].mean()
    ax.axhline(y=avg, color=COLORS["cyan"], linestyle=":",
               alpha=0.5, linewidth=1, label=f"Avg ({avg:.1f}h)")

    ax.set_title("Sleep Duration & Stages", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Hours")
    ax.set_xticks(x[::max(1, len(x) // 10)])
    ax.set_xticklabels(df["date"].values[::max(1, len(x) // 10)], rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=8, facecolor=COLORS["surface"],
              edgecolor=COLORS["grid"], labelcolor=COLORS["text_dim"])

    return _save_chart(fig, output)


def chart_steps(days: int = 30, output: Optional[str] = None) -> str:
    """Generate daily steps bar chart.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()
    config = get_config()
    goal = config.get("goals.daily_steps", 10000)

    daily_steps = db.get_daily_steps(days=days)
    if daily_steps.empty:
        raise ValueError("No step data found for this period")

    df = daily_steps.sort_values("date")
    if len(df) > 45:
        df = df.tail(45)

    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(fig, ax)

    x = np.arange(len(df))
    steps = df["steps"].values

    # Color bars based on goal achievement
    colors = [COLORS["green"] if s >= goal else COLORS["blue"] for s in steps]
    ax.bar(x, steps, 0.7, color=colors, alpha=0.85, edgecolor="none")

    # Goal line
    ax.axhline(y=goal, color=COLORS["yellow"], linestyle="--",
               alpha=0.7, linewidth=1.5, label=f"Goal ({goal:,})")

    # Average line
    avg = steps.mean()
    ax.axhline(y=avg, color=COLORS["cyan"], linestyle=":",
               alpha=0.5, linewidth=1, label=f"Avg ({avg:,.0f})")

    ax.set_title("Daily Steps", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Steps")
    ax.set_xticks(x[::max(1, len(x) // 10)])
    ax.set_xticklabels(df["date"].values[::max(1, len(x) // 10)], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(loc="upper right", fontsize=8, facecolor=COLORS["surface"],
              edgecolor=COLORS["grid"], labelcolor=COLORS["text_dim"])

    return _save_chart(fig, output)


def chart_heart(days: int = 30, output: Optional[str] = None) -> str:
    """Generate heart rate trend chart with min/max band.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()

    daily = db.get_daily_heart_rate(days=days)
    if daily.empty:
        raise ValueError("No heart rate data found for this period")

    df = daily.sort_values("date")
    if len(df) > 45:
        df = df.tail(45)

    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(fig, ax)

    x = np.arange(len(df))

    # Min/Max band
    ax.fill_between(x, df["min_hr"].values, df["max_hr"].values,
                    color=COLORS["pink"], alpha=0.15, label="Min–Max range")

    # Average line
    ax.plot(x, df["avg_hr"].values, color=COLORS["pink"], linewidth=2,
            marker="o", markersize=4, label="Average HR")

    # Overall average
    overall_avg = df["avg_hr"].mean()
    ax.axhline(y=overall_avg, color=COLORS["cyan"], linestyle=":",
               alpha=0.5, linewidth=1, label=f"Period avg ({overall_avg:.0f} bpm)")

    ax.set_title("Heart Rate Trend", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("BPM")
    ax.set_xticks(x[::max(1, len(x) // 10)])
    ax.set_xticklabels(df["date"].values[::max(1, len(x) // 10)], rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=8, facecolor=COLORS["surface"],
              edgecolor=COLORS["grid"], labelcolor=COLORS["text_dim"])

    return _save_chart(fig, output)


def chart_spo2(days: int = 30, output: Optional[str] = None) -> str:
    """Generate SpO2 trend chart with normal range.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()

    readings = db.get_spo2_readings(days=days)
    if readings.empty:
        raise ValueError("No SpO2 data found for this period")

    # Group by date
    daily = readings.groupby("date").agg({
        "spo2": ["mean", "min", "max"]
    }).round(1)
    daily.columns = ["avg", "min", "max"]
    daily = daily.reset_index().sort_values("date")

    if len(daily) > 45:
        daily = daily.tail(45)

    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(fig, ax)

    x = np.arange(len(daily))

    # Normal range band (95-100%)
    ax.axhspan(95, 100, color=COLORS["green"], alpha=0.08, label="Normal (95-100%)")
    ax.axhspan(90, 95, color=COLORS["yellow"], alpha=0.05, label="Low (90-95%)")

    # Min/Max band
    ax.fill_between(x, daily["min"].values, daily["max"].values,
                    color=COLORS["cyan"], alpha=0.2)

    # Average line
    ax.plot(x, daily["avg"].values, color=COLORS["cyan"], linewidth=2,
            marker="o", markersize=5, label="Average SpO2")

    ax.set_title("Blood Oxygen (SpO2)", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("SpO2 %")
    ax.set_ylim(85, 101)
    ax.set_xticks(x[::max(1, len(x) // 10)])
    ax.set_xticklabels(daily["date"].values[::max(1, len(x) // 10)], rotation=45, ha="right")
    ax.legend(loc="lower right", fontsize=8, facecolor=COLORS["surface"],
              edgecolor=COLORS["grid"], labelcolor=COLORS["text_dim"])

    return _save_chart(fig, output)


def chart_workouts(days: int = 30, output: Optional[str] = None) -> str:
    """Generate workout frequency and duration chart.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()

    workouts = db.get_workouts(days=days)
    if workouts.empty:
        raise ValueError("No workout data found for this period")

    # Group by type
    type_summary = workouts.groupby("exercise_name").agg({
        "duration_minutes": ["count", "sum", "mean"]
    })
    type_summary.columns = ["count", "total_min", "avg_min"]
    type_summary = type_summary.sort_values("total_min", ascending=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    _apply_dark_theme(fig, ax1)
    ax2.set_facecolor(COLORS["surface"])
    ax2.tick_params(colors=COLORS["text_dim"], labelsize=9)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color(COLORS["grid"])
    ax2.spines["bottom"].set_color(COLORS["grid"])

    # Left: total time per type (horizontal bars)
    palette = [COLORS["blue"], COLORS["purple"], COLORS["pink"],
               COLORS["green"], COLORS["orange"], COLORS["cyan"]]
    bar_colors = [palette[i % len(palette)] for i in range(len(type_summary))]

    ax1.barh(type_summary.index, type_summary["total_min"], color=bar_colors, alpha=0.85)
    ax1.set_xlabel("Total Minutes")
    ax1.set_title("By Total Time", fontsize=11, color=COLORS["text"])

    # Right: count per type
    ax2.barh(type_summary.index, type_summary["count"], color=bar_colors, alpha=0.85)
    ax2.set_xlabel("Sessions")
    ax2.set_title("By Frequency", fontsize=11, color=COLORS["text"])
    ax2.grid(axis="x", color=COLORS["grid"], alpha=0.3, linewidth=0.5)

    fig.suptitle(f"Workouts ({days} days)", fontsize=14,
                 fontweight="bold", color=COLORS["text"], y=1.02)

    return _save_chart(fig, output)


def chart_overview(days: int = 30, output: Optional[str] = None) -> str:
    """Generate 2x2 overview dashboard.

    Args:
        days: Number of days to chart.
        output: Output file path. Auto-generates if None.

    Returns:
        Path to the generated PNG file.
    """
    db = get_db()
    config = get_config()
    step_goal = config.get("goals.daily_steps", 10000)
    sleep_goal = config.get("goals.sleep_hours", 8)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor(COLORS["background"])
    fig.suptitle(f"Health Dashboard ({days} days)",
                 fontsize=16, fontweight="bold", color=COLORS["text"], y=0.98)

    # --- Sleep (top-left) ---
    ax = axes[0, 0]
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])

    try:
        sessions = db.get_sleep_sessions(days=days)
        if not sessions.empty:
            sleep_data = []
            for _, s in sessions.iterrows():
                date_str = s["start_time"].split()[0] if isinstance(s["start_time"], str) else str(s["start_time"])[:10]
                sleep_data.append({"date": date_str, "hours": s["duration_minutes"] / 60})
            sdf = pd.DataFrame(sleep_data).sort_values("date").tail(30)

            x = np.arange(len(sdf))
            ax.bar(x, sdf["hours"].values, color=COLORS["purple"], alpha=0.8)
            ax.axhline(y=sleep_goal, color=COLORS["green"], linestyle="--", alpha=0.6, linewidth=1)
            ax.set_title("Sleep", fontsize=11, color=COLORS["text"])
            ax.set_ylabel("Hours", color=COLORS["text_dim"], fontsize=8)
            ax.set_xticks(x[::max(1, len(x) // 5)])
            ax.set_xticklabels(sdf["date"].values[::max(1, len(x) // 5)], rotation=45, ha="right", fontsize=7)
        else:
            ax.text(0.5, 0.5, "No sleep data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
            ax.set_title("Sleep", fontsize=11, color=COLORS["text"])
    except Exception:
        ax.text(0.5, 0.5, "No sleep data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
        ax.set_title("Sleep", fontsize=11, color=COLORS["text"])

    # --- Steps (top-right) ---
    ax = axes[0, 1]
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])

    try:
        daily_steps = db.get_daily_steps(days=days)
        if not daily_steps.empty:
            sdf = daily_steps.sort_values("date").tail(30)
            x = np.arange(len(sdf))
            colors = [COLORS["green"] if s >= step_goal else COLORS["blue"] for s in sdf["steps"].values]
            ax.bar(x, sdf["steps"].values, color=colors, alpha=0.8)
            ax.axhline(y=step_goal, color=COLORS["yellow"], linestyle="--", alpha=0.6, linewidth=1)
            ax.set_title("Steps", fontsize=11, color=COLORS["text"])
            ax.set_ylabel("Steps", color=COLORS["text_dim"], fontsize=8)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
            ax.set_xticks(x[::max(1, len(x) // 5)])
            ax.set_xticklabels(sdf["date"].values[::max(1, len(x) // 5)], rotation=45, ha="right", fontsize=7)
        else:
            ax.text(0.5, 0.5, "No step data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
            ax.set_title("Steps", fontsize=11, color=COLORS["text"])
    except Exception:
        ax.text(0.5, 0.5, "No step data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
        ax.set_title("Steps", fontsize=11, color=COLORS["text"])

    # --- Heart Rate (bottom-left) ---
    ax = axes[1, 0]
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])

    try:
        daily_hr = db.get_daily_heart_rate(days=days)
        if not daily_hr.empty:
            hdf = daily_hr.sort_values("date").tail(30)
            x = np.arange(len(hdf))
            ax.fill_between(x, hdf["min_hr"].values, hdf["max_hr"].values, color=COLORS["pink"], alpha=0.15)
            ax.plot(x, hdf["avg_hr"].values, color=COLORS["pink"], linewidth=1.5, marker="o", markersize=3)
            ax.set_title("Heart Rate", fontsize=11, color=COLORS["text"])
            ax.set_ylabel("BPM", color=COLORS["text_dim"], fontsize=8)
            ax.set_xticks(x[::max(1, len(x) // 5)])
            ax.set_xticklabels(hdf["date"].values[::max(1, len(x) // 5)], rotation=45, ha="right", fontsize=7)
        else:
            ax.text(0.5, 0.5, "No HR data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
            ax.set_title("Heart Rate", fontsize=11, color=COLORS["text"])
    except Exception:
        ax.text(0.5, 0.5, "No HR data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
        ax.set_title("Heart Rate", fontsize=11, color=COLORS["text"])

    # --- SpO2 (bottom-right) ---
    ax = axes[1, 1]
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])

    try:
        readings = db.get_spo2_readings(days=days)
        if not readings.empty:
            daily_spo2 = readings.groupby("date").agg({"spo2": ["mean", "min", "max"]}).round(1)
            daily_spo2.columns = ["avg", "min", "max"]
            daily_spo2 = daily_spo2.reset_index().sort_values("date").tail(30)

            x = np.arange(len(daily_spo2))
            ax.axhspan(95, 100, color=COLORS["green"], alpha=0.08)
            ax.fill_between(x, daily_spo2["min"].values, daily_spo2["max"].values, color=COLORS["cyan"], alpha=0.2)
            ax.plot(x, daily_spo2["avg"].values, color=COLORS["cyan"], linewidth=1.5, marker="o", markersize=3)
            ax.set_title("SpO2", fontsize=11, color=COLORS["text"])
            ax.set_ylabel("%", color=COLORS["text_dim"], fontsize=8)
            ax.set_ylim(85, 101)
            ax.set_xticks(x[::max(1, len(x) // 5)])
            ax.set_xticklabels(daily_spo2["date"].values[::max(1, len(x) // 5)], rotation=45, ha="right", fontsize=7)
        else:
            ax.text(0.5, 0.5, "No SpO2 data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
            ax.set_title("SpO2", fontsize=11, color=COLORS["text"])
    except Exception:
        ax.text(0.5, 0.5, "No SpO2 data", transform=ax.transAxes, ha="center", color=COLORS["text_dim"])
        ax.set_title("SpO2", fontsize=11, color=COLORS["text"])

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _save_chart(fig, output)
