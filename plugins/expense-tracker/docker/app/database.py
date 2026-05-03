from __future__ import annotations
from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app import models  # noqa: F401 – registers ORM tables
    Base.metadata.create_all(bind=engine)
    _migrate_existing_db()


def _migrate_existing_db() -> None:
    """Tiny SQLite-safe migrations for installs created before 1.1.0."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "app_settings" not in table_names:
            conn.execute(text(
                "CREATE TABLE app_settings ("
                "key VARCHAR PRIMARY KEY, "
                "value VARCHAR NOT NULL, "
                "updated_at DATETIME)"
            ))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
