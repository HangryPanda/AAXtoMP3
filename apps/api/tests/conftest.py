"""Pytest fixtures for API tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from core.config import Settings, get_settings
from db.session import get_session
from main import app


# Test database URL (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with overrides."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        debug=True,
        environment="development",
        downloads_dir="/tmp/test_downloads",
        converted_dir="/tmp/test_converted",
        completed_dir="/tmp/test_completed",
        core_scripts_dir="/tmp/test_core",
    )


@pytest.fixture
async def test_engine(test_settings: Settings) -> AsyncGenerator[Any, None]:
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def client(
    test_session: AsyncSession,
    test_settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with dependency overrides."""

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = override_get_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_audible_client() -> MagicMock:
    """Create mock Audible client."""
    mock = MagicMock()
    mock.is_authenticated = AsyncMock(return_value=True)
    mock.get_library = AsyncMock(return_value=[])
    mock.download = AsyncMock(return_value={"success": True})
    return mock


@pytest.fixture
def mock_converter_engine() -> MagicMock:
    """Create mock converter engine."""
    mock = MagicMock()
    mock.convert = AsyncMock(return_value={"success": True, "returncode": 0})
    mock.validate_aax = AsyncMock(return_value={"valid": True})
    return mock


@pytest.fixture
def sample_book_data() -> dict[str, Any]:
    """Sample book data for testing."""
    return {
        "asin": "B00TEST123",
        "title": "Test Audiobook",
        "subtitle": "A Test Subtitle",
        "authors_json": '[{"name": "Test Author"}]',
        "narrators_json": '[{"name": "Test Narrator"}]',
        "runtime_length_min": 360,
        "release_date": "2024-01-01",
        "purchase_date": "2024-01-15",
        "publisher": "Test Publisher",
        "language": "English",
    }


@pytest.fixture
def sample_job_data() -> dict[str, Any]:
    """Sample job data for testing."""
    return {
        "task_type": "DOWNLOAD",
        "book_asin": "B00TEST123",
        "status": "PENDING",
    }
