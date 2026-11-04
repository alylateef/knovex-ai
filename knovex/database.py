from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from knovex.config import get_settings

settings = get_settings()

# Asynchronous engine & sessionmaker for FastAPI
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

sync_connect_args = {"check_same_thread": False} if settings.DATABASE_SYNC_URL.startswith("sqlite") else {}
sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=sync_connect_args,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding managed async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@contextmanager
def get_sync_db_context() -> Generator[Session, None, None]:
    """
    Pythonic context manager for synchronous database sessions with
    automatic commit on success, rollback on exception, and guaranteed session closure.
    """
    session: Session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_db() -> Session:
    """Convenience getter for a raw synchronous session."""
    return SyncSessionLocal()

