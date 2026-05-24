"""Match Fit Notes sessions to intervals.icu activities and format descriptions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .fitnotes import Session, Set
from .intervals import Activity

STRENGTH_TYPES = frozenset({"WeightTraining", "Workout"})
MATCH_TOLERANCE = timedelta(hours=2)


@dataclass(frozen=True)
class Match:
    """An intervals.icu activity matched with one or more Fit Notes sessions."""

    activity: Activity
    sessions: tuple[Session, ...]


def _activity_window(
    activity: Activity, tz: ZoneInfo
) -> tuple[datetime, datetime]:
    """Return [start, end] as UTC aware datetimes, expanded by MATCH_TOLERANCE."""
    start_local = activity.start_date_local.replace(tzinfo=tz)
    end_local = start_local + timedelta(seconds=activity.elapsed_time_s)
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    return (start_utc - MATCH_TOLERANCE, end_utc + MATCH_TOLERANCE)


def _overlaps(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    """True if [a_start, a_end] and [b_start, b_end] intervals overlap."""
    return a_start <= b_end and b_start <= a_end


def match_sessions(
    activities: list[Activity],
    sessions: list[Session],
    tz: ZoneInfo,
) -> list[Match]:
    """Match Fit Notes sessions to strength activities by time overlap.

    Only activities with type in STRENGTH_TYPES are considered.
    Activities without any matching session are excluded from the result.
    """
    matches: list[Match] = []
    for activity in activities:
        if activity.type not in STRENGTH_TYPES:
            continue

        win_start, win_end = _activity_window(activity, tz)
        matched = tuple(
            s for s in sessions if _overlaps(win_start, win_end, s.start_time, s.end_time)
        )
        if matched:
            matches.append(Match(activity=activity, sessions=matched))
    return matches


def _format_weight(kg: float) -> str:
    """Drop trailing .0 for clean display: 80.0 -> '80', 12.5 -> '12.5'."""
    return f"{kg:g}"


def _format_set(s: Set) -> str:
    """Format a single set as 'reps×weightkg [RPE x] [Status]'."""
    parts = [f"{s.reps}×{_format_weight(s.weight_kg)}kg"]
    if s.rpe is not None:
        parts.append(f"RPE{_format_weight(s.rpe)}")
    if s.status != "Done":
        parts.append(f"[{s.status}]")
    return " ".join(parts)


def _format_tonnage(kg: float) -> str:
    """Format tonnage: '2.3t' above 1000kg, '850kg' below."""
    if kg >= 1000:
        return f"{kg / 1000:.1f}t"
    return f"{kg:.0f}kg"


def format_description(sessions: tuple[Session, ...]) -> str:
    """Format one or more Fit Notes sessions as an intervals.icu description."""
    all_sets: list[Set] = [s for sess in sessions for s in sess.sets]

    by_exercise: dict[str, list[Set]] = defaultdict(list)
    for s in all_sets:
        by_exercise[s.exercise].append(s)

    tonnage = sum(s.reps * s.weight_kg for s in all_sets if s.status == "Done")
    header = (
        f"{sessions[0].name} — {len(all_sets)} sets across "
        f"{len(by_exercise)} exercises, {_format_tonnage(tonnage)}"
    )

    lines = [header, ""]
    for exercise, exo_sets in by_exercise.items():
        formatted = " · ".join(_format_set(s) for s in exo_sets)
        lines.append(f"{exercise}: {formatted}")

    return "\n".join(lines)