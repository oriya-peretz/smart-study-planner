import pytest
from pydantic import ValidationError

from app.schemas import TaskCreate, TaskStatus, TaskType, TaskUpdate


def homework(**overrides):
    data = {
        "title": "Exercise 3",
        "course": "Automata",
        "type": "homework",
        "due_at": "2026-11-20T23:59",
    }
    return {**data, **overrides}


def exam(**overrides):
    data = {
        "title": "Final exam",
        "course": "Automata",
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


def test_exam_with_location_and_notes_is_valid():
    task = TaskCreate(**exam(location="Building 2, room 104", notes="Open book"))
    assert task.location == "Building 2, room 104"
    assert task.status is None


@pytest.mark.parametrize(
    "field, value",
    [("estimated_hours", 3), ("status", "todo"), ("link", "https://example.com")],
)
def test_exam_rejects_non_exam_fields(field, value):
    with pytest.raises(ValidationError, match="an exam cannot have"):
        TaskCreate(**exam(**{field: value}))


def test_location_is_only_for_exams():
    with pytest.raises(ValidationError, match="only an exam can have"):
        TaskCreate(**homework(location="Room 104"))


@pytest.mark.parametrize("missing", ["title", "course", "type", "due_at"])
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
