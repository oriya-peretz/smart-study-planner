from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session, select

from app import db
from app.models import (
    FINISHED_STATUSES,
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


def save(session: Session, task: Task) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def all_tasks(session: Session, include_done: bool) -> list[TaskPublic]:
    tasks = [TaskPublic.model_validate(task) for task in session.exec(select(Task))]
    if not include_done:
        tasks = [task for task in tasks if task.status not in FINISHED_STATUSES]
    return tasks


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks", response_model=list[TaskPublic])
def list_tasks(session: db.SessionDep, include_done: bool = True) -> list[TaskPublic]:
    """All tasks in one list, the most urgent first."""
    return by_urgency(all_tasks(session, include_done))


@app.get("/tasks/by-course", response_model=list[CourseTasks])
def list_tasks_by_course(session: db.SessionDep, include_done: bool = True) -> list[CourseTasks]:
    """Tasks grouped by course, each course's tasks by urgency."""
    return by_course(all_tasks(session, include_done))


@app.post("/tasks", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, session: db.SessionDep) -> Task:
    return save(session, Task.model_validate(body))


@app.get("/tasks/{task_id}", response_model=TaskPublic)
def get_task(task_id: int, session: db.SessionDep) -> Task:
    return get_or_404(session, task_id)


@app.patch("/tasks/{task_id}", response_model=TaskPublic)
def update_task(task_id: int, body: TaskUpdate, session: db.SessionDep) -> Task:
    task = get_or_404(session, task_id)
    merged = task.model_dump(exclude={"id"}) | body.model_dump(exclude_unset=True)
    if merged["type"] == TaskType.EXAM:
        merged["status"] = None  # an exam's status comes from its date
    try:
        checked = TaskCreate.model_validate(merged)
    except ValidationError as error:
        # Same 422 response as an invalid request body.
        raise RequestValidationError(error.errors(include_url=False, include_context=False))
    task.sqlmodel_update(checked.model_dump())
    return save(session, task)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: db.SessionDep) -> None:
    session.delete(get_or_404(session, task_id))
    session.commit()
