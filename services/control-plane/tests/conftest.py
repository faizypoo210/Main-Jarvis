"""Pytest setup for control-plane API tests.

Database: PostgreSQL via asyncpg (same stack as production). Tests force DATABASE_URL
from PYTEST_CONTROL_PLANE_DATABASE_URL or a local default — see docs/TESTING.md.

Import order: env vars must be set before app modules load (cached Settings + engine).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

_CONTROL_PLANE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _CONTROL_PLANE_ROOT.parents[1]

# Isolated test DB URL (overrides .env for this pytest process only)
_DEFAULT_TEST_DB = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/jarvis_cp_test"
)
os.environ["DATABASE_URL"] = os.environ.get(
    "PYTEST_CONTROL_PLANE_DATABASE_URL",
    _DEFAULT_TEST_DB,
)
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-not-for-production")
os.environ["CONTROL_PLANE_API_KEY"] = os.environ.get(
    "PYTEST_CONTROL_PLANE_API_KEY",
    "pytest-control-plane-api-key",
)
os.environ.setdefault("CONTROL_PLANE_AUTH_MODE", "api_key")
# Avoid accidental SMS / reminders side effects
os.environ.setdefault("JARVIS_SMS_APPROVALS_ENABLED", "false")
os.environ.setdefault("APPROVAL_REMINDERS_ENABLED", "false")
# Skip engine.dispose() on ASGI shutdown so multiple httpx sessions reuse one pool (see app.main lifespan).
os.environ["CONTROL_PLANE_TESTING"] = "1"

# Jarvis repo root on path for `shared.*` imports (approval routing, etc.)
_sr = str(_REPO_ROOT)
if _sr not in sys.path:
    sys.path.insert(0, _sr)

# After env: import app (binds engine + settings cache to test DATABASE_URL)
from app.core.config import clear_settings_cache  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings_cache_after_each_test() -> None:
    yield
    clear_settings_cache()


@pytest.fixture(scope="session")
def _alembic_upgrade_session() -> None:
    """Apply migrations once per test session (opt-in via pytestmark on integration tests)."""
    env = os.environ.copy()
    env["DATABASE_URL"] = os.environ["DATABASE_URL"]
    _pp = f"{_CONTROL_PLANE_ROOT}{os.pathsep}{_REPO_ROOT}"
    env["PYTHONPATH"] = _pp if not env.get("PYTHONPATH") else f"{_pp}{os.pathsep}{env['PYTHONPATH']}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_CONTROL_PLANE_ROOT,
        env=env,
        check=True,
    )


async def _truncate_public_data() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT string_agg(
                    quote_ident(tablename), ', ' ORDER BY tablename
                )
                FROM pg_tables
                WHERE schemaname = 'public' AND tablename <> 'alembic_version'
                """
            )
        )
        tables = result.scalar_one_or_none()
        if tables:
            await conn.execute(
                text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
            )


@pytest_asyncio.fixture()
async def _clean_db() -> AsyncIterator[None]:
    await _truncate_public_data()
    yield


@pytest_asyncio.fixture(scope="session")
async def client(_alembic_upgrade_session: None) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as ac:
        yield ac


@pytest.fixture()
def api_headers() -> dict[str, str]:
    return {"x-api-key": os.environ["CONTROL_PLANE_API_KEY"]}
