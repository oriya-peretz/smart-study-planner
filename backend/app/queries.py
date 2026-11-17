"""Reading a user's courses and tasks, shared by the task routes and the plan."""

from sqlmodel import Session, select

from app.models import FINISHED_STATUSES, Course, Task, TaskPublic, User


def public(task: Task) -> TaskPublic:
    return TaskPublic.model_validate(task)


def user_courses(session: Session, user: User) -> list[Course]:
    return list(session.exec(select(Course).where(Course.user_id == user.id)))


def user_tasks(session: Session, user: User, include_done: bool) -> list[TaskPublic]:
    query = select(Task).join(Course).where(Course.user_id == user.id)
    tasks = [public(task) for task in session.exec(query)]
    if not include_done:
        tasks = [task for task in tasks if task.status not in FINISHED_STATUSES]
    return tasks
