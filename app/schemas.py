from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


# Fields that only make sense for one kind of task.
EXAM_ONLY_FIELDS = ("location",)
NON_EXAM_FIELDS = ("estimated_hours", "status", "link")


class TaskBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=100)
    type: TaskType
    due_at: datetime
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)
    status: TaskStatus | None = None
    link: str | None = Field(default=None, min_length=1, max_length=2000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class TaskCreate(TaskBase):
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
            if self.status is None:
                self.status = TaskStatus.TODO
        return self


class TaskUpdate(BaseModel):
    """PATCH body: every field is optional; only the fields that were sent change.

    Whether the fields fit the task's type is checked after merging with the
    stored task, since the type may come from the stored task.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    course: str | None = Field(default=None, min_length=1, max_length=100)
    type: TaskType | None = None
    due_at: datetime | None = None
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)
    status: TaskStatus | None = None
    link: str | None = Field(default=None, min_length=1, max_length=2000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class TaskPublic(TaskBase):
    id: int
