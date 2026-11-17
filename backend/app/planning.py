"""The study plan: a user's constraints, and the plan the AI service builds from them.

The backend owns every saved row. It sends the AI service everything a plan
needs, checks the answer (see app/ai_client.py), and saves only a checked plan.
A plan is rebuilt only when the user asks (POST /plan); GET /plan only reads.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, field_validator

from app import db
from app.ai_client import AIClientDep, AIServiceBadOutput, AIServiceUnavailable
from app.ai_contract import (
    Constraints,
    FallbackReason,
    PlanRequest,
    PlanResponse,
    PlanTask,
    TaskAssessment,
    WeeklyHours,
)
from app.auth import CurrentUser
from app.models import StudyConstraints, StudyPlan, TaskType, User
from app.queries import user_tasks

MAX_TASKS = 500  # the AI service's limit; the most urgent tasks go first


def get_today() -> date:
    """The plan's first day. A dependency, so tests can fix the date."""
    return date.today()


TodayDep = Annotated[date, Depends(get_today)]

router = APIRouter(tags=["plan"])


# ---- Constraints ----


class ConstraintsBody(BaseModel):
    """PUT /constraints: the limits a plan must keep."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    weekly_hours: WeeklyHours
    blocked_dates: list[date] = Field(default_factory=list, max_length=366)
    # A preference for the model, such as "keep Thursday light". It cannot
    # change the hours or the dates above.
    note: str = Field(default="", max_length=500)

    @field_validator("blocked_dates")
    @classmethod
    def sorted_once(cls, dates: list[date]) -> list[date]:
        return sorted(set(dates))


class ConstraintsPublic(ConstraintsBody):
    saved: bool  # False: nothing saved yet, so these are the defaults


def constraints_of(row: StudyConstraints) -> ConstraintsBody:
    return ConstraintsBody(
        weekly_hours=WeeklyHours.model_validate(row, from_attributes=True),
        blocked_dates=row.blocked_dates,
        note=row.note,
    )


@router.get("/constraints", response_model=ConstraintsPublic)
def get_constraints(session: db.SessionDep, user: CurrentUser) -> ConstraintsPublic:
    row = session.get(StudyConstraints, user.id)
    if row is None:
        return ConstraintsPublic(weekly_hours=WeeklyHours(), saved=False)
    return ConstraintsPublic(**constraints_of(row).model_dump(), saved=True)


@router.put("/constraints", response_model=ConstraintsPublic)
def put_constraints(
    body: ConstraintsBody, session: db.SessionDep, user: CurrentUser
) -> ConstraintsPublic:
    row = session.get(StudyConstraints, user.id) or StudyConstraints(user_id=user.id)
    row.sqlmodel_update(body.weekly_hours.model_dump())
    row.blocked_dates = [day.isoformat() for day in body.blocked_dates]
    row.note = body.note
    session.add(row)
    session.commit()
    return ConstraintsPublic(**body.model_dump(), saved=True)


# ---- Plan ----


class PlannedBlock(BaseModel):
    task_id: int
    title: str  # as it was when the plan was made
    course: str
    hours: float


class PlannedDay(BaseModel):
    date: date
    free_hours: float
    planned_hours: float
    blocks: list[PlannedBlock]


class PlannedTask(TaskAssessment):
    title: str
    course: str
    type: TaskType
    due_at: NaiveDatetime


class PlanPublic(BaseModel):
    created_at: NaiveDatetime
    start_date: date
    horizon_end: date
    source: str  # "model" or "baseline"
    fallback_reason: FallbackReason | None
    all_fit: bool
    # True when tasks, constraints or the note changed since the plan was made,
    # or when its first day has passed. Rebuilding is the user's choice.
    outdated: bool
    days: list[PlannedDay]
    tasks: list[PlannedTask]


def plan_request(session: db.Session, user: User, today: date) -> PlanRequest:
    """Everything the AI service needs, from the user's data as it is now."""
    row = session.get(StudyConstraints, user.id)
    if row is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Set your free study hours first."
        )
    limits = constraints_of(row)
    tasks = sorted(
        user_tasks(session, user, include_done=False), key=lambda t: t.due_at
    )
    return PlanRequest(
        start_date=today,
        constraints=Constraints(
            weekly_hours=limits.weekly_hours, blocked_dates=limits.blocked_dates
        ),
        tasks=[
            PlanTask(
                id=task.id,
                title=task.title,
                course=task.course.name,
                type=task.type,
                due_at=task.due_at,
                estimated_hours=task.estimated_hours,
            )
            for task in tasks[:MAX_TASKS]
        ],
        note=limits.note,
    )


def inputs(request: dict) -> dict:
    """What a plan depends on, apart from its first day."""
    return {key: value for key, value in request.items() if key != "start_date"}


def plan_public(row: StudyPlan, outdated: bool) -> PlanPublic:
    sent = PlanRequest.model_validate(row.request)
    answer = PlanResponse.model_validate(row.answer)
    tasks = {task.id: task for task in sent.tasks}
    return PlanPublic(
        created_at=row.created_at,
        start_date=answer.start_date,
        horizon_end=answer.horizon_end,
        source=answer.source,
        fallback_reason=answer.fallback_reason,
        all_fit=answer.all_fit,
        outdated=outdated,
        days=[
            PlannedDay(
                date=day.date,
                free_hours=day.free_hours,
                planned_hours=day.planned_hours,
                blocks=[
                    PlannedBlock(
                        task_id=block.task_id,
                        title=tasks[block.task_id].title,
                        course=tasks[block.task_id].course,
                        hours=block.hours,
                    )
                    for block in day.blocks
                ],
            )
            for day in answer.days
        ],
        tasks=[
            PlannedTask(
                **item.model_dump(),
                title=tasks[item.task_id].title,
                course=tasks[item.task_id].course,
                type=tasks[item.task_id].type,
                due_at=tasks[item.task_id].due_at,
            )
            for item in answer.tasks
        ],
    )


@router.post("/plan", response_model=PlanPublic)
def make_plan(
    session: db.SessionDep, user: CurrentUser, ai: AIClientDep, today: TodayDep
) -> PlanPublic:
    """Build a new plan now. A failure keeps the previous plan."""
    request = plan_request(session, user, today)
    # The slow AI call comes before any write, so no database lock is held
    # while the model thinks.
    try:
        answer = ai.make_plan(request)
    except AIServiceUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service unavailable"
        ) from exc
    except AIServiceBadOutput as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="AI service returned invalid output"
        ) from exc
    row = session.get(StudyPlan, user.id) or StudyPlan(user_id=user.id)
    row.created_at = datetime.now().replace(microsecond=0)
    row.request = request.model_dump(mode="json")
    row.answer = answer.model_dump(mode="json")
    session.add(row)
    session.commit()
    return plan_public(row, outdated=False)


@router.get("/plan", response_model=PlanPublic)
def get_plan(session: db.SessionDep, user: CurrentUser, today: TodayDep) -> PlanPublic:
    """The saved plan, and whether it is outdated. Never calls the AI service."""
    row = session.get(StudyPlan, user.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No plan yet")
    try:
        now = inputs(plan_request(session, user, today).model_dump(mode="json"))
        changed = now != inputs(row.request)
    except HTTPException:  # the constraints are gone, so nothing matches them
        changed = True
    started = date.fromisoformat(row.request["start_date"])
    return plan_public(row, outdated=changed or started != today)
