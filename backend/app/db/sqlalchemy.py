from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.postgres_dsn,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.pg_pool_size,
    max_overflow=settings.pg_max_overflow,
    pool_recycle=settings.pg_pool_recycle_seconds,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
