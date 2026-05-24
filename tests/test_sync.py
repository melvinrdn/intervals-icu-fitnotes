"""Tests for matching and description formatting."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from intervals_icu_fitnotes.fitnotes import Session, Set
from intervals_icu_fitnotes.intervals import Activity
from intervals_icu_fitnotes.sync import (
    format_description,
    match_sessions,
)

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def make_set(
    exercise: str = "Bench",
    reps: int = 5,
    weight: float = 60.0,
    rpe: float | None = None,
    status: str = "Done",
) -> Set:
    ts = datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)
    return Set(
        session_name="Push",
        start_time=ts,
        end_time=ts,
        exercise=exercise,
        equipment="Barbell",
        reps=reps,
        weight_kg=weight,
        time_s=None,
        status=status,  # type: ignore[arg-type]
        is_warmup=False,
        rpe=rpe,
        rir=None,
        categories=(),
        note="",
    )


def make_session(
    name: str = "Push",
    start: str = "2025-06-01T10:00:00+00:00",
    end: str = "2025-06-01T11:00:00+00:00",
    sets: tuple[Set, ...] = (),
) -> Session:
    return Session(
        name=name,
        start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end),
        sets=sets or (make_set(),),
    )


def make_activity(
    type_: str = "WeightTraining",
    start_local: str = "2025-06-01T12:00:00",  # 10:00 UTC in Stockholm summer time (UTC+2)
    duration_s: int = 3600,
    id_: str = "act-1",
) -> Activity:
    return Activity(
        id=id_,
        type=type_,
        name="Strength",
        start_date_local=datetime.fromisoformat(start_local),
        elapsed_time_s=duration_s,
        description=None,
    )


class TestMatchSessions:
    def test_perfect_time_overlap(self) -> None:
        # Activity 10:00-11:00 UTC, session 10:00-11:00 UTC
        activity = make_activity()
        session = make_session()
        matches = match_sessions([activity], [session], STOCKHOLM)

        assert len(matches) == 1
        assert matches[0].activity == activity
        assert matches[0].sessions == (session,)

    def test_session_within_tolerance_before(self) -> None:
        # Session ends 90min before activity start: within ±2h tolerance
        activity = make_activity()  # 10:00-11:00 UTC
        session = make_session(
            start="2025-06-01T07:30:00+00:00",
            end="2025-06-01T08:30:00+00:00",
        )
        matches = match_sessions([activity], [session], STOCKHOLM)
        assert len(matches) == 1

    def test_session_within_tolerance_after(self) -> None:
        # Session starts 90min after activity end: within ±2h tolerance
        activity = make_activity()  # 10:00-11:00 UTC
        session = make_session(
            start="2025-06-01T12:30:00+00:00",
            end="2025-06-01T13:30:00+00:00",
        )
        matches = match_sessions([activity], [session], STOCKHOLM)
        assert len(matches) == 1

    def test_session_outside_tolerance(self) -> None:
        # Session 3h before activity start: outside ±2h tolerance
        activity = make_activity()  # 10:00-11:00 UTC
        session = make_session(
            start="2025-06-01T06:00:00+00:00",
            end="2025-06-01T07:00:00+00:00",
        )
        matches = match_sessions([activity], [session], STOCKHOLM)
        assert matches == []

    def test_non_strength_activity_ignored(self) -> None:
        activity = make_activity(type_="Run")
        session = make_session()
        matches = match_sessions([activity], [session], STOCKHOLM)
        assert matches == []

    def test_activity_without_match_excluded(self) -> None:
        activity = make_activity()
        matches = match_sessions([activity], [], STOCKHOLM)
        assert matches == []

    def test_multiple_sessions_aggregated(self) -> None:
        activity = make_activity(duration_s=7200)  # 10:00-12:00 UTC
        s1 = make_session(start="2025-06-01T10:00:00+00:00", end="2025-06-01T10:45:00+00:00")
        s2 = make_session(start="2025-06-01T11:00:00+00:00", end="2025-06-01T11:45:00+00:00")
        matches = match_sessions([activity], [s1, s2], STOCKHOLM)

        assert len(matches) == 1
        assert matches[0].sessions == (s1, s2)

    def test_workout_type_also_matched(self) -> None:
        activity = make_activity(type_="Workout")
        session = make_session()
        matches = match_sessions([activity], [session], STOCKHOLM)
        assert len(matches) == 1


class TestFormatDescription:
    def test_single_exercise_with_rpe(self) -> None:
        session = make_session(
            sets=(
                make_set("Bench", reps=8, weight=60, rpe=7),
                make_set("Bench", reps=6, weight=70, rpe=8.5),
            )
        )
        desc = format_description((session,))

        assert "Push — 2 sets across 1 exercises" in desc
        assert "Bench: 8×60kg RPE7 · 6×70kg RPE8.5" in desc

    def test_tonnage_in_header(self) -> None:
        # 2×(5×80) = 800kg
        session = make_session(
            sets=(make_set(reps=5, weight=80), make_set(reps=5, weight=80))
        )
        desc = format_description((session,))
        assert "800kg" in desc

    def test_tonnage_in_tonnes_when_large(self) -> None:
        # 50×100 = 5000kg = 5.0t
        sets = tuple(make_set(reps=50, weight=100) for _ in range(1))
        session = make_session(sets=sets)
        desc = format_description((session,))
        assert "5.0t" in desc

    def test_failed_status_marked(self) -> None:
        session = make_session(
            sets=(
                make_set(reps=5, weight=80, status="Done"),
                make_set(reps=3, weight=100, status="Failed"),
            )
        )
        desc = format_description((session,))
        assert "[Failed]" in desc

    def test_failed_excluded_from_tonnage(self) -> None:
        # Only Done sets count: 5×80 = 400kg, Failed 3×100 ignored
        session = make_session(
            sets=(
                make_set(reps=5, weight=80, status="Done"),
                make_set(reps=3, weight=100, status="Failed"),
            )
        )
        desc = format_description((session,))
        assert "400kg" in desc

    def test_decimal_weights_clean(self) -> None:
        session = make_session(sets=(make_set(weight=12.5),))
        desc = format_description((session,))
        assert "12.5kg" in desc
        assert "12.50kg" not in desc

    def test_integer_weights_no_trailing_zero(self) -> None:
        session = make_session(sets=(make_set(weight=80.0),))
        desc = format_description((session,))
        assert "80kg" in desc
        assert "80.0kg" not in desc

    def test_multiple_sessions_aggregated(self) -> None:
        s1 = make_session(name="Push", sets=(make_set("Bench", reps=5, weight=80),))
        s2 = make_session(name="Core", sets=(make_set("Squat", reps=5, weight=100),))
        desc = format_description((s1, s2))
        assert "Bench" in desc
        assert "Squat" in desc
        assert "2 sets across 2 exercises" in desc

    def test_combined_title_when_multiple_session_names(self) -> None:
        s1 = make_session(name="Séance A", sets=(make_set("Bench"),))
        s2 = make_session(name="Core", sets=(make_set("Plank"),))
        desc = format_description((s1, s2))
        assert "Séance A + Core" in desc

    def test_duplicate_session_names_deduplicated(self) -> None:
        s1 = make_session(name="Push", sets=(make_set("Bench"),))
        s2 = make_session(name="Push", sets=(make_set("Fly"),))
        desc = format_description((s1, s2))
        assert "Push + Push" not in desc
        assert desc.split(" — ")[0] == "Push"

    def test_exercises_preserve_order(self) -> None:
        session = make_session(
            sets=(
                make_set("Squat"),
                make_set("Bench"),
                make_set("Deadlift"),
            )
        )
        desc = format_description((session,))
        squat_idx = desc.index("Squat")
        bench_idx = desc.index("Bench")
        deadlift_idx = desc.index("Deadlift")
        assert squat_idx < bench_idx < deadlift_idx


class TestFormatBodyweight:
    def test_bodyweight_sets_show_only_reps(self) -> None:
        session = make_session(
            sets=(
                make_set("Russian twist", reps=20, weight=0),
                make_set("Russian twist", reps=18, weight=0),
            )
        )
        desc = format_description((session,))
        assert "Russian twist: 20 · 18 reps" in desc
        # The exercise line itself shouldn't have ×0kg
        exercise_line = [l for l in desc.split("\n") if l.startswith("Russian twist")][0]
        assert "0kg" not in exercise_line

    def test_bodyweight_collapses_when_identical(self) -> None:
        session = make_session(
            sets=tuple(make_set("Pullup", reps=8, weight=0) for _ in range(3))
        )
        desc = format_description((session,))
        assert "Pullup: 3×8 reps" in desc

    def test_bodyweight_excluded_from_tonnage(self) -> None:
        # 3 sets of 20 bodyweight reps = 0kg tonnage
        session = make_session(
            sets=tuple(make_set("Pullup", reps=20, weight=0) for _ in range(3))
        )
        desc = format_description((session,))
        assert "0kg" in desc


class TestFormatIsometric:
    def test_isometric_shows_duration(self) -> None:
        s1 = make_set("Plank", reps=0, weight=0)
        s2 = make_set("Plank", reps=0, weight=0)
        # Replace time_s using dataclass replace pattern
        from dataclasses import replace

        s1 = replace(s1, time_s=30.0)
        s2 = replace(s2, time_s=45.0)
        session = make_session(sets=(s1, s2))
        desc = format_description((session,))
        assert "Plank: 30s · 45s" in desc

    def test_isometric_collapses_when_identical(self) -> None:
        from dataclasses import replace

        s = make_set("Plank", reps=0, weight=0)
        s = replace(s, time_s=30.0)
        session = make_session(sets=(s, s, s))
        desc = format_description((session,))
        assert "Plank: 3×30s" in desc

    def test_duration_format_minutes(self) -> None:
        from dataclasses import replace

        s = make_set("Plank", reps=0, weight=0)
        s = replace(s, time_s=90.0)
        session = make_session(sets=(s,))
        desc = format_description((session,))
        assert "1m30s" in desc

    def test_duration_format_whole_minutes(self) -> None:
        from dataclasses import replace

        s = make_set("Plank", reps=0, weight=0)
        s = replace(s, time_s=120.0)
        session = make_session(sets=(s,))
        desc = format_description((session,))
        assert "2m" in desc


class TestMixedAndCollapse:
    def test_weighted_exercise_with_some_bodyweight_sets(self) -> None:
        # Pullups: first set with added weight, rest bodyweight
        session = make_session(
            sets=(
                make_set("Pullup", reps=3, weight=5),
                make_set("Pullup", reps=4, weight=0),
                make_set("Pullup", reps=3, weight=0),
            )
        )
        desc = format_description((session,))
        assert "Pullup: 3×5kg · 4×BW · 3×BW" in desc

    def test_collapse_requires_at_least_3_identical_sets(self) -> None:
        # 2 identical sets should NOT collapse
        session = make_session(
            sets=(
                make_set("Bench", reps=5, weight=80),
                make_set("Bench", reps=5, weight=80),
            )
        )
        desc = format_description((session,))
        assert "Bench: 5×80kg · 5×80kg" in desc
        assert "2×5×80kg" not in desc

    def test_collapse_with_exactly_3_identical_sets(self) -> None:
        session = make_session(
            sets=tuple(make_set("Bench", reps=5, weight=80) for _ in range(3))
        )
        desc = format_description((session,))
        assert "Bench: 3×5×80kg" in desc