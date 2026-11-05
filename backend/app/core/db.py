"""راه‌اندازی موتور پایگاه داده و نشست‌ها — SQLAlchemy 2."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _is_sqlite(url: str) -> bool:
    return url.strip().lower().startswith("sqlite")


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if _is_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_recycle"] = 1800
    return create_engine(url, **kwargs)


engine = build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
    """برای SQLite قید کلید خارجی فعال می‌شود؛ PostgreSQL خودش کنترل می‌کند."""
    try:
        import sqlite3

        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    except Exception:  # pragma: no cover
        pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
