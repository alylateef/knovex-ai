"""
Knovex AI - Pytest Test Configuration & Fixtures
"""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_SYNC_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["QDRANT_URL"] = ":memory:"
os.environ["XAI_API_KEY"] = "mock-xai-api-key"

from knovex.database import Base, get_async_db
from knovex.main import app
from knovex.models import Tenant, User
from knovex.security import create_access_token, hash_password


@pytest_asyncio.fixture(scope="function")
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    async def override_get_async_db():
        yield test_db

    app.dependency_overrides[get_async_db] = override_get_async_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def tenant_a(test_db: AsyncSession):
    tenant = Tenant(id="tenant-a-uuid", name="Acme Corp", slug="acme-corp")
    user = User(
        id="user-a-uuid",
        tenant_id="tenant-a-uuid",
        email="alice@acme.com",
        hashed_password=hash_password("password123"),
        role="admin",
    )
    test_db.add(tenant)
    test_db.add(user)
    await test_db.commit()
    token, _ = create_access_token("user-a-uuid", "tenant-a-uuid", "admin", "alice@acme.com")
    return {"tenant": tenant, "user": user, "token": token}


@pytest_asyncio.fixture(scope="function")
async def tenant_b(test_db: AsyncSession):
    tenant = Tenant(id="tenant-b-uuid", name="Beta Inc", slug="beta-inc")
    user = User(
        id="user-b-uuid",
        tenant_id="tenant-b-uuid",
        email="bob@beta.com",
        hashed_password=hash_password("password456"),
        role="user",
    )
    test_db.add(tenant)
    test_db.add(user)
    await test_db.commit()
    token, _ = create_access_token("user-b-uuid", "tenant-b-uuid", "user", "bob@beta.com")
    return {"tenant": tenant, "user": user, "token": token}
