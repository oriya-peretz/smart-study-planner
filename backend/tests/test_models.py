from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models import (
    CoursePublic,
    TaskCreate,
    TaskPublic,
    TaskStatus,
    TaskType,
    TaskUpdate,
    exam_status,
    to_local_time,
)

COURSE = CoursePublic(id=1, name="Automata")


def homework(**overrides):
    data = {
        "title": "Exercise 3",
        "course_id": 1,
        "type": "homework",
        "due_at": "2026-11-20T23:59",
    }
    return {**data, **overrides}


def exam(**overrides):
    data = {
        "title": "Final exam",
        "course_id": 1,
        "type": "exam",
        "due_at": "2027-01-15T09:00",
    }
    return {**data, **overrides}


def test_minimal_homework_is_valid_and_defaults_to_todo():
    task = TaskCreate(**homework())
    assert task.type == TaskType.HOMEWORK
    assert task.status == TaskStatus.TODO
    assert task.estimated_hours is None
    assert task.link is None


def test_homework_with_all_optional_fields():
    task = TaskCreate(
        **homework(
            estimated_hours=4.5,
            status="in_progress",
            link="https://github.com/me/automata-ex3",
            notes="Ask about question 2",
        )
    )
    assert task.estimated_hours == 4.5
    assert task.status == TaskStatus.IN_PROGRESS


def test_local_file_path_is_accepted_as_link():
    task = TaskCreate(**homework(link=r"C:\Users\me\Documents\ex3.docx"))
    assert task.link == r"C:\Users\me\Documents\ex3.docx"


def test_exam_with_optional_fields_is_valid():
    task = TaskCreate(
        **exam(location="Building 2, room 104", estimated_hours=12, notes="Open book")
    )
    assert task.location == "Building 2, room 104"
    assert task.estimated_hours == 12
    assert task.status is None


@pytest.mark.parametrize(
    "field, value",
    [("status", "todo"), ("link", "https://example.com")],
)
def test_exam_rejects_non_exam_fields(field, value):
    with pytest.raises(ValidationError, match="an exam cannot have"):
        TaskCreate(**exam(**{field: value}))


def test_only_an_exam_can_be_past():
    with pytest.raises(ValidationError, match="only an exam can be past"):
        TaskCreate(**homework(status="past"))


def test_location_is_only_for_exams():
    with pytest.raises(ValidationError, match="only an exam can have"):
        TaskCreate(**homework(location="Room 104"))


@pytest.mark.parametrize("missing", ["title", "course_id", "type", "due_at"])
def test_required_fields(missing):
    data = homework()
    del data[missing]
    with pytest.raises(ValidationError):
        TaskCreate(**data)


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},  # whitespace only becomes empty after stripping
        {"type": "quiz"},  # not one of the five types
        {"estimated_hours": 0},
        {"estimated_hours": -2},
        {"status": "finished"},
        {"due_at": "next week"},
        {"priority": "high"},  # unknown fields are rejected
    ],
)
def test_invalid_values_are_rejected(overrides):
    with pytest.raises(ValidationError):
        TaskCreate(**homework(**overrides))


def test_update_keeps_only_sent_fields():
    update = TaskUpdate(status="done")
    assert update.model_dump(exclude_unset=True) == {"status": TaskStatus.DONE}


def test_exam_status_depends_on_its_date():
    now = datetime(2026, 11, 1, 12, 0)
    assert exam_status(datetime(2026, 11, 1, 11, 59), now) == TaskStatus.PAST
    assert exam_status(datetime(2026, 11, 1, 12, 0), now) == TaskStatus.PAST
    assert exam_status(datetime(2026, 11, 1, 12, 1), now) == TaskStatus.TODO


def test_public_exam_gets_status_from_its_date():
    past = TaskPublic(id=1, course=COURSE, **exam(due_at="2020-01-01T09:00"))
    future = TaskPublic(id=2, course=COURSE, **exam(due_at="2099-01-01T09:00"))
    assert past.status == TaskStatus.PAST
    assert future.status == TaskStatus.TODO


def test_public_non_exam_keeps_its_own_status():
    task = TaskPublic(
        id=1, course=COURSE, status="in_progress", **homework(due_at="2020-01-01T09:00")
    )
    assert task.status == TaskStatus.IN_PROGRESS


def test_time_zone_is_converted_to_local_time():
    task = TaskCreate(**homework(due_at="2026-11-20T10:00+00:00"))
    assert task.due_at.tzinfo is None
    expected = datetime(2026, 11, 20, 10, 0, tzinfo=UTC).astimezone()
    assert task.due_at == expected.replace(tzinfo=None)


# ---- Israeli summer and winter time ----
# In 2026 Israel moves to summer time (UTC+3) on 27 March at 02:00 and back to
# winter time (UTC+2) on 25 October at 02:00, when 01:00-02:00 happens twice.

ISRAEL = ZoneInfo("Asia/Jerusalem")


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_winter_and_summer_times_convert_to_the_same_wall_clock():
    winter = to_local_time(utc("2027-01-15T07:00"), ISRAEL)  # UTC+2
    summer = to_local_time(utc("2027-07-15T06:00"), ISRAEL)  # UTC+3
    assert winter == datetime(2027, 1, 15, 9, 0)
    assert summer == datetime(2027, 7, 15, 9, 0)


def test_the_hour_after_the_spring_change_is_skipped():
    # 00:00 UTC on 27 March is 02:00 winter time, which becomes 03:00 summer time.
    assert to_local_time(utc("2026-03-26T23:59"), ISRAEL) == datetime(
        2026, 3, 27, 1, 59
    )
    assert to_local_time(utc("2026-03-27T00:00"), ISRAEL) == datetime(2026, 3, 27, 3, 0)


def test_the_repeated_autumn_hour_is_the_known_limit_of_local_time():
    # Two different moments, one hour apart, read the same on the wall clock.
    first = to_local_time(utc("2026-10-24T22:30"), ISRAEL)  # 01:30 summer time
    second = to_local_time(utc("2026-10-24T23:30"), ISRAEL)  # 01:30 winter time
    assert first == second == datetime(2026, 10, 25, 1, 30)


def test_exam_status_is_unaffected_by_the_clock_change():
    # An exam right after the autumn change is still upcoming one minute before it.
    exam_at = datetime(2026, 10, 25, 9, 0)
    assert exam_status(exam_at, datetime(2026, 10, 25, 8, 59)) == TaskStatus.TODO
    assert exam_status(exam_at, datetime(2026, 10, 25, 9, 0)) == TaskStatus.PAST
