from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session, func, select

from app import auth, db
from app.auth import CurrentUser
from app.models import (
    FINISHED_STATUSES,
    Course,
    CourseCreate,
    CoursePublic,
    CourseTasks,
    Task,
    TaskCreate,
    TaskPublic,
    TaskType,
    TaskUpdate,
    User,
)
from app.ordering import by_course, by_urgency


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.create_db_and_tables()
    yield
    db.engine.dispose()


app = FastAPI(title="Smart Study Planner", lifespan=lifespan)
app.include_router(auth.router)


def save(session: Session, row: Course | Task):
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# Another user's course or task answers 404, exactly like a missing one:
# a 403 would confirm to a stranger that the id exists.


def own_course(session: Session, user: User, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None or course.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def own_task(session: Session, user: User, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None or task.course.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def invalid(field: str, message: str) -> RequestValidationError:
    """A 422 in the same shape as FastAPI's own validation errors."""
    return RequestValidationError([{"loc": ("body", field), "msg": message, "type": "value_error"}])


def check_own_course(session: Session, user: User, course_id: int) -> None:
    course = session.get(Course, course_id)
    if course is None or course.user_id != user.id:
        raise invalid("course_id", "there is no course with this id")


def check_name_is_free(session: Session, user: User, name: str, course_id: int | None = None) -> None:
    """A user's course names are unique, ignoring upper/lower case ("Automata" = "automata")."""
    query = select(Course).where(Course.user_id == user.id, func.lower(Course.name) == name.lower())
    other = session.exec(query).first()
    if other is not None and other.id != course_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"A course named {other.name!r} already exists")


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---- Courses ----


@app.get("/courses", response_model=list[CoursePublic])
def list_courses(session: db.SessionDep, user: CurrentUser) -> list[Course]:
    return sorted(user_courses(session, user), key=lambda course: course.name.casefold())


@app.post("/courses", response_model=CoursePublic, status_code=status.HTTP_201_CREATED)
def create_course(body: CourseCreate, session: db.SessionDep, user: CurrentUser) -> Course:
    check_name_is_free(session, user, body.name)
    return save(session, Course.model_validate(body, update={"user_id": user.id}))


@app.patch("/courses/{course_id}", response_model=CoursePublic)
def rename_course(course_id: int, body: CourseCreate, session: db.SessionDep, user: CurrentUser) -> Course:
    course = own_course(session, user, course_id)
    check_name_is_free(session, user, body.name, course_id)
    course.name = body.name
    return save(session, course)


@app.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, session: db.SessionDep, user: CurrentUser) -> None:
    course = own_course(session, user, course_id)
    if session.exec(select(Task).where(Task.course_id == course_id)).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This course still has tasks. Delete them first."
        )
    session.delete(course)
    session.commit()


# ---- Tasks ----


@app.get("/tasks", response_model=list[TaskPublic])
def list_tasks(session: db.SessionDep, user: CurrentUser, include_done: bool = True) -> list[TaskPublic]:
    """All of the user's tasks in one list, the most urgent first."""
    return by_urgency(user_tasks(session, user, include_done))


@app.get("/tasks/by-course", response_model=list[CourseTasks])
def list_tasks_by_course(
    session: db.SessionDep, user: CurrentUser, include_done: bool = True
) -> list[CourseTasks]:
    """Every course of the user with its tasks by urgency; courses without tasks come last."""
    courses = [CoursePublic.model_validate(course) for course in user_courses(session, user)]
    return by_course(user_tasks(session, user, include_done), courses)


@app.post("/tasks", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, session: db.SessionDep, user: CurrentUser) -> TaskPublic:
    check_own_course(session, user, body.course_id)
    return public(save(session, Task.model_validate(body)))


@app.get("/tasks/{task_id}", response_model=TaskPublic)
def get_task(task_id: int, session: db.SessionDep, user: CurrentUser) -> TaskPublic:
    return public(own_task(session, user, task_id))


@app.patch("/tasks/{task_id}", response_model=TaskPublic)
def update_task(task_id: int, body: TaskUpdate, session: db.SessionDep, user: CurrentUser) -> TaskPublic:
    task = own_task(session, user, task_id)
    changes = body.model_dump(exclude_unset=True)
    merged = task.model_dump(exclude={"id"}) | changes
    if merged["type"] == TaskType.EXAM and "status" not in changes:
        # A task becoming an exam drops its stored status: an exam's status comes
        # from its date. A status the client sent is kept, so validation rejects it.
        merged["status"] = None
    try:
        checked = TaskCreate.model_validate(merged)
    except ValidationError as error:
        # Same 422 response as an invalid request body.
        raise RequestValidationError(error.errors(include_url=False, include_context=False))
    check_own_course(session, user, checked.course_id)
    task.sqlmodel_update(checked.model_dump())
    return public(save(session, task))


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: db.SessionDep, user: CurrentUser) -> None:
    session.delete(own_task(session, user, task_id))
    session.commit()
