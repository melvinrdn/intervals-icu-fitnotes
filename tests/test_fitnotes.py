"""Tests for the Fit Notes CSV parser."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from intervals_icu_fitnotes.fitnotes import (
    Set,
    group_into_sessions,
    parse_csv,
)

HEADER = (
    "Name,StartTime,EndTime,BodyWeight,Exercise,Equipment,"
    "Reps,Weight,Time,Distance,Status,IsWarmup,RPE,RIR,Categories,Note"
)


def write_csv(tmp_path: Path, rows: list[str]) -> Path:
    """Helper: write a CSV with the standard header and given data rows."""
    path = tmp_path / "fitnotes.csv"
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


class TestParseCsv:
    def test_basic_row(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,8,"60,0",,,Done,false,,,"Pectorals,Triceps",'
            ],
        )
        sets = parse_csv(path)

        assert len(sets) == 1
        s = sets[0]
        assert s.session_name == "Push"
        assert s.exercise == "Bench"
        assert s.equipment == "Barbell"
        assert s.reps == 8
        assert s.weight_kg == 60.0
        assert s.status == "Done"
        assert s.is_warmup is False
        assert s.categories == ("Pectorals", "Triceps")
        assert s.note == ""
        assert s.rpe is None
        assert s.rir is None
        assert s.time_s is None

    def test_timestamps_are_utc_aware(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,8,"60,0",,,Done,false,,,"Pectorals",'
            ],
        )
        s = parse_csv(path)[0]

        assert s.start_time == datetime(2025, 2, 23, 10, 13, 53, tzinfo=timezone.utc)
        assert s.end_time == datetime(2025, 2, 23, 11, 8, 47, tzinfo=timezone.utc)
        assert s.start_time.tzinfo is not None
        assert s.end_time.tzinfo is not None

    def test_decimal_comma_in_weight(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Fly,Cable,8,"11,25",,,Done,false,,,"Pectorals",'
            ],
        )
        assert parse_csv(path)[0].weight_kg == 11.25

    def test_rpe_and_rir_parsed(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,5,"80,0",,,Done,false,"8,5",2,"Pectorals",'
            ],
        )
        s = parse_csv(path)[0]
        assert s.rpe == 8.5
        assert s.rir == 2

    def test_time_field_parsed_as_seconds(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Core,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Plank,Bodyweight,1,"0,0",00:01:30,,Done,false,,,"Core",'
            ],
        )
        s = parse_csv(path)[0]
        assert s.time_s == 90.0

    def test_warmup_flag(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,10,"20,0",,,Done,true,,,"Pectorals",'
            ],
        )
        assert parse_csv(path)[0].is_warmup is True

    def test_all_status_values(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,5,"80,0",,,Done,false,,,"Pectorals",',
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,3,"90,0",,,Failed,false,,,"Pectorals",',
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,5,"85,0",,,NotStarted,false,,,"Pectorals",',
            ],
        )
        statuses = [s.status for s in parse_csv(path)]
        assert statuses == ["Done", "Failed", "NotStarted"]

    def test_empty_categories(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,8,"60,0",,,Done,false,,,,',
            ],
        )
        assert parse_csv(path)[0].categories == ()

    def test_note_field(self, tmp_path: Path) -> None:
        path = write_csv(
            tmp_path,
            [
                'Push,2025-02-23T10:13:53Z,2025-02-23T11:08:47Z,"94,0",'
                'Bench,Barbell,8,"60,0",,,Done,false,,,"Pectorals","felt strong"'
            ],
        )
        assert parse_csv(path)[0].note == "felt strong"

    def test_empty_csv(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path, [])
        assert parse_csv(path) == []


class TestGroupIntoSessions:
    @staticmethod
    def make_set(name: str, start: str, exercise: str = "Bench") -> Set:
        ts = datetime.fromisoformat(start)
        return Set(
            session_name=name,
            start_time=ts,
            end_time=ts,
            exercise=exercise,
            equipment="Barbell",
            reps=5,
            weight_kg=60.0,
            time_s=None,
            status="Done",
            is_warmup=False,
            rpe=None,
            rir=None,
            categories=(),
            note="",
        )

    def test_groups_by_name_and_start_time(self) -> None:
        sets = [
            self.make_set("Push", "2025-02-23T10:00:00+00:00"),
            self.make_set("Push", "2025-02-23T10:00:00+00:00", exercise="Fly"),
            self.make_set("Pull", "2025-02-25T10:00:00+00:00"),
        ]
        sessions = group_into_sessions(sets)

        assert len(sessions) == 2
        assert sessions[0].name == "Push"
        assert len(sessions[0].sets) == 2
        assert sessions[1].name == "Pull"
        assert len(sessions[1].sets) == 1

    def test_same_name_different_start_are_separate_sessions(self) -> None:
        sets = [
            self.make_set("Push", "2025-02-23T10:00:00+00:00"),
            self.make_set("Push", "2025-02-25T10:00:00+00:00"),
        ]
        assert len(group_into_sessions(sets)) == 2

    def test_empty_input(self) -> None:
        assert group_into_sessions([]) == []

    def test_sessions_sorted_chronologically(self) -> None:
        sets = [
            self.make_set("Late", "2025-03-01T10:00:00+00:00"),
            self.make_set("Early", "2025-01-01T10:00:00+00:00"),
            self.make_set("Mid", "2025-02-01T10:00:00+00:00"),
        ]
        sessions = group_into_sessions(sets)
        assert [s.name for s in sessions] == ["Early", "Mid", "Late"]
