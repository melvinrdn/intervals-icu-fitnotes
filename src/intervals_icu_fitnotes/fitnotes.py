"""Parse FitNotes CSV exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from pathlib import Path
from typing import Literal

Status = Literal["Done", "Failed", "NotStarted"]


@dataclass(frozen=True)
class Set:
    """A single set logged in Fit Notes."""

    session_name: str
    start_time: datetime
    end_time: datetime
    exercise: str
    equipment: str
    reps: int
    weight_kg: float
    time_s: float | None
    status: Status
    is_warmup: bool
    rpe: float | None
    rir: int | None
    categories: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class Session:
    """A workout session: all sets sharing the same Name and StartTime."""

    name: str
    start_time: datetime
    end_time: datetime
    sets: tuple[Set, ...]


def _parse_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value.replace(",", "."))


def _parse_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _parse_duration(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))


def parse_csv(path: Path) -> list[Set]:
    """Parse a Fit Notes CSV export into a flat list of sets"""
    sets: list[Set] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            categories = tuple(
                c.strip() for c in row["Categories"].split(",") if c.strip()
            )
            sets.append(
                Set(
                    session_name=row["Name"],
                    start_time=datetime.fromisoformat(row["StartTime"]),
                    end_time=datetime.fromisoformat(row["EndTime"]),
                    exercise=row["Exercise"],
                    equipment=row["Equipment"],
                    reps=_parse_int(row["Reps"]) or 0,
                    weight_kg=_parse_float(row["Weight"]) or 0.0,
                    time_s=_parse_duration(row["Time"]),
                    status=row["Status"],  # type: ignore[arg-type]
                    is_warmup=row["IsWarmup"].lower() == "true",
                    rpe=_parse_float(row["RPE"]),
                    rir=_parse_int(row["RIR"]),
                    categories=categories,
                    note=row["Note"],
                )
            )
    return sets


def group_into_sessions(sets: list[Set]) -> list[Session]:
    """Group sets into sessions, sorted chronologically by start_time."""
    key = lambda s: (s.start_time, s.session_name, s.end_time)
    ordered = sorted(sets, key=key)
    sessions = []
    for (start, name, end), grp in groupby(ordered, key=key):
        sessions.append(
            Session(name=name, start_time=start, end_time=end, sets=tuple(grp))
        )
    return sessions
