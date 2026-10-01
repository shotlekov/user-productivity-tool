#!/usr/bin/env python3
"""User productivity tool with optional GUI."""

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

# ===== CONFIGURATION =====

USER_PRODUCTIVITY_DEFAULT_ACTIONS = [
    "Ingest clip",
    "Edit clip",
    "Update detect",
    "Deactivate clip & delete detects",
    "Mark POI as Done",
]

USER_PRODUCTIVITY_ACTION_WEIGHTS = {
    "Ingest clip": 5.0,
    "Edit clip": 4.0,
    "Update detect": 2.5,
    "Deactivate clip & delete detects": 2.5,
    "Mark POI as Done": 1.0,
}

# ===== CORE LOGIC =====


def _normalize_key(value):
    return str(value or "").strip().lower().replace(" ", "_")


def _row_value(row, *keys):
    normalized = {_normalize_key(key): value for key, value in row.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value is not None:
            return str(value or "").strip()
    return ""


def _parse_action_log_dt(day_str, hour_str):
    day_text = str(day_str or "").strip().lstrip("\ufeff")
    hour_text = str(hour_str or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(f"{day_text} {hour_text}", fmt)
        except ValueError:
            continue
    return None


def _fmt_mmss_millis(seconds):
    if seconds is None:
        return ""
    total_ms = int(round(float(seconds) * 1000))
    minutes = total_ms // 60000
    remainder_ms = total_ms % 60000
    secs = remainder_ms / 1000.0
    return f"{minutes:02d}:{secs:06.3f}"


def _fmt_signed_mmss_millis(seconds):
    if seconds is None:
        return ""
    sign = "+" if seconds >= 0 else "-"
    return sign + _fmt_mmss_millis(abs(seconds))


def _fmt_signed_percent(value):
    if value is None:
        return ""
    return f"{float(value):+.1f}%"


def _fmt_score(value):
    if value is None:
        return ""
    return f"{float(value):.1f}"


def _fmt_analyzer_duration(seconds):
    if seconds is None:
        return ""
    total_seconds = float(seconds)
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _productivity_default_action_weight(action):
    return float(USER_PRODUCTIVITY_ACTION_WEIGHTS.get(action, 1.0))


def _normalize_productivity_action_weights(action_weights=None):
    weights = dict(USER_PRODUCTIVITY_ACTION_WEIGHTS)
    if action_weights:
        for action, value in dict(action_weights).items():
            action = str(action or "").strip()
            if not action:
                continue
            try:
                weight = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(weight) or weight < 0:
                continue
            weights[action] = weight
    return weights


def _productivity_action_weight(action, action_weights=None):
    weights = (
        action_weights
        if action_weights is not None
        else USER_PRODUCTIVITY_ACTION_WEIGHTS
    )
    return float(weights.get(action, _productivity_default_action_weight(action)))


def _productivity_action_sort_key(action):
    try:
        return (0, USER_PRODUCTIVITY_DEFAULT_ACTIONS.index(action))
    except ValueError:
        return (1, str(action or "").lower())


def _validate_action_log_headers(fieldnames):
    normalized = {_normalize_key(name) for name in (fieldnames or [])}
    required_groups = {
        "day": {"day"},
        "hour": {"hour", "time"},
        "username": {"username", "user", "user_name"},
        "action": {"action"},
    }
    missing = [
        display
        for display, aliases in required_groups.items()
        if not normalized.intersection(aliases)
    ]
    if missing:
        raise ValueError(
            "Action log CSV is missing required columns: " + ", ".join(missing)
        )


def _detect_action_log_dialect(sample):
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\\t|")
    except csv.Error:
        return csv.excel


def read_action_log_csv(csv_path):
    rows = []
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        reader = csv.DictReader(fh, dialect=_detect_action_log_dialect(sample))
        _validate_action_log_headers(reader.fieldnames)
        for row in reader:
            username = _row_value(row, "username", "user", "user_name")
            if not username or username.lower() == "system":
                continue
            action = _row_value(row, "action")
            day = _row_value(row, "day")
            hour = _row_value(row, "hour", "time")
            dt = _parse_action_log_dt(day, hour)
            if not action or dt is None:
                continue
            rows.append({"username": username, "action": action, "day": day, "dt": dt})
    return rows


def build_user_productivity_report(
    csv_path,
    threshold_minutes=5.0,
    selected_actions=None,
    action_weights=None,
    selected_users=None,
):
    action_weights = _normalize_productivity_action_weights(action_weights)
    try:
        threshold_seconds = float(threshold_minutes) * 60.0
    except (TypeError, ValueError):
        threshold_seconds = 300.0
    if threshold_seconds <= 0:
        threshold_seconds = 300.0

    rows = read_action_log_csv(csv_path)
    if selected_users is not None:
        selected_user_set = {str(username) for username in selected_users}
        rows = [row for row in rows if row["username"] in selected_user_set]
        selected_users = sorted(
            selected_user_set, key=lambda username: username.lower()
        )
    rows.sort(key=lambda row: (row["username"].lower(), row["dt"], row["action"]))

    deduped = []
    seen = set()
    for row in rows:
        key = (
            row["day"],
            row["dt"].strftime("%H:%M:%S"),
            row["username"],
            row["action"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    user_durations = {}
    action_durations = {}
    user_action_volumes = {}
    action_volumes = {}
    skipped_duplicate = 0
    skipped_long = 0

    for row in deduped:
        user_action_volumes[(row["username"], row["action"])] = (
            user_action_volumes.get((row["username"], row["action"]), 0) + 1
        )
        action_volumes[row["action"]] = action_volumes.get(row["action"], 0) + 1

    for idx, row in enumerate(deduped):
        if idx == 0:
            continue
        prev = deduped[idx - 1]
        if prev["username"] != row["username"] or prev["dt"].date() != row["dt"].date():
            continue
        delta_seconds = (row["dt"] - prev["dt"]).total_seconds()
        if delta_seconds <= 0:
            skipped_duplicate += 1
            continue
        if delta_seconds > threshold_seconds:
            skipped_long += 1
            continue
        user_durations.setdefault((row["username"], row["action"]), []).append(
            delta_seconds
        )
        action_durations.setdefault(row["action"], []).append(delta_seconds)

    all_actions = sorted(
        set(action_durations.keys()) | set(action_volumes.keys()),
        key=_productivity_action_sort_key,
    )
    if selected_actions is None:
        default_set = set(USER_PRODUCTIVITY_DEFAULT_ACTIONS)
        actions = [
            action
            for action in USER_PRODUCTIVITY_DEFAULT_ACTIONS
            if action in all_actions and action in default_set
        ]
        if not actions:
            actions = all_actions
        selected_actions = actions
    else:
        selected_set = {str(action) for action in selected_actions}
        actions = [action for action in all_actions if action in selected_set]
        selected_actions = actions

    users = sorted(
        {
            username
            for username, action in (
                set(user_durations.keys()) | set(user_action_volumes.keys())
            )
            if action in actions
        },
        key=lambda username: username.lower(),
    )
    user_active_days = {
        username: len(
            {
                row["dt"].date().isoformat()
                for row in deduped
                if row["username"] == username and row["action"] in actions
            }
        )
        for username in users
    }

    reference = {}
    combined_results = []
    for action in actions:
        durations = action_durations.get(action, [])
        avg_seconds = sum(durations) / len(durations) if durations else None
        if durations:
            combined_results.append((action, avg_seconds, len(durations)))
        avg_volume = (
            (
                sum(
                    (
                        user_action_volumes.get((username, action), 0)
                        / user_active_days.get(username, 1)
                    )
                    for username in users
                    if user_active_days.get(username, 0)
                )
                / len(users)
            )
            if users
            else 0
        )
        reference[action] = {
            "avg_seconds": avg_seconds,
            "duration": _fmt_mmss_millis(avg_seconds) if durations else "",
            "count": len(durations),
            "total_volume": action_volumes.get(action, 0),
            "avg_volume": avg_volume,
            "volume": f"{avg_volume:.1f}",
        }

    matrix = []
    per_user_results = []
    ranking = []
    reference_total_volume = sum(action_volumes.get(action, 0) for action in actions)
    reference_avg_volume_per_user = (
        (
            sum(
                sum(
                    user_action_volumes.get((username, action), 0) for action in actions
                )
                / user_active_days.get(username, 1)
                for username in users
                if user_active_days.get(username, 0)
            )
            / len(users)
        )
        if users
        else 0
    )
    weighted_reference_avg_volume_per_user = sum(
        (reference.get(action, {}).get("avg_volume") or 0)
        * _productivity_action_weight(action, action_weights)
        for action in actions
    )

    for username in users:
        cells = {}
        counts = {}
        deltas = {}
        display_cells = {}
        volume_cells = {}
        volume_deltas = {}
        volume_delta_values = {}
        total_volume_cells = {}
        total_volume = 0
        weighted_total_volume = 0.0
        avg_daily_volume_total = 0.0
        weighted_avg_daily_volume_total = 0.0
        active_days = user_active_days.get(username, 0)
        weighted_speed_ratio = 0.0
        speed_weight = 0.0
        user_duration_total = 0.0
        reference_duration_total = 0.0

        for action in actions:
            action_weight = _productivity_action_weight(action, action_weights)
            durations = user_durations.get((username, action), [])
            volume_count = user_action_volumes.get((username, action), 0)
            total_volume += volume_count
            weighted_total_volume += volume_count * action_weight
            avg_daily_volume = (volume_count / active_days) if active_days else 0
            avg_daily_volume_total += avg_daily_volume
            weighted_avg_daily_volume_total += avg_daily_volume * action_weight
            reference_avg_volume = reference.get(action, {}).get("avg_volume") or 0
            volume_delta = (
                (
                    (avg_daily_volume - reference_avg_volume)
                    / reference_avg_volume
                    * 100.0
                )
                if reference_avg_volume
                else None
            )
            volume_cells[action] = f"{avg_daily_volume:.1f}"
            total_volume_cells[action] = str(volume_count)
            volume_delta_values[action] = volume_delta
            volume_deltas[action] = _fmt_signed_percent(volume_delta)

            if durations:
                avg = sum(durations) / len(durations)
                per_user_results.append((username, action, avg, len(durations)))
                reference_avg = reference.get(action, {}).get("avg_seconds")
                delta = avg - reference_avg if reference_avg is not None else None
                if reference_avg and avg > 0:
                    weight = len(durations) * action_weight
                    weighted_speed_ratio += (reference_avg / avg) * weight
                    speed_weight += weight
                    user_duration_total += avg * weight
                    reference_duration_total += reference_avg * weight
                cells[action] = _fmt_mmss_millis(avg)
                deltas[action] = _fmt_signed_mmss_millis(delta)
                display_cells[action] = f"{cells[action]} ({deltas[action]})"
                counts[action] = len(durations)
            else:
                cells[action] = ""
                deltas[action] = ""
                display_cells[action] = ""
                counts[action] = 0

        volume_factor = (
            (weighted_avg_daily_volume_total / weighted_reference_avg_volume_per_user)
            if weighted_reference_avg_volume_per_user
            else None
        )
        speed_factor = (weighted_speed_ratio / speed_weight) if speed_weight else None
        score = (
            (volume_factor * speed_factor * 100.0)
            if volume_factor is not None and speed_factor is not None
            else None
        )
        avg_duration = (user_duration_total / speed_weight) if speed_weight else None
        reference_avg_duration = (
            (reference_duration_total / speed_weight) if speed_weight else None
        )
        ranking.append(
            {
                "username": username,
                "display_name": username,
                "total_volume": total_volume,
                "weighted_total_volume": weighted_total_volume,
                "weighted_total_volume_display": f"{weighted_total_volume:.1f}",
                "active_days": active_days,
                "avg_daily_volume": avg_daily_volume_total,
                "avg_daily_volume_display": f"{avg_daily_volume_total:.1f}",
                "weighted_avg_daily_volume": weighted_avg_daily_volume_total,
                "weighted_avg_daily_volume_display": f"{weighted_avg_daily_volume_total:.1f}",
                "volume_factor": volume_factor,
                "volume_delta": _fmt_signed_percent(
                    (volume_factor - 1.0) * 100.0 if volume_factor is not None else None
                ),
                "speed_factor": speed_factor,
                "speed_delta": _fmt_signed_percent(
                    (speed_factor - 1.0) * 100.0 if speed_factor is not None else None
                ),
                "avg_duration": _fmt_mmss_millis(avg_duration),
                "reference_avg_duration": _fmt_mmss_millis(reference_avg_duration),
                "score": score,
                "score_display": _fmt_score(score),
            }
        )
        matrix.append(
            {
                "username": username,
                "display_name": username,
                "cells": cells,
                "deltas": deltas,
                "display_cells": display_cells,
                "counts": counts,
                "volume_cells": volume_cells,
                "total_volume_cells": total_volume_cells,
                "volume_deltas": volume_deltas,
                "volume_delta_values": volume_delta_values,
                "total_volume": total_volume,
                "weighted_total_volume": weighted_total_volume,
                "weighted_total_volume_display": f"{weighted_total_volume:.1f}",
                "active_days": active_days,
                "avg_daily_volume": avg_daily_volume_total,
                "avg_daily_volume_display": f"{avg_daily_volume_total:.1f}",
                "weighted_avg_daily_volume": weighted_avg_daily_volume_total,
                "weighted_avg_daily_volume_display": f"{weighted_avg_daily_volume_total:.1f}",
            }
        )

    ranking = sorted(
        ranking,
        key=lambda row: (
            -(row["score"] if row["score"] is not None else -1),
            -row.get("avg_daily_volume", 0),
            row["display_name"].lower(),
        ),
    )
    for idx, row in enumerate(ranking, start=1):
        row["rank"] = idx

    return {
        "threshold_minutes": threshold_seconds / 60.0,
        "source_rows": len(rows),
        "deduped_rows": len(deduped),
        "skipped_duplicate": skipped_duplicate,
        "skipped_long": skipped_long,
        "actions": actions,
        "all_actions": all_actions,
        "selected_actions": selected_actions,
        "action_weights": {
            action: _productivity_action_weight(action, action_weights)
            for action in actions
        },
        "all_action_weights": {
            action: _productivity_action_weight(action, action_weights)
            for action in all_actions
        },
        "users": users,
        "selected_users": selected_users,
        "reference": reference,
        "volume_reference": {
            "total_volume": reference_total_volume,
            "avg_volume_per_user": reference_avg_volume_per_user,
            "avg_volume_display": f"{reference_avg_volume_per_user:.1f}"
            if users
            else "",
            "weighted_avg_volume_per_user": weighted_reference_avg_volume_per_user,
            "weighted_avg_volume_display": f"{weighted_reference_avg_volume_per_user:.1f}"
            if users
            else "",
            "basis": "average_daily",
        },
        "ranking_reference": {
            "score_display": "100.0" if users else "",
            "total_volume": f"{weighted_reference_avg_volume_per_user:.1f}"
            if users
            else "",
            "volume_delta": "+0.0%" if users else "",
            "speed_delta": "+0.0%" if users else "",
            "avg_duration": "",
        },
        "ranking": ranking,
        "matrix": matrix,
        "combined_results": combined_results,
        "per_user_results": per_user_results,
    }


# ===== MARKDOWN OUTPUT =====


def _markdown_cell(value):
    return str(value if value is not None else "").replace("|", "\\|")


def render_user_productivity_md(report, input_source=None):
    lines = []
    lines.append("# User Productivity Report")
    lines.append("")
    if input_source is not None:
        lines.append(f"- **Input source:** {input_source}")
    lines.append(f"- **Skip threshold:** {report['threshold_minutes']:g} minutes")
    lines.append(f"- **Source rows used:** {report.get('source_rows', 0)}")
    lines.append(f"- **Deduped rows:** {report.get('deduped_rows', 0)}")
    lines.append(f"- **Selected actions:** {len(report.get('actions', []))}")
    lines.append("")
    lines.append("## Action Weights")
    lines.append("")
    lines.append("| Action | Weight |")
    lines.append("|---|---:|")
    for action in report.get("actions", []):
        weight = report.get("action_weights", {}).get(
            action, _productivity_default_action_weight(action)
        )
        lines.append(f"| {_markdown_cell(action)} | {float(weight):.1f} |")
    lines.append("")
    lines.append("## User Productivity Ranking")
    lines.append("")
    lines.append(
        "| Rank | User | Total Actions | Weighted Total | Active Days | Weighted Daily Volume | Volume Delta | Speed Delta | Avg Duration | Score |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in report.get("ranking", []):
        lines.append(
            "| {rank} | {user} | {total} | {weighted_total} | {days} | {weighted_daily} | {volume_delta} | {speed_delta} | {avg_duration} | {score} |".format(
                rank=row.get("rank", ""),
                user=_markdown_cell(row.get("display_name") or row.get("username", "")),
                total=row.get("total_volume", ""),
                weighted_total=row.get("weighted_total_volume_display", ""),
                days=row.get("active_days", ""),
                weighted_daily=row.get("weighted_avg_daily_volume_display", ""),
                volume_delta=row.get("volume_delta", ""),
                speed_delta=row.get("speed_delta", ""),
                avg_duration=row.get("avg_duration", ""),
                score=row.get("score_display", ""),
            )
        )
    lines.append("")
    lines.append("## Combined Results")
    lines.append("")
    lines.append("| # | Action | Average Duration | Sample Size |")
    lines.append("|---:|---|---:|---:|")
    for idx, (action, avg_sec, count) in enumerate(
        report.get("combined_results", []), start=1
    ):
        lines.append(
            f"| {idx} | {_markdown_cell(action)} | {_fmt_analyzer_duration(avg_sec)} | {count} |"
        )
    lines.append("")
    lines.append("## Per-User Average Durations")
    lines.append("")
    users_sorted = sorted(
        {username for username, _, _, _ in report.get("per_user_results", [])}
    )
    for user_idx, username in enumerate(users_sorted, start=1):
        user_rows = [
            (action, avg_sec, count)
            for u, action, avg_sec, count in sorted(report.get("per_user_results", []))
            if u == username
        ]
        lines.append(f"### {user_idx}. {_markdown_cell(username)}")
        lines.append("")
        lines.append("| Action | Avg Duration | n |")
        lines.append("|---|---:|---:|")
        for action, avg_sec, count in user_rows:
            lines.append(
                f"| {_markdown_cell(action)} | {_fmt_analyzer_duration(avg_sec)} | {count} |"
            )
        lines.append("")
    lines.append("Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return "\n".join(lines)


# ===== ARGUMENT PARSING =====


def parse_weight_arg(weight_arg):
    if "=" not in str(weight_arg):
        raise argparse.ArgumentTypeError("weights must use ACTION=NUMBER")
    action, value = str(weight_arg).split("=", 1)
    action = action.strip()
    if not action:
        raise argparse.ArgumentTypeError("weight action cannot be empty")
    try:
        weight = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("weight value must be numeric") from exc
    if not math.isfinite(weight) or weight < 0:
        raise argparse.ArgumentTypeError(
            "weight value must be a non-negative finite number"
        )
    return action, weight


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read a CCR Users actions CSV and write or display a Markdown user productivity report.",
    )
    parser.add_argument(
        "--gui", action="store_true", help="Open the graphical interface."
    )
    parser.add_argument("--input", help="Path to the Users actions CSV file.")
    parser.add_argument(
        "--output", help="Path for the Markdown report. Prints to stdout when omitted."
    )
    parser.add_argument(
        "--threshold-minutes",
        type=float,
        default=5.0,
        help="Maximum action-to-action gap to count as processing time.",
    )
    parser.add_argument(
        "--action",
        action="append",
        dest="actions",
        help="Action to include. May be repeated.",
    )
    parser.add_argument(
        "--user",
        action="append",
        dest="users",
        help="User to include. May be repeated.",
    )
    parser.add_argument(
        "--weight",
        action="append",
        type=parse_weight_arg,
        default=[],
        help="Action weight as ACTION=NUMBER. May be repeated.",
    )
    args = parser.parse_args(argv)
    if not args.gui and argv and not args.input:
        parser.error("--input is required unless --gui is used")
    return args


# ===== DESIGN TOKENS =====


def _get_design_tokens(theme="light"):
    """Centralized design tokens for consistent visual language."""
    base = {
        "spacing": {
            "xs": 4,
            "sm": 8,
            "md": 16,
            "lg": 24,
            "xl": 32,
            "2xl": 48,
        },
        "border_radius": {
            "sm": 4,
            "md": 8,
            "lg": 12,
            "xl": 16,
            "full": 9999,
        },
        "shadow": {
            "none": "0 0 0 0 transparent",
            "xs": "0 1px 2px 0 rgba(0,0,0,0.05)",
            "sm": "0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1)",
            "md": "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)",
            "lg": "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)",
            "xl": "0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)",
        },
        "transition": {
            "fast": 100,
            "normal": 200,
            "slow": 300,
        },
        "z_index": {
            "base": 0,
            "dropdown": 100,
            "sticky": 200,
            "modal": 300,
            "popover": 400,
            "tooltip": 500,
        },
    }

    if theme == "dark":
        base["color"] = {
            # Base surfaces
            "bg_primary": "#0f172a",  # Slate-950
            "bg_secondary": "#1e293b",  # Slate-800
            "bg_tertiary": "#253047",  # Elevated
            "bg_hover": "#334155",  # Slate-700
            "bg_active": "#1e293b",  # Slate-800
            # Borders
            "border_subtle": "#1e293b",  # Slate-800
            "border_default": "#334155",  # Slate-700
            "border_emphasis": "#475569",  # Slate-600
            # Text
            "text_primary": "#f1f5f9",  # Slate-50
            "text_secondary": "#94a3b8",  # Slate-400
            "text_muted": "#64748b",  # Slate-500
            "text_inverse": "#0f172a",  # Slate-950
            # Accent (Cyan)
            "accent_primary": "#22d3ee",  # Cyan-400
            "accent_hover": "#67e8f9",  # Cyan-300
            "accent_active": "#0891b2",  # Cyan-600
            "accent_bg": "#164e63",  # Cyan-900/800
            "accent_text": "#0f172a",  # Slate-950
            # Semantic
            "success": "#22c55e",  # Green-500
            "success_bg": "#14532d",  # Green-900
            "success_text": "#dcfce7",  # Green-50
            "warning": "#f59e0b",  # Amber-500
            "warning_bg": "#78350f",  # Amber-900
            "warning_text": "#fef9c3",  # Amber-50
            "error": "#ef4444",  # Red-500
            "error_bg": "#7f1d1d",  # Red-900
            "error_text": "#fef2f2",  # Red-50
            "info": "#3b82f6",  # Blue-500
            "info_bg": "#1e3a5f",  # Blue-900
            "info_text": "#dbeafe",  # Blue-50
            # Selection
            "select_bg": "#164e63",  # Cyan-900/800
            "select_text": "#22d3ee",  # Cyan-400
            # Zebra striping
            "zebra_subtle": "#172033",  # Slightly darker than card
        }
    else:
        base["color"] = {
            # Base surfaces - increased contrast
            "bg_primary": "#e2e8f0",  # Slate-200 (was Slate-50)
            "bg_secondary": "#ffffff",  # White
            "bg_tertiary": "#f1f5f9",  # Slate-100 (was Slate-50)
            "bg_hover": "#cbd5e1",  # Slate-300 (was Slate-200)
            "bg_active": "#e2e8f0",  # Slate-200
            # Borders - darker for better contrast
            "border_subtle": "#cbd5e1",  # Slate-300
            "border_default": "#94a3b8",  # Slate-400 (was Slate-300)
            "border_emphasis": "#64748b",  # Slate-500 (was Slate-400)
            # Text - darker for better contrast
            "text_primary": "#0f172a",  # Slate-950
            "text_secondary": "#334155",  # Slate-700 (was Slate-600)
            "text_muted": "#475569",  # Slate-600 (was Slate-500)
            "text_inverse": "#ffffff",  # White
            # Accent (Blue)
            "accent_primary": "#2563eb",  # Blue-600
            "accent_hover": "#1d4ed8",  # Blue-700
            "accent_active": "#1e40af",  # Blue-800
            "accent_bg": "#dbeafe",  # Blue-100
            "accent_text": "#ffffff",  # White
            # Semantic
            "success": "#16a34a",  # Green-600
            "success_bg": "#dcfce7",  # Green-100
            "success_text": "#14532d",  # Green-900
            "warning": "#d97706",  # Amber-600
            "warning_bg": "#fef9c3",  # Amber-100
            "warning_text": "#78350f",  # Amber-900
            "error": "#dc2626",  # Red-600
            "error_bg": "#fef2f2",  # Red-100
            "error_text": "#7f1d1d",  # Red-900
            "info": "#2563eb",  # Blue-600
            "info_bg": "#dbeafe",  # Blue-100
            "info_text": "#1e3a5f",  # Blue-900
            # Selection
            "select_bg": "#dbeafe",  # Blue-100
            "select_text": "#1e40af",  # Blue-800
            # Zebra striping
            "zebra_subtle": "#f1f5f9",  # Slate-100 (was Slate-50)
        }

    return base


# ===== GUI FUNCTIONS =====


def discover_actions_for_gui(csv_path=None):
    actions = list(USER_PRODUCTIVITY_DEFAULT_ACTIONS)
    if csv_path:
        csv_actions = {row["action"] for row in read_action_log_csv(csv_path)}
        for action in sorted(csv_actions, key=_productivity_action_sort_key):
            if action not in actions:
                actions.append(action)
    weights = {
        action: _productivity_default_action_weight(action) for action in actions
    }
    return actions, weights


def discover_users_for_gui(csv_path=None):
    if not csv_path:
        return []
    users = {row["username"] for row in read_action_log_csv(csv_path)}
    return sorted(users, key=lambda username: username.lower())


def run_gui():
    import tkinter as tk
    from tkinter import scrolledtext, ttk
    import tkinter.font as tkfont

    # Add rounded rectangle method to Canvas
    def _create_rounded_rect(self, x1, y1, x2, y2, radius=12, **kwargs):
        """Create a rounded rectangle on the canvas."""
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    tk.Canvas.create_rounded_rect = _create_rounded_rect

    class UserProductivityApp:
        def __init__(self, root):
            self.tk = tk
            self.root = root
            self.root.title("User Productivity Tool")

            # Background task queue for thread-safe UI updates
            import queue
            import threading

            self._queue = queue
            self._threading = threading
            self._task_queue = queue.Queue()
            self._bg_thread = None

            # Initialize theme variable before font setup
            self.current_theme = tk.StringVar(value="light")
            self.csv_path_var = tk.StringVar()
            self.threshold_var = tk.StringVar(value="5")
            self.status_var = tk.StringVar(
                value="Select a user action log CSV to begin."
            )
            self.current_markdown = ""
            self.current_report = None
            self.action_rows = []
            self.user_rows = []
            self.ranking_sort_var = tk.StringVar(value="Score")
            self.ranking_desc_var = tk.BooleanVar(value=True)

            # Widget references for theme updates
            self.weights_canvas = None
            self.users_canvas = None
            self.result_text = None
            self.ranking_tree = None
            self.details_tree = None
            self.info_text_widgets = []

            # Set up proper font detection first
            self._setup_fonts()

            # Define palettes according to specification
            self.PALETTES = {
                "dark": {
                    "app": "#0f172a",  # Slate-950
                    "card": "#1e293b",  # Slate-800
                    "input": "#0f172a",  # Slate-950
                    "border": "#334155",  # Slate-700
                    "text": "#f1f5f9",  # Slate-50
                    "text2": "#94a3b8",  # Slate-400
                    "accent": "#22d3ee",  # Cyan-400
                    "accent_text": "#0f172a",  # Slate-950
                    "accent_hover": "#67e8f9",  # Cyan-300
                    "select": "#164e63",  # Slate-900/800 mix
                    "zebra": "#172033",  # Darker card
                },
                "light": {
                    "app": "#f1f5f9",  # Slate-50
                    "card": "#ffffff",  # White
                    "input": "#ffffff",  # White
                    "border": "#cbd5e1",  # Slate-200
                    "text": "#0f172a",  # Slate-950
                    "text2": "#475569",  # Slate-600
                    "accent": "#2563eb",  # Blue-600 (changed from 500 for better contrast)
                    "accent_text": "#ffffff",  # White
                    "accent_hover": "#1d4ed8",  # Blue-700
                    "select": "#dbeafe",  # Blue-100
                    "zebra": "#f8fafc",  # Slate-50
                },
            }

            self.current_theme = tk.StringVar(value="light")
            self.csv_path_var = tk.StringVar()
            self.threshold_var = tk.StringVar(value="5")
            self.status_var = tk.StringVar(
                value="Select a user action log CSV to begin."
            )
            self.current_markdown = ""
            self.current_report = None
            self.action_rows = []
            self.user_rows = []
            self.ranking_sort_var = tk.StringVar(value="Score")
            self.ranking_desc_var = tk.BooleanVar(value=True)

            # Widget references for theme updates
            self.weights_canvas = None
            self.users_canvas = None
            self.result_text = None
            self.ranking_tree = None
            self.details_tree = None
            self.info_text_widgets = []

            self._apply_theme()
            self._setup_layout()
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
            self.root.minsize(1000, 700)
            self.root.geometry("1200x800")

            # Initialize with empty states
            self.set_action_rows(*discover_actions_for_gui())
            self.set_user_rows([])

            # Start queue polling
            self._poll_task_queue()

            # Auto-load sample CSV for testing after 2 seconds
            self.root.after(2000, self._auto_load_sample_csv_test)

        def _auto_load_sample_csv_test(self):
            """Automatically load sample CSV for testing."""
            import os
            import sys

            # Handle PyInstaller bundled mode
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(__file__)

            sample_path = os.path.join(base_path, "sample.csv")
            if os.path.exists(sample_path):
                self.csv_path_var.set(sample_path)
                self.browse_csv()  # This will trigger the normal browse_csv flow

        def _poll_task_queue(self):
            """Poll background task queue and execute callbacks on main thread."""
            try:
                while True:
                    callback = self._task_queue.get_nowait()
                    try:
                        callback()
                    except Exception as e:
                        # Show callback exception in status bar for debugging
                        original_status = self.status_var.get()
                        self.status_var.set(f"Callback error: {str(e)}")
                        self.root.after(
                            2000, lambda: self.status_var.set(original_status)
                        )
            except self._queue.Empty:
                pass
            # Schedule next poll
            self.root.after(50, self._poll_task_queue)

        def _run_in_background(self, task_func, on_done, on_error=None):
            """Run a function in a background thread, call on_done/on_error on main thread."""

            def worker():
                try:
                    result = task_func()
                    self._task_queue.put(lambda: on_done(result))
                except Exception as exc:
                    if on_error:
                        self._task_queue.put(lambda: on_error(exc))
                    else:
                        self._task_queue.put(
                            lambda: self._show_error("Background task failed", str(exc))
                        )

            self._bg_thread = self._threading.Thread(target=worker, daemon=True)
            self._bg_thread.start()

        def _show_error(self, title, message):
            from tkinter import messagebox

            messagebox.showerror(title, message)
            self.status_var.set(f"Error: {message}")

        def _set_busy(self, busy):
            """Show/hide busy state (cursor, button states)."""
            if busy:
                self.root.config(cursor="watch")
                # Disable main action buttons
                for widget in [
                    getattr(self, "generate_btn", None),
                    getattr(self, "export_btn", None),
                ]:
                    if widget:
                        widget.config(state="disabled")
            else:
                self.root.config(cursor="")
                for widget in [
                    getattr(self, "generate_btn", None),
                    getattr(self, "export_btn", None),
                ]:
                    if widget:
                        widget.config(state="normal")

        def _setup_fonts(self):
            """Detect and set up proper fonts according to specification."""
            available_families = set(tkfont.families())
            preferred_sans = ["Inter", "Ubuntu", "Segoe UI", "DejaVu Sans"]
            preferred_mono = ["JetBrains Mono", "DejaVu Sans Mono"]

            # Find first available sans font
            sans_font = None
            for font in preferred_sans:
                if font in available_families:
                    sans_font = font
                    break
            if not sans_font:
                sans_font = "sans-serif"  # fallback

            # Find first available mono font
            mono_font = None
            for font in preferred_mono:
                if font in available_families:
                    mono_font = font
                    break
            if not mono_font:
                mono_font = "monospace"  # fallback

            self.sans_font = sans_font
            self.mono_font = mono_font

            # Design tokens for spacing
            self.tokens = _get_design_tokens(self.current_theme.get())
            self.spacing = self.tokens["spacing"]

            # Named fonts for consistent usage across all styles
            # Base size increased from 10pt to 11pt for better readability
            self.fUI = (sans_font, 11)  # Base UI font (Regular 400)
            self.fUIMedium = (sans_font, 11, "normal")  # Medium (500) - simulated
            self.fUISemibold = (sans_font, 11, "bold")  # Semibold (600)
            self.fUIBold = (sans_font, 11, "bold")  # Bold (700)
            self.fSmall = (sans_font, 10)  # Small headers (Use, Action, Weight, etc.)
            self.fSmallBold = (sans_font, 10, "bold")
            self.fMono = (mono_font, 10)  # Monospace for code/markdown
            self.fMonoSmall = (mono_font, 9)
            self.fHeading = (sans_font, 14, "bold")  # Section headings
            self.fDisplay = (sans_font, 20, "bold")  # Large numbers (score badges)
            self.fCaption = (sans_font, 9)  # Captions, helper text

            # Configure default Tk named fonts
            default_font = tkfont.nametofont("TkDefaultFont")
            default_font.configure(family=sans_font, size=11)

            text_font = tkfont.nametofont("TkTextFont")
            text_font.configure(family=sans_font, size=11)

            heading_font = tkfont.nametofont("TkHeadingFont")
            heading_font.configure(family=sans_font, size=14, weight="bold")

            menu_font = tkfont.nametofont("TkMenuFont")
            menu_font.configure(family=sans_font, size=11)

            # Set combobox dropdown list font
            self.root.option_add("*TCombobox*Listbox.font", self.fUI)

        def _get_design_tokens(self):
            """Get design tokens for current theme."""
            return _get_design_tokens(self.current_theme.get())

        def _apply_theme(self):
            """Apply theme to all widgets - called on init and theme change."""
            self.tokens = _get_design_tokens(self.current_theme.get())
            self.spacing = self.tokens["spacing"]
            colors = self.tokens["color"]
            style = ttk.Style(self.root)

            try:
                style.theme_use("clam")
            except self.tk.TclError:
                pass

            # Configure root
            self.root.configure(background=colors["bg_primary"])

            # Configure ttk styles
            self._configure_ttk_styles(style, colors)

            # Configure tk widgets that need manual updates
            self._configure_tk_widgets(colors)

        def _configure_ttk_styles(self, style, colors):
            """Configure all ttk styles for current theme."""
            # Base styles
            style.configure(
                ".",
                background=colors["bg_primary"],
                foreground=colors["text_primary"],
                font=self.fUI,
            )

            # Frames - Elevated card system
            style.configure("TFrame", background=colors["bg_primary"])
            style.configure(
                "Card.TFrame",  # Elevation 1 - default card
                background=colors["bg_secondary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
            )
            style.configure(
                "CardElevated.TFrame",  # Elevation 2 - raised card
                background=colors["bg_tertiary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_emphasis"],
            )
            style.configure(
                "CardModal.TFrame",  # Elevation 3 - modal/dropdown
                background=colors["bg_tertiary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_emphasis"],
            )
            style.configure(
                "Plain.TFrame",
                background=colors["bg_secondary"],
                borderwidth=0,
                relief="flat",
            )
            # Surface.TFrame - alias for Plain.TFrame for any legacy references
            style.configure(
                "Surface.TFrame",
                background=colors["bg_secondary"],
                borderwidth=0,
                relief="flat",
            )

            # Labels
            style.configure(
                "TLabel",
                background=colors["bg_primary"],
                foreground=colors["text_primary"],
                font=self.fUI,
                padding=(0, 4),
            )
            style.configure(
                "Secondary.TLabel",
                background=colors["bg_primary"],
                foreground=colors["text_secondary"],
                font=self.fUI,
                padding=(0, 4),
            )
            style.configure(
                "Muted.TLabel",
                background=colors["bg_primary"],
                foreground=colors["text_muted"],
                font=self.fUI,
                padding=(0, 4),
            )
            style.configure(
                "Card.TLabel",
                background=colors["bg_secondary"],
                foreground=colors["text_primary"],
                font=self.fSmall,
                padding=(0, 4),
            )
            style.configure(
                "Card.Muted.TLabel",
                background=colors["bg_secondary"],
                foreground=colors["text_muted"],
                font=self.fSmall,
                padding=(0, 4),
            )

            # LabelFrames
            style.configure(
                "TLabelframe",
                background=colors["bg_secondary"],
                bordercolor=colors["border_default"],
                borderwidth=0,
                relief="flat",
            )
            style.configure(
                "TLabelframe.Label",
                background=colors["bg_secondary"],
                foreground=colors["accent_primary"],
                font=self.fUIBold,
            )

            # Buttons - padding (16,6) for consistent height
            style.configure(
                "TButton",
                background=colors["bg_secondary"],
                foreground=colors["text_primary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
                focuscolor=colors["accent_primary"],
                padding=(16, 6),
                font=self.fUI,
            )
            style.map(
                "TButton",
                background=[
                    ("active", colors["bg_hover"]),
                    ("pressed", colors["accent_primary"]),
                    ("disabled", colors["bg_secondary"]),
                ],
                foreground=[("disabled", colors["text_muted"])],
            )

            style.configure(
                "Accent.TButton",
                background=colors["accent_primary"],
                foreground=colors["accent_text"],
                borderwidth=1,
                relief="solid",
                focuscolor=colors["accent_primary"],
                padding=(16, 6),
                font=self.fUIBold,
            )
            style.map(
                "Accent.TButton",
                background=[
                    ("active", colors["accent_hover"]),
                    ("pressed", colors["accent_primary"]),
                ],
                foreground=[("pressed", colors["accent_text"])],
            )

            style.configure(
                "Ghost.TButton",
                background=colors["bg_secondary"],
                foreground=colors["text_primary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
                padding=(16, 6),
                font=self.fUI,
            )
            style.map(
                "Ghost.TButton",
                background=[
                    ("active", colors["bg_hover"]),
                    ("pressed", colors["accent_hover"]),
                ],
                foreground=[
                    ("active", colors["text_primary"]),
                    ("pressed", colors["accent_text"]),
                ],
            )

            # Entries - padding (8,6)
            style.configure(
                "TEntry",
                fieldbackground=colors["bg_secondary"],
                foreground=colors["text_primary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
                insertcolor=colors["text_primary"],
                padding=(8, 6),
                font=self.fUI,
            )
            style.map(
                "TEntry",
                bordercolor=[("focus", colors["accent_primary"])],
                fieldbackground=[("focus", colors["bg_secondary"])],
            )

            # Combobox - padding (8,6), dropdown font set via root.option_add
            style.configure(
                "TCombobox",
                fieldbackground=colors["bg_secondary"],
                foreground=colors["text_primary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
                arrowcolor=colors["text_secondary"],
                padding=(8, 6),
                font=self.fUI,
            )
            style.map("TCombobox", bordercolor=[("focus", colors["accent_primary"])])

            # Checkbuttons
            style.configure(
                "TCheckbutton",
                background=colors["bg_primary"],
                foreground=colors["text_primary"],
                indicatorcolor=colors["bg_secondary"],
                indicatorbordercolor=colors["border_default"],
            )
            style.map(
                "TCheckbutton",
                background=[("active", colors["bg_primary"])],
                foreground=[("active", colors["text_primary"])],
                indicatorcolor=[
                    ("selected", colors["accent_primary"]),
                    ("!selected", colors["bg_secondary"]),
                ],
                indicatorbordercolor=[
                    ("selected", colors["accent_primary"]),
                    ("focus", colors["accent_primary"]),
                ],
            )
            style.configure(
                "Card.TCheckbutton",
                background=colors["bg_secondary"],
                foreground=colors["text_primary"],
                indicatorcolor=colors["bg_secondary"],
                indicatorbordercolor=colors["border_default"],
            )
            style.map(
                "Card.TCheckbutton",
                background=[("active", colors["bg_secondary"])],
                foreground=[("active", colors["text_primary"])],
                indicatorcolor=[
                    ("selected", colors["accent_primary"]),
                    ("!selected", colors["bg_secondary"]),
                ],
                indicatorbordercolor=[
                    ("selected", colors["accent_primary"]),
                    ("focus", colors["accent_primary"]),
                ],
            )

            # Action checkboxes - centered in column
            style.configure(
                "Action.TCheckbutton",
                background=colors["bg_secondary"],
                foreground=colors["text_primary"],
                indicatorcolor=colors["bg_secondary"],
                indicatorbordercolor=colors["border_default"],
                padding=[12, 4],
            )
            style.map(
                "Action.TCheckbutton",
                background=[("active", colors["bg_secondary"])],
                foreground=[("active", colors["text_primary"])],
                indicatorcolor=[
                    ("selected", colors["accent_primary"]),
                    ("!selected", colors["bg_secondary"]),
                ],
                indicatorbordercolor=[
                    ("selected", colors["accent_primary"]),
                    ("focus", colors["accent_primary"]),
                ],
            )

            # Notebook (tabs)
            style.configure("TNotebook", background=colors["bg_primary"], borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background=colors["bg_secondary"],
                foreground=colors["text_secondary"],
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
                padding=[20, 10],
            )
            style.map(
                "TNotebook.Tab",
                background=[
                    ("selected", colors["bg_secondary"]),
                    ("active", colors["bg_hover"]),
                ],
                foreground=[
                    ("selected", colors["accent_primary"]),
                    ("active", colors["text_primary"]),
                ],
                bordercolor=[("selected", colors["accent_primary"])],
                padding=[("selected", [25, 12])],
            )

            # Treeview
            style.configure(
                "Treeview",
                background=colors["bg_secondary"],
                fieldbackground=colors["bg_secondary"],
                foreground=colors["text_primary"],
                borderwidth=0,
                rowheight=32,
            )
            style.configure(
                "Treeview.Heading",
                background=colors["bg_secondary"],
                foreground=colors["accent_primary"],
                font=self.fSmallBold,
                borderwidth=1,
                relief="solid",
                bordercolor=colors["border_default"],
            )
            style.map("Treeview.Heading", background=[("active", colors["bg_hover"])])
            style.map(
                "Treeview",
                background=[
                    ("selected", colors["select_bg"]),
                    ("focus", colors["select_bg"]),
                ],
                foreground=[
                    ("selected", colors["select_text"]),
                    ("focus", colors["select_text"]),
                ],
            )

            # Scrollbars
            style.configure(
                "Vertical.TScrollbar",
                background=colors["bg_secondary"],
                troughcolor=colors["bg_primary"],
                bordercolor=colors["border_default"],
                arrowcolor=colors["text_secondary"],
                width=8,
            )
            style.map(
                "Vertical.TScrollbar",
                background=[
                    ("active", colors["accent_hover"]),
                    ("pressed", colors["accent_primary"]),
                ],
            )

            style.configure(
                "Horizontal.TScrollbar",
                background=colors["bg_secondary"],
                troughcolor=colors["bg_primary"],
                bordercolor=colors["border_default"],
                arrowcolor=colors["text_secondary"],
                height=8,
            )
            style.map(
                "Horizontal.TScrollbar",
                background=[
                    ("active", colors["accent_hover"]),
                    ("pressed", colors["accent_primary"]),
                ],
            )

            # Progressbar
            style.configure(
                "TProgressbar",
                background=colors["accent_primary"],
                troughcolor=colors["bg_secondary"],
                borderwidth=0,
                thickness=4,
            )

            # Separator
            style.configure("TSeparator", background=colors["border_default"])

        def _configure_tk_widgets(self, colors):
            """Configure tk widgets (Canvas, ScrolledText) that need manual updates."""
            # Update canvas backgrounds
            if self.weights_canvas:
                self.weights_canvas.configure(
                    background=colors["bg_secondary"], highlightthickness=0
                )
            if self.users_canvas:
                self.users_canvas.configure(
                    background=colors["bg_secondary"], highlightthickness=0
                )

            # Update ScrolledText widgets
            if self.result_text:
                self.result_text.configure(
                    background=colors["bg_secondary"],
                    foreground=colors["text_primary"],
                    insertbackground=colors["accent_primary"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_text"],
                    borderwidth=0,
                    highlightthickness=0,
                    font=self.fMono,
                )

            # Update info tab text widgets
            for text_widget in getattr(self, "info_text_widgets", []):
                text_widget.configure(
                    background=colors["bg_secondary"],
                    foreground=colors["text_primary"],
                    insertbackground=colors["accent_primary"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_text"],
                    borderwidth=0,
                    highlightthickness=0,
                    font=self.fMono,
                )

            # Update treeview tags for existing trees
            for tree in [self.ranking_tree, self.details_tree]:
                if tree:
                    tree.tag_configure("oddrow", background=colors["bg_secondary"])
                    tree.tag_configure("evenrow", background=colors["zebra_subtle"])

        def _create_theme_toggle(self, parent):
            """Create a compact theme toggle button."""
            colors = self.tokens["color"]

            # Use a styled button that shows current theme
            btn = ttk.Button(
                parent,
                text="🌙 Dark" if self.current_theme.get() == "dark" else "☀️ Light",
                style="Ghost.TButton",
                command=lambda: self._toggle_theme(btn),
            )
            return btn

        def _toggle_theme(self, btn):
            """Toggle theme and update button text."""
            new_theme = "dark" if self.current_theme.get() == "light" else "light"
            self.current_theme.set(new_theme)
            btn.configure(text="🌙 Dark" if new_theme == "dark" else "☀️ Light")
            self._apply_theme()

        def _setup_layout(self):
            """Set up the complete GUI layout according to specification."""
            # Main container with padding - using spacing tokens
            main_frame = ttk.Frame(self.root)
            main_frame.grid(
                row=0,
                column=0,
                sticky="nsew",
                padx=self.spacing["lg"],
                pady=self.spacing["lg"],
            )
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(2, weight=1)  # Results row expands

            # Helper to compute minsize for a column based on font
            def measure_text(text, font_tuple):
                import tkinter.font as tkfont

                f = tkfont.Font(font=font_tuple)
                return f.measure(text) + self.spacing["md"]  # 16px padding

            # Pre-compute column minsizes for weights panel (shared by header and data rows)
            # We'll use fSmall for header labels, fUI for data
            # We compute minsizes dynamically when data is loaded, but set a minimum base
            self._weights_col0_minsize = 48  # checkbox column
            self._weights_col1_minsize = measure_text("Action", self.fSmall)
            self._weights_col2_minsize = measure_text("Weight", self.fSmall)

            # File selection frame (Input card) - OUTER CARD (Elevated)
            file_frame = ttk.Frame(main_frame, style="CardElevated.TFrame")
            file_frame.grid(row=0, column=0, sticky="ew", pady=(0, self.spacing["lg"]))
            file_frame.columnconfigure(1, weight=1)

            # Row 0: CSV selection
            ttk.Label(file_frame, text="Action log CSV", style="Card.TLabel").grid(
                row=0,
                column=0,
                sticky="w",
                padx=(self.spacing["md"], self.spacing["md"]),
                pady=(self.spacing["md"], self.spacing["xs"]),
            )
            csv_entry = ttk.Entry(file_frame, textvariable=self.csv_path_var)
            csv_entry.grid(
                row=0,
                column=1,
                sticky="ew",
                padx=(self.spacing["md"], self.spacing["md"]),
                pady=(self.spacing["md"], self.spacing["xs"]),
            )
            ttk.Button(
                file_frame,
                text="Browse...",
                command=self.browse_csv,
                style="Ghost.TButton",
            ).grid(
                row=0,
                column=2,
                sticky="w",
                padx=(self.spacing["md"], self.spacing["md"]),
                pady=(self.spacing["md"], self.spacing["xs"]),
            )

            # Row 1: Threshold and theme - INNER FRAME (Plain.TFrame)
            threshold_frame = ttk.Frame(file_frame, style="Plain.TFrame")
            threshold_frame.grid(
                row=1,
                column=0,
                columnspan=3,
                sticky="ew",
                padx=(
                    self.spacing["md"],
                    self.spacing["md"],
                ),  # Keep inside card borders
                pady=(self.spacing["xs"], self.spacing["md"]),
            )
            threshold_frame.columnconfigure(0, weight=1)  # Allow label column to expand
            threshold_frame.columnconfigure(1, weight=0)
            threshold_frame.columnconfigure(2, weight=0)
            threshold_frame.columnconfigure(3, weight=0)

            ttk.Label(
                threshold_frame,
                text="Skip threshold minutes",
                style="Card.Muted.TLabel",
            ).grid(
                row=0,
                column=0,
                sticky="e",
                padx=(self.spacing["md"], self.spacing["md"]),
            )
            ttk.Entry(threshold_frame, textvariable=self.threshold_var, width=8).grid(
                row=0, column=1, sticky="w", padx=(0, self.spacing["lg"])
            )

            # Theme toggle switch (replaces combobox)
            ttk.Label(threshold_frame, text="Theme", style="Card.Muted.TLabel").grid(
                row=0, column=2, sticky="w", padx=(self.spacing["md"], 0)
            )
            self._create_theme_toggle(threshold_frame).grid(
                row=0, column=3, sticky="w", padx=(0, self.spacing["md"])
            )

            # Options frame with two equal cards - using elevated cards
            options_frame = ttk.Frame(main_frame)
            options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
            options_frame.columnconfigure(0, weight=1, uniform="option_panels")
            options_frame.columnconfigure(1, weight=1, uniform="option_panels")

            # Action Weights card - OUTER CARD
            weights_card = ttk.Frame(options_frame, style="Card.TFrame")
            weights_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            weights_card.columnconfigure(0, weight=1)
            weights_card.rowconfigure(1, weight=1)

            # Weights header - INNER FRAME (Plain.TFrame)
            weights_header = ttk.Frame(weights_card, style="Plain.TFrame")
            weights_header.grid(row=0, column=0, sticky="ew", pady=(16, 8), padx=16)
            weights_header.columnconfigure(0, minsize=self._weights_col0_minsize)
            weights_header.columnconfigure(
                1, weight=1, minsize=self._weights_col1_minsize
            )
            weights_header.columnconfigure(2, minsize=self._weights_col2_minsize)

            ttk.Label(weights_header, text="Use", style="Card.Muted.TLabel").grid(
                row=0, column=0, sticky="w", padx=(12, 0)
            )
            ttk.Label(weights_header, text="Action", style="Card.TLabel").grid(
                row=0, column=1, sticky="w", padx=(12, 12)
            )
            ttk.Label(weights_header, text="Weight", style="Card.Muted.TLabel").grid(
                row=0, column=2, sticky="w", padx=(0, 12)
            )

            # Weights canvas frame - INNER FRAME (Plain.TFrame)
            weights_canvas_frame = ttk.Frame(weights_card, style="Plain.TFrame")
            weights_canvas_frame.grid(
                row=1,
                column=0,
                sticky="nsew",
                padx=self.spacing["lg"],
                pady=(0, self.spacing["lg"]),
            )
            weights_canvas_frame.columnconfigure(0, weight=1)
            weights_canvas_frame.rowconfigure(0, weight=1)

            colors = self.tokens["color"]
            self.weights_canvas = tk.Canvas(
                weights_canvas_frame,
                highlightthickness=0,
                background=colors["bg_secondary"],
            )
            self.weights_scrollbar = ttk.Scrollbar(
                weights_canvas_frame,
                orient="vertical",
                command=self.weights_canvas.yview,
            )
            self.weights_frame = ttk.Frame(self.weights_canvas, style="Plain.TFrame")
            self.weights_window = self.weights_canvas.create_window(
                (0, 0), window=self.weights_frame, anchor="nw"
            )
            self.weights_canvas.configure(yscrollcommand=self.weights_scrollbar.set)

            self.weights_canvas.grid(row=0, column=0, sticky="nsew")
            self.weights_scrollbar.grid(row=0, column=1, sticky="ns")

            self.weights_frame.bind("<Configure>", self._sync_weights_scroll)
            self.weights_canvas.bind("<Configure>", self._sync_weights_width)

            # Apply column minsizes to data rows frame too
            self.weights_frame.columnconfigure(0, minsize=self._weights_col0_minsize)
            self.weights_frame.columnconfigure(
                1, weight=1, minsize=self._weights_col1_minsize
            )
            self.weights_frame.columnconfigure(2, minsize=self._weights_col2_minsize)

            # Users card - OUTER CARD
            users_card = ttk.Frame(options_frame, style="Card.TFrame")
            users_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            users_card.columnconfigure(0, weight=1)
            users_card.rowconfigure(1, weight=1)

            # Users toolbar - INNER FRAME (Plain.TFrame)
            users_toolbar = ttk.Frame(users_card, style="Plain.TFrame")
            users_toolbar.grid(row=0, column=0, sticky="ew", pady=(16, 8), padx=16)
            users_toolbar.columnconfigure(0, weight=0)
            users_toolbar.columnconfigure(1, weight=0)
            users_toolbar.columnconfigure(2, weight=1)

            ttk.Button(
                users_toolbar,
                text="Select All",
                command=lambda: self.set_user_selection(True),
                style="Ghost.TButton",
            ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
            ttk.Button(
                users_toolbar,
                text="Clear",
                command=lambda: self.set_user_selection(False),
                style="Ghost.TButton",
            ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
            ttk.Label(
                users_toolbar,
                text="Included in calculations",
                style="Card.Muted.TLabel",
            ).grid(row=0, column=2, sticky="e")

            # Users canvas frame - INNER FRAME (Plain.TFrame)
            users_canvas_frame = ttk.Frame(users_card, style="Plain.TFrame")
            users_canvas_frame.grid(
                row=1,
                column=0,
                sticky="nsew",
                padx=self.spacing["lg"],
                pady=(0, self.spacing["lg"]),
            )
            users_canvas_frame.columnconfigure(0, weight=1)
            users_canvas_frame.rowconfigure(0, weight=1)

            colors = self.tokens["color"]
            self.users_canvas = tk.Canvas(
                users_canvas_frame,
                highlightthickness=0,
                background=colors["bg_secondary"],
            )
            self.users_scrollbar = ttk.Scrollbar(
                users_canvas_frame, orient="vertical", command=self.users_canvas.yview
            )
            self.users_frame = ttk.Frame(self.users_canvas, style="Plain.TFrame")
            self.users_window = self.users_canvas.create_window(
                (0, 0), window=self.users_frame, anchor="nw"
            )
            self.users_canvas.configure(yscrollcommand=self.users_scrollbar.set)

            self.users_canvas.grid(row=0, column=0, sticky="nsew")
            self.users_scrollbar.grid(row=0, column=1, sticky="ns")

            self.users_frame.bind("<Configure>", self._sync_users_scroll)
            self.users_canvas.bind("<Configure>", self._sync_users_width)

            # Make users_frame expand to fill canvas (no grey areas)
            self.users_frame.columnconfigure(0, weight=1)

            # Results card - OUTER CARD
            results_card = ttk.Frame(main_frame, style="Card.TFrame")
            results_card.grid(row=2, column=0, sticky="nsew", pady=(0, 16))
            results_card.columnconfigure(0, weight=1)
            results_card.rowconfigure(0, weight=1)

            # Notebook for tabs
            self.result_tabs = ttk.Notebook(results_card)
            self.result_tabs.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

            # Compute sort combobox width from longest option
            sort_labels = [label for _key, label, _default_desc in RANKING_SORT_OPTIONS]
            max_label_len = max(len(label) for label in sort_labels)
            sort_combo_width = max_label_len + 2

            # Ranking tab - Plain.TFrame (tabs are inner to notebook)
            ranking_tab = ttk.Frame(self.result_tabs, style="Plain.TFrame")
            ranking_tab.columnconfigure(0, weight=1)
            ranking_tab.rowconfigure(1, weight=1)

            # Ranking controls - INNER FRAME (Plain.TFrame)
            ranking_controls = ttk.Frame(ranking_tab, style="Plain.TFrame")
            ranking_controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            ranking_controls.columnconfigure(0, weight=0)
            ranking_controls.columnconfigure(1, weight=0)
            ranking_controls.columnconfigure(2, weight=0)
            ranking_controls.columnconfigure(3, weight=1)

            ttk.Label(ranking_controls, text="Sort by", style="Card.TLabel").grid(
                row=0, column=0, sticky="w", padx=(0, 8)
            )
            sort_combo = ttk.Combobox(
                ranking_controls,
                textvariable=self.ranking_sort_var,
                values=sort_labels,
                state="readonly",
                width=sort_combo_width,
            )
            sort_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
            sort_combo.bind("<<ComboboxSelected>>", self._on_ranking_sort_changed)

            ttk.Checkbutton(
                ranking_controls,
                text="Descending",
                variable=self.ranking_desc_var,
                command=self.apply_ranking_sort,
                style="Card.TCheckbutton",
            ).grid(row=0, column=2, sticky="w", padx=(0, 8))
            ttk.Button(
                ranking_controls, text="Apply", command=self.apply_ranking_sort
            ).grid(row=0, column=3, sticky="w")

            # Ranking treeview - inner wrapper (Card.TFrame with 8px padding per spec)
            tree_frame = ttk.Frame(ranking_tab, style="Card.TFrame")
            tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
            tree_frame.columnconfigure(0, weight=1)
            tree_frame.rowconfigure(0, weight=1)

            self.ranking_tree = self._create_tree_tab(
                tree_frame,
                (
                    ("rank", "Rank", 64, "center"),
                    ("user", "User", 180, "w"),
                    ("total", "Total Actions", 110, "e"),
                    ("weighted_total", "Weighted Total", 120, "e"),
                    ("days", "Active Days", 100, "e"),
                    ("weighted_daily", "Weighted Daily Volume", 150, "e"),
                    ("volume_delta", "Volume Delta", 110, "e"),
                    ("speed_delta", "Speed Delta", 110, "e"),
                    ("avg_duration", "Avg Duration", 110, "e"),
                    ("score", "Score", 90, "e"),
                ),
            )

            y_scrollbar_ranking = ttk.Scrollbar(
                tree_frame, orient="vertical", command=self.ranking_tree.yview
            )
            x_scrollbar_ranking = ttk.Scrollbar(
                tree_frame, orient="horizontal", command=self.ranking_tree.xview
            )
            self.ranking_tree.configure(
                yscrollcommand=y_scrollbar_ranking.set,
                xscrollcommand=x_scrollbar_ranking.set,
            )
            self.ranking_tree.grid(row=0, column=0, sticky="nsew")
            y_scrollbar_ranking.grid(row=0, column=1, sticky="ns")
            x_scrollbar_ranking.grid(row=1, column=0, sticky="ew")

            self.result_tabs.add(ranking_tab, text="Ranking")

            # Details tab - Plain.TFrame (tabs are inner to notebook)
            details_tab = ttk.Frame(self.result_tabs, style="Plain.TFrame")
            details_tab.columnconfigure(0, weight=1)
            details_tab.rowconfigure(0, weight=1)

            # Treeview wrapper (Card.TFrame with 8px padding per spec)
            tree_frame_details = ttk.Frame(details_tab, style="Card.TFrame")
            tree_frame_details.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
            tree_frame_details.columnconfigure(0, weight=1)
            tree_frame_details.rowconfigure(0, weight=1)

            self.details_tree = self._create_tree_tab(
                tree_frame_details,
                (
                    ("user", "User", 180, "w"),
                    ("action", "Action", 220, "w"),
                    ("total", "Total", 90, "e"),
                    ("avg_daily", "Avg Daily", 100, "e"),
                    ("volume_delta", "Volume Delta", 110, "e"),
                    ("avg_duration", "Avg Duration", 110, "e"),
                    ("duration_delta", "Duration Delta", 120, "e"),
                    ("samples", "Samples", 90, "e"),
                ),
            )

            y_scrollbar_details = ttk.Scrollbar(
                tree_frame_details, orient="vertical", command=self.details_tree.yview
            )
            x_scrollbar_details = ttk.Scrollbar(
                tree_frame_details, orient="horizontal", command=self.details_tree.xview
            )
            self.details_tree.configure(
                yscrollcommand=y_scrollbar_details.set,
                xscrollcommand=x_scrollbar_details.set,
            )
            self.details_tree.grid(row=0, column=0, sticky="nsew")
            y_scrollbar_details.grid(row=0, column=1, sticky="ns")
            x_scrollbar_details.grid(row=1, column=0, sticky="ew")

            self.result_tabs.add(details_tab, text="Action Details")

            # Markdown tab - Plain.TFrame
            markdown_tab = ttk.Frame(self.result_tabs, style="Plain.TFrame")
            markdown_tab.columnconfigure(0, weight=1)
            markdown_tab.rowconfigure(0, weight=1)

            self.result_text = scrolledtext.ScrolledText(
                markdown_tab,
                wrap="word",
                undo=True,
                borderwidth=0,
                highlightthickness=0,
            )
            self.result_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

            self.result_tabs.add(markdown_tab, text="Markdown")

            # Info tab
            self._create_info_tab(self.result_tabs)

            # Bottom bar (not a card)
            bottom_frame = ttk.Frame(main_frame)
            bottom_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
            bottom_frame.columnconfigure(2, weight=1)

            self.generate_btn = ttk.Button(
                bottom_frame,
                text="Generate Report",
                command=self.generate_report,
                style="Accent.TButton",
            )
            self.generate_btn.grid(row=0, column=0, sticky="w", padx=(0, 12))
            self.export_btn = ttk.Button(
                bottom_frame,
                text="Export MD",
                command=self.export_markdown,
                style="Ghost.TButton",
            )
            self.export_btn.grid(row=0, column=1, sticky="w")
            ttk.Label(
                bottom_frame, textvariable=self.status_var, style="Secondary.TLabel"
            ).grid(row=0, column=2, sticky="w")

        def _create_tree_tab(self, parent, columns):
            """Create a generic treeview."""
            from tkinter import ttk

            tree = ttk.Treeview(
                parent, columns=[column[0] for column in columns], show="headings"
            )

            for column_id, label, width, anchor in columns:
                tree.heading(column_id, text=label)
                tree.column(
                    column_id, width=width, minwidth=60, anchor=anchor, stretch=True
                )

            self._configure_tree_tags(tree)

            return tree

        def _create_info_tab(self, notebook):
            """Create info tab."""
            from tkinter import scrolledtext, ttk

            info_tab = ttk.Frame(notebook, style="Plain.TFrame")
            info_tab.columnconfigure(0, weight=1)
            info_tab.rowconfigure(0, weight=1)

            info_text = scrolledtext.ScrolledText(
                info_tab, wrap="word", borderwidth=0, highlightthickness=0
            )
            info_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            info_text.insert("1.0", _build_gui_info_text())
            info_text.configure(state="disabled")

            # Store reference for theme updates
            if not hasattr(self, "info_text_widgets"):
                self.info_text_widgets = []
            self.info_text_widgets.append(info_text)

            notebook.add(info_tab, text="Info")

        def _configure_tree_tags(self, tree):
            """Configure treeview tags for alternating row colors."""
            colors = self.tokens["color"]
            tree.tag_configure("oddrow", background=colors["bg_secondary"])
            tree.tag_configure("evenrow", background=colors["zebra_subtle"])
            # Score badge tags
            tree.tag_configure("score_excellent", foreground=colors["success"])
            tree.tag_configure("score_good", foreground=colors["warning"])
            tree.tag_configure("score_poor", foreground=colors["error"])
            tree.tag_configure("score_neutral", foreground=colors["text_secondary"])
            # Delta tags
            tree.tag_configure("delta_positive", foreground=colors["success"])
            tree.tag_configure("delta_negative", foreground=colors["error"])
            tree.tag_configure("delta_neutral", foreground=colors["text_secondary"])

        def _sync_weights_scroll(self, _event=None):
            self.weights_canvas.configure(scrollregion=self.weights_canvas.bbox("all"))

        def _sync_weights_width(self, event):
            self.weights_canvas.itemconfigure(self.weights_window, width=event.width)

        def _sync_users_scroll(self, _event=None):
            self.users_canvas.configure(scrollregion=self.users_canvas.bbox("all"))

        def _sync_users_width(self, event):
            self.users_canvas.itemconfigure(self.users_window, width=event.width)

        def _populate_treeview(self, tree, data, columns):
            """Populate a treeview with data."""
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            # Insert data with alternating row colors
            for i, row in enumerate(data):
                values = [row.get(col[0], "") for col in columns]
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                tree.insert("", "end", values=values, tags=(tag,))

        def browse_csv(self):
            from tkinter import filedialog

            path = filedialog.askopenfilename(
                title="Select user action log CSV",
                filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            )
            if not path:
                return
            self.csv_path_var.set(path)
            self.status_var.set("Loading CSV...")
            self._set_busy(True)

            def load_csv():
                try:
                    actions, weights = discover_actions_for_gui(path)
                    users = discover_users_for_gui(path)
                    result = (actions, weights, users)
                    return result
                except Exception as e:
                    raise

            def on_done(result):
                actions, weights, users = result
                self.set_action_rows(actions, weights)
                self.set_user_rows(users)
                self.status_var.set(
                    f"Loaded {len(actions)} actions and {len(users)} users from CSV/defaults."
                )
                self._set_busy(False)

            def on_error(exc):
                from tkinter import messagebox

                messagebox.showerror("CSV error", str(exc))
                self.status_var.set("Could not read selected CSV.")
                self._set_busy(False)

            self._run_in_background(load_csv, on_done, on_error)

        def set_action_rows(self, actions, weights):
            from tkinter import ttk

            for child in self.weights_frame.winfo_children():
                child.destroy()
            self.action_rows = []
            # Use shared minsizes from layout
            self.weights_frame.columnconfigure(0, minsize=self._weights_col0_minsize)
            self.weights_frame.columnconfigure(
                1, weight=1, minsize=self._weights_col1_minsize
            )
            self.weights_frame.columnconfigure(2, minsize=self._weights_col2_minsize)

            for row_idx, action in enumerate(actions):
                enabled_var = self.tk.BooleanVar(value=True)
                weight_var = self.tk.StringVar(
                    value=f"{float(weights.get(action, 1.0)):g}"
                )

                ttk.Checkbutton(
                    self.weights_frame,
                    variable=enabled_var,
                    style="Action.TCheckbutton",
                ).grid(row=row_idx, column=0, pady=4)
                ttk.Label(self.weights_frame, text=action).grid(
                    row=row_idx, column=1, sticky="ew", padx=(8, 8), pady=4
                )
                ttk.Entry(self.weights_frame, textvariable=weight_var, width=12).grid(
                    row=row_idx, column=2, sticky="w", pady=4, padx=(0, 8)
                )

                self.action_rows.append((action, enabled_var, weight_var))

        def set_user_rows(self, users):
            from tkinter import ttk

            for child in self.users_frame.winfo_children():
                child.destroy()
            self.user_rows = []
            self.users_frame.columnconfigure(0, weight=1)

            if not users:
                ttk.Label(
                    self.users_frame,
                    text="Select a CSV to load users.",
                    style="Card.Muted.TLabel",
                    padding=(8, 8),
                    anchor="center",
                ).grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
                return

            for row_idx, username in enumerate(users):
                enabled_var = self.tk.BooleanVar(value=True)
                ttk.Checkbutton(
                    self.users_frame,
                    text=username,
                    variable=enabled_var,
                ).grid(row=row_idx, column=0, sticky="ew", pady=4, padx=8)
                self.user_rows.append((username, enabled_var))

        def set_user_selection(self, selected):
            for _username, enabled_var in self.user_rows:
                enabled_var.set(bool(selected))

        def collect_options(self):
            csv_text = self.csv_path_var.get().strip()
            if not csv_text:
                raise ValueError("Please select a user action log CSV.")
            csv_path = Path(csv_text)
            if not csv_path.exists():
                raise ValueError("Selected CSV file does not exist.")

            try:
                threshold = float(self.threshold_var.get())
            except ValueError as exc:
                raise ValueError("Skip threshold must be a number.") from exc
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError("Skip threshold must be greater than zero.")

            selected_actions = []
            weights = {}
            for action, enabled_var, weight_var in self.action_rows:
                if not enabled_var.get():
                    continue
                try:
                    weight = float(weight_var.get())
                except ValueError as exc:
                    raise ValueError(
                        f"Weight for {action!r} must be a number."
                    ) from exc
                if not math.isfinite(weight) or weight < 0:
                    raise ValueError(
                        f"Weight for {action!r} must be a non-negative finite number."
                    )
                selected_actions.append(action)
                weights[action] = weight
            if not selected_actions:
                raise ValueError("Select at least one action.")

            selected_users = None
            if self.user_rows:
                selected_users = [
                    username
                    for username, enabled_var in self.user_rows
                    if enabled_var.get()
                ]
                if not selected_users:
                    raise ValueError("Select at least one user.")
            return csv_path, threshold, selected_actions, weights, selected_users

        def generate_report(self):
            self._set_busy(True)
            self.status_var.set("Generating report...")

            def do_generate():
                csv_path, threshold, selected_actions, weights, selected_users = (
                    self.collect_options()
                )
                report = build_user_productivity_report(
                    csv_path,
                    threshold_minutes=threshold,
                    selected_actions=selected_actions,
                    action_weights=weights,
                    selected_users=selected_users,
                )
                markdown = render_user_productivity_md(
                    report, input_source=str(csv_path)
                )
                return report, markdown

            def on_done(result):
                report, markdown = result
                self.current_report = report
                self.current_markdown = markdown
                self.render_result_views(report)
                medians = _report_numeric_medians(report)
                median_score = medians.get("score")
                score_text = (
                    f"{median_score:.1f}" if median_score is not None else "n/a"
                )
                self.status_var.set(f"Report generated. Median score: {score_text}.")
                self._set_busy(False)

            def on_error(exc):
                from tkinter import messagebox

                messagebox.showerror("Report error", str(exc))
                self.status_var.set("Report generation failed.")
                self._set_busy(False)

            self._run_in_background(do_generate, on_done, on_error)

        def render_result_views(self, report):
            medians = _report_numeric_medians(report)
            self._populate_ranking_tree(report, medians)

            # Populate details tree
            details_data = []
            for row in sorted(
                report.get("matrix", []),
                key=lambda item: (
                    item.get("display_name") or item.get("username", "")
                ).lower(),
            ):
                username = row.get("display_name") or row.get("username", "")
                for action in report.get("actions", []):
                    total = row.get("total_volume_cells", {}).get(action, "")
                    if str(total).strip() in ("", "0"):
                        continue
                    details_data.append(
                        {
                            "user": username,
                            "action": action,
                            "total": total,
                            "avg_daily": row.get("volume_cells", {}).get(action, ""),
                            "volume_delta": row.get("volume_deltas", {}).get(
                                action, ""
                            ),
                            "avg_duration": row.get("cells", {}).get(action, ""),
                            "duration_delta": row.get("deltas", {}).get(action, ""),
                            "samples": row.get("counts", {}).get(action, ""),
                        }
                    )
            self._populate_treeview(
                self.details_tree,
                details_data,
                [
                    ("user", "User", 180, "w"),
                    ("action", "Action", 220, "w"),
                    ("total", "Total", 90, "e"),
                    ("avg_daily", "Avg Daily", 100, "e"),
                    ("volume_delta", "Volume Delta", 110, "e"),
                    ("avg_duration", "Avg Duration", 110, "e"),
                    ("duration_delta", "Duration Delta", 120, "e"),
                    ("samples", "Samples", 90, "e"),
                ],
            )

            self.result_text.delete("1.0", self.tk.END)
            self.result_text.insert("1.0", self.current_markdown)

        def _populate_ranking_tree(self, report, medians):
            """Populate the ranking treeview."""
            # Clear existing items
            for item in self.ranking_tree.get_children():
                self.ranking_tree.delete(item)

            # Get sorted rows
            rows = _sort_ranking_rows(
                report.get("ranking", []),
                self._selected_ranking_metric(),
                descending=self.ranking_desc_var.get(),
            )

            # Insert data
            for i, row in enumerate(rows):
                values = (
                    row.get("rank", ""),
                    row.get("display_name") or row.get("username", ""),
                    row.get("total_volume", ""),
                    row.get("weighted_total_volume_display", ""),
                    row.get("active_days", ""),
                    row.get("weighted_avg_daily_volume_display", ""),
                    row.get("volume_delta", ""),
                    row.get("speed_delta", ""),
                    row.get("avg_duration", ""),
                    row.get("score_display", ""),
                )
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                self.ranking_tree.insert("", "end", values=values, tags=(tag,))

        def _clear_tree(self, tree):
            for item in tree.get_children(""):
                tree.delete(item)

        def export_markdown(self):
            from tkinter import filedialog, messagebox

            if not self.current_markdown:
                self.generate_report()
                if not self.current_markdown:
                    return
            output_path = filedialog.asksaveasfilename(
                title="Export Markdown report",
                defaultextension=".md",
                filetypes=(("Markdown files", "*.md"), ("All files", "*.*")),
            )
            if not output_path:
                return
            try:
                Path(output_path).write_text(self.current_markdown, encoding="utf-8")
            except Exception as exc:
                messagebox.showerror("Export error", str(exc))
                self.status_var.set("Export failed.")
                return
            self.status_var.set(f"Exported {output_path}.")

        def _selected_ranking_metric(self):
            return RANKING_SORT_LABELS.get(self.ranking_sort_var.get(), "score")

        def _on_ranking_sort_changed(self, _event=None):
            metric = self._selected_ranking_metric()
            self.ranking_desc_var.set(RANKING_SORT_DEFAULT_DESC.get(metric, True))
            self.apply_ranking_sort()

        def apply_ranking_sort(self):
            if not self.current_report:
                return
            medians = _report_numeric_medians(self.current_report)
            self._populate_ranking_tree(self.current_report, medians)

    # Expose the class for testing
    globals()["UserProductivityApp"] = UserProductivityApp

    # Store instance for testing access
    globals()["_UserProductivityApp_instance"] = None

    def _build_gui_info_text():
        return """User Productivity Tool Logic

    CSV input
    - The tool reads a user action log CSV with columns for day, hour/time, username, and action.
    - Comma, semicolon, tab, and pipe-delimited files are detected automatically.
    - Day values can be DD.MM.YYYY or YYYY-MM-DD. Time values should be HH:MM:SS or HH:MM.
    - Rows for username "system" are skipped before any calculation.

    Row cleanup
    - Rows without a username, action, or parseable timestamp are ignored.
    - Exact duplicate events are deduplicated by day, time, username, and action.
    - Events are sorted by user, timestamp, and action before timing is calculated.

    Time and threshold logic
    - Processing time for an action is inferred from the gap between a user's previous event and current event on the same day.
    - Gaps less than or equal to zero are skipped.
    - Gaps above the skip threshold are treated as idle/out-of-scope time and skipped.
    - The default threshold is 5 minutes.

    Actions and weights
    - The action list starts with the default productivity actions and adds actions found in the CSV.
    - Checked actions are included in the report.
    - Each action weight changes how strongly that action contributes to weighted totals and productivity score.
    - Unknown/custom actions default to weight 1.0.

    Users
    - The Users panel lists non-system users found in the selected CSV.
    - Checked users are included in calculations, ranking, reference values, and Markdown export.
    - Clearing a user removes their rows before report metrics are calculated.

    Reference values
    - Average duration per action is calculated from valid timing gaps across all included users.
    - Average daily volume per action is calculated across users and active days.
    - These reference values become the baseline for comparing each user.

    Score calculation
    - Volume factor compares a user's weighted average daily volume against the reference weighted average daily volume.
    - Speed factor compares reference duration against the user's duration for actions where timing samples exist.
    - Score = volume factor x speed factor x 100.
    - A score around 100 means near the group baseline. Higher scores indicate stronger weighted volume and/or faster action pace.

    Tables and colors
    - Ranking shows user-level totals, weighted volume, speed, and score.
    - Action Details shows per-user action volume and duration breakdowns.
    - Green rows are above the median for the table's main comparison metric.
    - Red rows are below the median.
    - Neutral rows are at the median or have too little numeric data to classify.

    Sorting
    - Click any table header to sort that table.
    - Use the Ranking Sort controls to sort users by score, actions, weighted totals, volume, speed, duration, or user name.
    - Avg Duration defaults to ascending because lower duration is better.

    Export
    - Export MD saves the full Markdown report using the currently generated results.
    - The Markdown export is intentionally calculation-focused and does not include GUI colors."""

    root = tk.Tk()
    globals()["_UserProductivityApp_instance"] = UserProductivityApp(root)
    root.mainloop()
    return 0


# ===== RANKING SORT CONFIG =====

RANKING_SORT_OPTIONS = [
    ("score", "Score", True),
    ("total_actions", "Total Actions", True),
    ("weighted_total", "Weighted Total", True),
    ("active_days", "Active Days", True),
    ("weighted_daily", "Weighted Daily Volume", True),
    ("volume_delta", "Volume Delta", True),
    ("speed_delta", "Speed Delta", True),
    ("avg_duration", "Avg Duration", False),
    ("user", "User", False),
]
RANKING_SORT_LABELS = {label: key for key, label, _default_desc in RANKING_SORT_OPTIONS}
RANKING_SORT_DEFAULT_DESC = {
    key: default_desc for key, _label, default_desc in RANKING_SORT_OPTIONS
}


# Expose UserProductivityApp for testing (defined inside run_gui)
# This will be set when run_gui() is called
UserProductivityApp = None


# ===== HELPER FUNCTIONS FOR GUI =====


def _report_numeric_medians(report):
    ranking = report.get("ranking", [])
    return {
        "score": _median_numeric(row.get("score") for row in ranking),
        "weighted_daily": _median_numeric(
            row.get("weighted_avg_daily_volume") for row in ranking
        ),
        "weighted_total": _median_numeric(
            row.get("weighted_total_volume") for row in ranking
        ),
        "detail_volume": _median_numeric(
            count
            for row in report.get("matrix", [])
            for count in row.get("total_volume_cells", {}).values()
            if _coerce_float(count) is not None
        ),
    }


def _median_numeric(values):
    numbers = sorted(
        number
        for number in (_coerce_float(value) for value in values)
        if number is not None
    )
    if not numbers:
        return None
    midpoint = len(numbers) // 2
    if len(numbers) % 2:
        return numbers[midpoint]
    return (numbers[midpoint - 1] + numbers[midpoint]) / 2.0


def _coerce_float(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _value_result_tag(value, median, lower_is_better=False):
    value = _coerce_float(value)
    median = _coerce_float(median)
    if value is None or median is None:
        return "neutral"
    if value == median:
        return "near_median"
    is_better = value < median if lower_is_better else value > median
    return "above_median" if is_better else "below_median"


def _parse_gui_duration_seconds(value):
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60.0 + seconds
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600.0 + minutes * 60.0 + seconds
    except ValueError:
        return None
    return None


def _ranking_metric_value(row, metric):
    if metric == "score":
        return _coerce_float(row.get("score"))
    if metric == "total_actions":
        return _coerce_float(row.get("total_volume"))
    if metric == "weighted_total":
        return _coerce_float(row.get("weighted_total_volume"))
    if metric == "active_days":
        return _coerce_float(row.get("active_days"))
    if metric == "weighted_daily":
        return _coerce_float(row.get("weighted_avg_daily_volume"))
    if metric == "volume_delta":
        volume_factor = _coerce_float(row.get("volume_factor"))
        return None if volume_factor is None else (volume_factor - 1.0) * 100.0
    if metric == "speed_delta":
        speed_factor = _coerce_float(row.get("speed_factor"))
        return None if speed_factor is None else (speed_factor - 1.0) * 100.0
    if metric == "avg_duration":
        return _parse_gui_duration_seconds(row.get("avg_duration"))
    if metric == "user":
        return str(row.get("display_name") or row.get("username") or "").lower()
    return _coerce_float(row.get("score"))


def _sort_ranking_rows(rows, metric, descending=True):
    metric = metric if metric in RANKING_SORT_DEFAULT_DESC else "score"

    def sort_key(row):
        value = _ranking_metric_value(row, metric)
        has_value = value is not None and value != ""
        name = str(row.get("display_name") or row.get("username") or "").lower()
        return (0 if has_value else 1, value if has_value else 0, name)

    return sorted(list(rows), key=sort_key, reverse=descending)


# ===== MAIN ENTRY POINT =====


def main(argv=None, gui_runner=run_gui):
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    args = parse_args(raw_argv)
    if args.gui or not raw_argv:
        result = gui_runner()
        return 0 if result is None else result
    weights = dict(args.weight or [])
    report = build_user_productivity_report(
        args.input,
        threshold_minutes=args.threshold_minutes,
        selected_actions=args.actions,
        action_weights=weights,
        selected_users=args.users,
    )
    markdown = render_user_productivity_md(report, input_source=args.input)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
