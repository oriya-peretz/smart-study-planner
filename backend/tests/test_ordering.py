from datetime import datetime

from app.models import CoursePublic, TaskPublic
from app.ordering import by_course, by_urgency

COURSES = {name: CoursePublic(id=i, name=name) for i, name in enumerate(["A", "Algorithms", "Automata", "Calculus", "Empty"], 1)}


def task(id, course, due, status="todo", type="homework"):
    c = COURSES[course]
    fields = {"id": id, "title": f"task {id}", "course_id": c.id, "course": c, "type": type, "due_at": due}
    if type != "exam":
        fields["status"] = status
    return TaskPublic(**fields)


def test_overdue_open_task_is_most_urgent():
    overdue = task(1, "A", datetime(2020, 1, 1))
    upcoming = task(2, "A", datetime(2099, 1, 1))
    assert by_urgency([upcoming, overdue]) == [overdue, upcoming]


def test_done_tasks_come_last_even_if_earlier():
    done = task(1, "A", datetime(2026, 11, 1), status="done")
    open_task = task(2, "A", datetime(2026, 12, 1))
    assert by_urgency([done, open_task]) == [open_task, done]


def test_past_exam_sorts_with_finished_tasks():
    past_exam = task(1, "A", datetime(2020, 1, 1), type="exam")
    homework = task(2, "A", datetime(2099, 1, 1))
    assert by_urgency([past_exam, homework]) == [homework, past_exam]


def test_same_date_is_ordered_by_id():
    first = task(1, "A", datetime(2026, 11, 1))
    second = task(2, "A", datetime(2026, 11, 1))
    assert by_urgency([second, first]) == [first, second]


def test_courses_ordered_by_their_most_urgent_task():
    groups = by_course(
        [
            task(1, "Automata", datetime(2026, 12, 1)),
            task(2, "Algorithms", datetime(2026, 11, 5)),
            task(3, "Automata", datetime(2026, 11, 10)),
            task(4, "Calculus", datetime(2026, 11, 1), status="done"),
        ],
        [COURSES["Automata"], COURSES["Algorithms"], COURSES["Calculus"]],
    )
    assert [g.course.name for g in groups] == ["Algorithms", "Automata", "Calculus"]
    assert [t.id for t in groups[1].tasks] == [3, 1]


def test_courses_without_tasks_come_last_by_name():
    groups = by_course(
        [task(1, "Automata", datetime(2026, 12, 1))],
        [COURSES["Empty"], COURSES["Automata"], COURSES["Calculus"]],
    )
    assert [g.course.name for g in groups] == ["Automata", "Calculus", "Empty"]
    assert groups[1].tasks == []


def test_no_courses_means_no_groups():
    assert by_course([], []) == []
