"""The AI service's contract: what the backend sends to POST /plan and gets back.

The service stores nothing. The backend owns the data and sends everything the
plan needs in each request.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NaiveDatetime,
    field_validator,
)

# Free hours in one day, in steps of half an hour (the plan's smallest block).
DayHours = Annotated[float, Field(ge=0, le=16, multiple_of=0.5)]

# In date.weekday() order: Monday is 0, Sunday is 6.
WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskType(StrEnum):
    """The backend's task types (its own copy: the services share no code)."""

    EXAM = "exam"
    SUBMISSION = "submission"
    ONLINE_QUIZ = "online_quiz"
    HOMEWORK = "homework"
    PROJECT = "project"


class WeeklyHours(Request):
    """How many hours the user can study on each day of the week."""

    sunday: DayHours = 0
    monday: DayHours = 0
    tuesday: DayHours = 0
    wednesday: DayHours = 0
    thursday: DayHours = 0
    friday: DayHours = 0
    saturday: DayHours = 0

    def on(self, day: date) -> float:
        return getattr(self, WEEKDAYS[day.weekday()])


class Constraints(Request):
    """Hard limits from the user. The plan never goes beyond them."""

    weekly_hours: WeeklyHours
    blocked_dates: list[date] = Field(default_factory=list, max_length=366)


class PlanTask(Request):
    """One unfinished task. An exam's estimated hours are preparation time."""

    id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=100)
    type: TaskType
    due_at: NaiveDatetime  # the user's local time, like the backend stores it
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)


class PlanRequest(Request):
    start_date: date  # the plan's first day
    constraints: Constraints
    tasks: list[PlanTask] = Field(max_length=500)

    @field_validator("tasks")
    @classmethod
    def ids_are_unique(cls, tasks: list[PlanTask]) -> list[PlanTask]:
        ids = [task.id for task in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task ids must be unique")
        return tasks


class Block(BaseModel):
    """Time for one task on one day."""

    task_id: int
    hours: float


class DayPlan(BaseModel):
    date: date
    free_hours: float
    planned_hours: float  # never more than free_hours
    blocks: list[Block]


class Assessment(StrEnum):
    ON_TRACK = "on_track"  # every needed hour is planned before the due date
    SHORTFALL = "shortfall"  # not enough free hours: see missing_hours
    NO_ESTIMATE = "no_estimate"  # without an estimate there is nothing to plan
    OVERDUE = "overdue"  # the due date is before the plan's first day
    LATER = "later"  # due after the horizon; planned in a later week


class TaskAssessment(BaseModel):
    task_id: int
    assessment: Assessment
    # The estimate rounded up to half hours; None when there is no estimate.
    needed_hours: float | None
    # Free hours from the start up to the day before the due date, ignoring the
    # other tasks; slack is free_hours_before_due minus needed_hours.
    free_hours_before_due: float | None
    slack_hours: float | None
    planned_hours: float  # in the whole horizon
    planned_hours_this_week: float  # in the detailed days
    missing_hours: float  # needed hours that could not be planned in time


class PlanResponse(BaseModel):
    start_date: date
    horizon_end: date  # the last day the plan looked at
    source: Literal["baseline"]  # step 2 adds plans proposed by the model
    all_fit: bool  # no task has a shortfall
    days: list[DayPlan]  # the detailed days, from start_date
    tasks: list[TaskAssessment]  # by priority: least slack first
