"""The baseline plan: deterministic rules, no model.

Hours are counted in half-hour units internally, so sums are exact integers.

1. Free time per day comes only from the constraints (blocked dates have none).
2. A task can be worked on only on days before its due date.
3. If not every task fits, keep the largest number of tasks on time
   (Moore-Hodgson); the others still get whatever time is left, and their
   missing hours are reported.
4. Each half hour goes to the task with the least slack (least-laxity-first),
   tasks that fit before those that do not. Slack is the free time left before
   the due date minus the work left, so a long task due later can come before
   a short one due sooner.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.schemas import (
    Assessment,
    Block,
    DayPlan,
    PlanRequest,
    PlanResponse,
    PlanTask,
    TaskAssessment,
)

HORIZON_DAYS = 56  # look 8 weeks ahead
DETAIL_DAYS = 7  # return the first week day by day


def to_units(hours: float) -> int:
    """Hours to half-hour units, rounded up: an estimate of 1.2 h needs 1.5 h."""
    return math.ceil(round(hours * 2, 9))


def to_hours(units: int) -> float:
    return units / 2


@dataclass
class Candidate:
    """A task the plan can work on within the horizon."""

    task: PlanTask
    deadline: int  # index of the due day; days 0 .. deadline - 1 are usable
    need: int  # half-hour units

    @property
    def order(self) -> tuple[datetime, int]:
        return self.task.due_at, self.task.id


def fitting_ids(candidates: list[Candidate], before: list[int]) -> set[int]:
    """The largest set of tasks that can all be done before their due dates.

    `before[d]` is the free time in days 0 .. d - 1. Moore-Hodgson: take tasks by
    due date; whenever the total no longer fits, drop the largest task so far.
    """
    kept: list[Candidate] = []
    total = 0
    for candidate in sorted(candidates, key=lambda c: (c.deadline, c.order)):
        kept.append(candidate)
        total += candidate.need
        if total > before[candidate.deadline]:
            # the largest task; among equals, the one due last
            largest = max(kept, key=lambda c: (c.need, c.order))
            kept.remove(largest)
            total -= largest.need
    return {c.task.id for c in kept}


def make_plan(request: PlanRequest) -> PlanResponse:
    start = request.start_date
    days = [start + timedelta(days=i) for i in range(HORIZON_DAYS)]
    blocked = set(request.constraints.blocked_dates)
    hours = request.constraints.weekly_hours
    free = [0 if day in blocked else to_units(hours.on(day)) for day in days]
    before = [0]  # before[d]: free time in days 0 .. d - 1
    for units in free:
        before.append(before[-1] + units)

    assessments: dict[int, Assessment] = {}
    candidates: list[Candidate] = []
    for task in request.tasks:
        deadline = (task.due_at.date() - start).days
        if task.estimated_hours is None:
            assessments[task.id] = Assessment.NO_ESTIMATE
        elif deadline < 0:
            assessments[task.id] = Assessment.OVERDUE
        elif deadline > HORIZON_DAYS:
            assessments[task.id] = Assessment.LATER
        else:
            need = to_units(task.estimated_hours)
            candidates.append(Candidate(task, deadline, need))

    fits = fitting_ids(candidates, before)
    left = {c.task.id: c.need for c in candidates}
    planned = [dict[int, int]() for _ in days]  # day -> task id -> units

    for day in range(HORIZON_DAYS):
        used = 0
        while used < free[day]:
            open_now = [c for c in candidates if left[c.task.id] and day < c.deadline]
            if not open_now:
                break
            # The next half hour goes to the task with the least slack: the free
            # time left before its due date minus the work it still needs.
            now = before[day] + used  # free time already behind us
            _, _, (_, chosen) = min(
                (
                    c.task.id not in fits,
                    before[c.deadline] - now - left[c.task.id],
                    c.order,
                )
                for c in open_now
            )
            left[chosen] -= 1
            planned[day][chosen] = planned[day].get(chosen, 0) + 1
            used += 1

    def total(task_id: int, days: range) -> int:
        return sum(planned[day].get(task_id, 0) for day in days)

    by_id = {c.task.id: c for c in candidates}
    results = []
    for task in request.tasks:
        candidate = by_id.get(task.id)
        if candidate is None:
            results.append(
                TaskAssessment(
                    task_id=task.id,
                    assessment=assessments[task.id],
                    needed_hours=(
                        to_hours(to_units(task.estimated_hours))
                        if task.estimated_hours is not None
                        else None
                    ),
                    free_hours_before_due=None,
                    slack_hours=None,
                    planned_hours=0,
                    planned_hours_this_week=0,
                    missing_hours=0,
                )
            )
            continue
        available = before[candidate.deadline]
        missing = left[task.id]
        results.append(
            TaskAssessment(
                task_id=task.id,
                assessment=Assessment.SHORTFALL if missing else Assessment.ON_TRACK,
                needed_hours=to_hours(candidate.need),
                free_hours_before_due=to_hours(available),
                slack_hours=to_hours(available - candidate.need),
                planned_hours=to_hours(total(task.id, range(HORIZON_DAYS))),
                planned_hours_this_week=to_hours(total(task.id, range(DETAIL_DAYS))),
                missing_hours=to_hours(missing),
            )
        )

    # Plannable tasks first, least slack first; then the ones the plan only reports.
    rank = {task.id: (task.due_at, task.id) for task in request.tasks}
    results.sort(
        key=lambda r: (
            r.slack_hours is None,
            r.slack_hours if r.slack_hours is not None else 0,
            rank[r.task_id],
        )
    )
    position = {r.task_id: i for i, r in enumerate(results)}

    detail = []
    for day in range(DETAIL_DAYS):
        blocks = sorted(planned[day].items(), key=lambda item: position[item[0]])
        detail.append(
            DayPlan(
                date=days[day],
                free_hours=to_hours(free[day]),
                planned_hours=to_hours(sum(planned[day].values())),
                blocks=[Block(task_id=i, hours=to_hours(u)) for i, u in blocks],
            )
        )

    return PlanResponse(
        start_date=start,
        horizon_end=days[-1],
        source="baseline",
        all_fit=all(r.assessment != Assessment.SHORTFALL for r in results),
        days=detail,
        tasks=results,
    )
