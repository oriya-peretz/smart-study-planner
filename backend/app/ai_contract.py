"""The backend's own copy of the AI service's contract for POST /plan.

The services share no code, so the backend states what it sends and what it is
willing to accept. tests/test_contract.py checks this copy against the schema the
AI service publishes. Class names match the AI service's, so the schemas can be
compared by name.
"""

from datetime import date, timedelta
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime

from app.models import TaskType

DayHours = Annotated[float, Field(ge=0, le=16, multiple_of=0.5)]

DETAIL_DAYS = 7

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


# ---- What the backend sends ----


class WeeklyHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sunday: DayHours = 0
    monday: DayHours = 0
    tuesday: DayHours = 0
    wednesday: DayHours = 0
    thursday: DayHours = 0
    friday: DayHours = 0
    saturday: DayHours = 0

    def on(self, day: date) -> float:
        return getattr(self, WEEKDAYS[day.weekday()])


class Constraints(BaseModel):
    weekly_hours: WeeklyHours
    blocked_dates: list[date] = Field(default_factory=list, max_length=366)


class PlanTask(BaseModel):
    id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=100)
    type: TaskType
    due_at: NaiveDatetime
    estimated_hours: float | None = Field(default=None, gt=0, le=1000)


class PlanRequest(BaseModel):
    start_date: date
    constraints: Constraints
    tasks: list[PlanTask] = Field(max_length=500)
    note: str = Field(default="", max_length=500)


# ---- What the backend accepts back ----


class Block(BaseModel):
    task_id: int
    hours: float


class DayPlan(BaseModel):
    date: date
    free_hours: float
    planned_hours: float
    blocks: list[Block]


class FallbackReason(StrEnum):
    BUDGET_EXCEEDED = "budget_exceeded"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"


class Assessment(StrEnum):
    ON_TRACK = "on_track"
    SHORTFALL = "shortfall"
    NO_ESTIMATE = "no_estimate"
    OVERDUE = "overdue"
    LATER = "later"


class TaskAssessment(BaseModel):
    task_id: int
    assessment: Assessment
    needed_hours: float | None
    free_hours_before_due: float | None
    slack_hours: float | None
    planned_hours: float
    planned_hours_this_week: float
    missing_hours: float


class PlanResponse(BaseModel):
    start_date: date
    horizon_end: date
    source: Literal["baseline", "model"]
    fallback_reason: FallbackReason | None = None
    all_fit: bool
    days: list[DayPlan]
    tasks: list[TaskAssessment]


def answer_problems(sent: PlanRequest, answer: PlanResponse) -> list[str]:
    """What is wrong with a well-formed answer, checked against what was sent.

    The AI service enforces these rules itself; the backend checks again before
    saving, because only the backend writes data.
    """
    problems = []
    tasks = {task.id: task for task in sent.tasks}
    blocked = set(sent.constraints.blocked_dates)
    hours = sent.constraints.weekly_hours

    if answer.start_date != sent.start_date:
        problems.append("the plan starts on another day")
    dates = [day.date for day in answer.days]
    expected = [sent.start_date + timedelta(days=i) for i in range(DETAIL_DAYS)]
    if dates != expected:
        problems.append("the days are not the seven days from the start date")
    for day in answer.days:
        free = 0 if day.date in blocked else hours.on(day.date)
        planned = sum(block.hours for block in day.blocks)
        if day.free_hours != free:
            problems.append(f"{day.date}: free hours differ from the user's")
        if planned != day.planned_hours or planned > free:
            problems.append(f"{day.date}: more hours planned than are free")
        for block in day.blocks:
            task = tasks.get(block.task_id)
            if task is None:
                problems.append(f"{day.date}: a block for a task that was not sent")
            elif day.date >= task.due_at.date():
                problems.append(f"{day.date}: task {task.id} is planned too late")
            if block.hours <= 0:
                problems.append(f"{day.date}: a block without hours")
    assessed = [item.task_id for item in answer.tasks]
    if sorted(assessed) != sorted(tasks):
        problems.append("not every task sent is assessed exactly once")
    return problems
