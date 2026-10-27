"""The two ways to view tasks: one list by urgency, or grouped by course."""

from collections.abc import Iterable

from app.models import FINISHED_STATUSES, CoursePublic, CourseTasks, TaskPublic


def urgency_key(task: TaskPublic) -> tuple:
    """Open tasks before finished ones (done, or past exams); then the nearest date first.

    An overdue open task has the earliest date, so it comes first.
    The id breaks ties so the order is always the same.
    """
    return (task.status in FINISHED_STATUSES, task.due_at, task.id)


def by_urgency(tasks: Iterable[TaskPublic]) -> list[TaskPublic]:
    return sorted(tasks, key=urgency_key)


def by_course(tasks: Iterable[TaskPublic], courses: Iterable[CoursePublic]) -> list[CourseTasks]:
    """Every course with its tasks by urgency.

    Courses are ordered by their most urgent task; courses without tasks come
    last, by name, so a new course still shows up.
    """
    groups = {course.id: CourseTasks(course=course, tasks=[]) for course in courses}
    for task in by_urgency(tasks):
        groups[task.course_id].tasks.append(task)

    def course_order(group: CourseTasks) -> tuple:
        if group.tasks:
            return (0, urgency_key(group.tasks[0]))
        return (1, group.course.name.casefold(), group.course.id)

    return sorted(groups.values(), key=course_order)
