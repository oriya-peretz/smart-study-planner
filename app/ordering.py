"""The two ways to view tasks: one list by urgency, or grouped by course."""

from collections.abc import Iterable

from app.models import CourseTasks, TaskPublic, TaskStatus


def urgency_key(task: TaskPublic) -> tuple:
    """Open tasks before done ones; among them, the nearest date first.

    An overdue open task has the earliest date, so it comes first.
    The id breaks ties so the order is always the same.
    """
    return (task.status == TaskStatus.DONE, task.due_at, task.id)


def by_urgency(tasks: Iterable[TaskPublic]) -> list[TaskPublic]:
    return sorted(tasks, key=urgency_key)


def by_course(tasks: Iterable[TaskPublic]) -> list[CourseTasks]:
    """Each course with its tasks by urgency; the course with the most urgent task first."""
    groups: dict[str, list[TaskPublic]] = {}
    for task in by_urgency(tasks):
        groups.setdefault(task.course, []).append(task)
    # Tasks were sorted before grouping, so each group's first task is its most
    # urgent, and dicts keep insertion order: courses are already in order.
    return [CourseTasks(course=course, tasks=items) for course, items in groups.items()]
