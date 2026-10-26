import os
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


def make_engine(url: str) -> Engine:
    # FastAPI runs `def` routes in a thread pool, so SQLite must allow other threads.
    return create_engine(url, connect_args={"check_same_thread": False})


engine = make_engine(DATABASE_URL)


def create_db_and_tables() -> None:
    db_file = engine.url.database  # e.g. "./data/app.db"; None for in-memory
    if db_file:
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
