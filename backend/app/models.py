from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, ConfigDict, NaiveDatetime, model_validator
from sqlmodel import Field, SQLModel


class TaskType(StrEnum):
    EXAM = "exam"  # מבחן
    SUBMISSION = "submission"  # מטלת הגשה
    ONLINE_QUIZ = "online_quiz"  # בוחן ממוחשב
    HOMEWORK = "homework"  # עבודת בית
    PROJECT = "project"  # פרויקט


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    PAST = "past"  # exams only: the exam's date has passed


# Statuses that need no more work; they sort last and can be hidden.
FINISHED_STATUSES = (TaskStatus.DONE, TaskStatus.PAST)


# Fields that only make sense for one kind of task.
# An exam's status is not sent by the client: it is derived from its date.
EXAM_ONLY_FIELDS = ("location",)
NON_EXAM_FIELDS = ("status", "link")


def to_local_time(value: datetime) -> datetime:
    """Keep every date as local time without a time zone, so they compare safely."""
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


LocalDatetime = Annotated[datetime, AfterValidator(to_local_time)]


class TaskBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=100, index=True)
    type: TaskType
    due_at: NaiveDatetime = Field(index=True)  # local time, see to_local_time
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)
    status: TaskStatus | None = None
    link: str | None = Field(default=None, min_length=1, max_length=2000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class Task(TaskBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class TaskCreate(TaskBase):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    due_at: LocalDatetime

    @model_validator(mode="after")
    def check_fields_match_type(self):
        if self.type == TaskType.EXAM:
            sent = [name for name in NON_EXAM_FIELDS if getattr(self, name) is not None]
            if sent:
                raise ValueError(f"an exam cannot have: {', '.join(sent)}")
        else:
            sent = [name for name in EXAM_ONLY_FIELDS if getattr(self, name) is not None]
            if sent:
                raise ValueError(f"only an exam can have: {', '.join(sent)}")
            if self.status == TaskStatus.PAST:
                raise ValueError("only an exam can be past")
            if self.status is None:
                self.status = TaskStatus.TODO
        return self


class TaskUpdate(SQLModel):
    """PATCH body: every field is optional; only the fields that were sent change.

    Sending null clears an optional field. Whether the fields fit the task's
    type is checked after merging with the stored task (see app/main.py),
    since the type may come from the stored task.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    course: str | None = Field(default=None, min_length=1, max_length=100)
    type: TaskType | None = None
    due_at: LocalDatetime | None = None
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)
    status: TaskStatus | None = None
    link: str | None = Field(default=None, min_length=1, max_length=2000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


def exam_status(due_at: datetime, now: datetime) -> TaskStatus:
    """An exam is past once its date and time have passed.

    Past, not done: the date passing does not mean the exam was taken.
    """
    return TaskStatus.PAST if due_at <= now else TaskStatus.TODO


class TaskPublic(TaskBase):
    id: int

    @model_validator(mode="after")
    def set_exam_status(self):
        if self.type == TaskType.EXAM:
            self.status = exam_status(self.due_at, datetime.now())
        return self


class CourseTasks(SQLModel):
    """One course and its tasks, for the by-course view."""

    course: str
    tasks: list[TaskPublic]
