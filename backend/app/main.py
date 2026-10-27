from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, func, select

from app import db
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
)
from app.ordering import by_course, by_urgency


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.create_db_and_tables()
    yield
    db.engine.dispose()


app = FastAPI(title="Smart Study Planner", lifespan=lifespan)


def save(session: Session, row: SQLModel):
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_or_404(session: Session, model: type[SQLModel], row_id: int):
    row = session.get(model, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found")
    return row


def invalid(field: str, message: str) -> RequestValidationError:
    """A 422 in the same shape as FastAPI's own validation errors."""
    return RequestValidationError([{"loc": ("body", field), "msg": message, "type": "value_error"}])


def check_course_exists(session: Session, course_id: int) -> None:
    if session.get(Course, course_id) is None:
        raise invalid("course_id", "there is no course with this id")


def check_name_is_free(session: Session, name: str, course_id: int | None = None) -> None:
    """Course names are unique, ignoring upper/lower case ("Automata" = "automata")."""
    query = select(Course).where(func.lower(Course.name) == name.lower())
    other = session.exec(query).first()
    if other is not None and other.id != course_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"A course named {other.name!r} already exists")


def public(task: Task) -> TaskPublic:
    return TaskPublic.model_validate(task)


def all_tasks(session: Session, include_done: bool) -> list[TaskPublic]:
    tasks = [public(task) for task in session.exec(select(Task))]
    if not include_done:
        tasks = [task for task in tasks if task.status not in FINISHED_STATUSES]
    return tasks


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---- Courses ----


@app.get("/courses", response_model=list[CoursePublic])
def list_courses(session: db.SessionDep) -> list[Course]:
    return list(session.exec(select(Course).order_by(func.lower(Course.name))))


@app.post("/courses", response_model=CoursePublic, status_code=status.HTTP_201_CREATED)
def create_course(body: CourseCreate, session: db.SessionDep) -> Course:
    check_name_is_free(session, body.name)
    return save(session, Course.model_validate(body))


@app.patch("/courses/{course_id}", response_model=CoursePublic)
def rename_course(course_id: int, body: CourseCreate, session: db.SessionDep) -> Course:
    course = get_or_404(session, Course, course_id)
    check_name_is_free(session, body.name, course_id)
    course.name = body.name
    return save(session, course)


@app.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, session: db.SessionDep) -> None:
    course = get_or_404(session, Course, course_id)
    if session.exec(select(Task).where(Task.course_id == course_id)).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This course still has tasks. Delete them first."
        )
    session.delete(course)
    session.commit()


# ---- Tasks ----


@app.get("/tasks", response_model=list[TaskPublic])
def list_tasks(session: db.SessionDep, include_done: bool = True) -> list[TaskPublic]:
    """All tasks in one list, the most urgent first."""
    return by_urgency(all_tasks(session, include_done))


@app.get("/tasks/by-course", response_model=list[CourseTasks])
def list_tasks_by_course(session: db.SessionDep, include_done: bool = True) -> list[CourseTasks]:
    """Every course with its tasks by urgency; courses without tasks come last."""
    courses = [CoursePublic.model_validate(course) for course in session.exec(select(Course))]
    return by_course(all_tasks(session, include_done), courses)


@app.post("/tasks", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, session: db.SessionDep) -> TaskPublic:
    check_course_exists(session, body.course_id)
    return public(save(session, Task.model_validate(body)))


@app.get("/tasks/{task_id}", response_model=TaskPublic)
def get_task(task_id: int, session: db.SessionDep) -> TaskPublic:
    return public(get_or_404(session, Task, task_id))


@app.patch("/tasks/{task_id}", response_model=TaskPublic)
def update_task(task_id: int, body: TaskUpdate, session: db.SessionDep) -> TaskPublic:
    task = get_or_404(session, Task, task_id)
    merged = task.model_dump(exclude={"id"}) | body.model_dump(exclude_unset=True)
    if merged["type"] == TaskType.EXAM:
        merged["status"] = None  # an exam's status comes from its date
    try:
        checked = TaskCreate.model_validate(merged)
    except ValidationError as error:
        # Same 422 response as an invalid request body.
        raise RequestValidationError(error.errors(include_url=False, include_context=False))
    check_course_exists(session, checked.course_id)
    task.sqlmodel_update(checked.model_dump())
    return public(save(session, task))


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: db.SessionDep) -> None:
    session.delete(get_or_404(session, Task, task_id))
    session.commit()
