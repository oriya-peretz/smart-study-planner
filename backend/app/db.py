import os
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, inspect, text
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
    add_missing_columns()


# create_all makes missing tables but never changes existing ones. A column
# added to a model after a database was created is added here, with the
# default it would get anyway, so existing data is kept. (A bigger project
# would use a migration tool such as Alembic.)
ADDED_COLUMNS = {
    "user": {"language": "VARCHAR NOT NULL DEFAULT 'en'"},
}


def add_missing_columns() -> None:
    existing = inspect(engine)
    with engine.begin() as connection:
        for table, columns in ADDED_COLUMNS.items():
            present = {column["name"] for column in existing.get_columns(table)}
            for name, definition in columns.items():
                if name not in present:
                    connection.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN {name} {definition}')
                    )


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
