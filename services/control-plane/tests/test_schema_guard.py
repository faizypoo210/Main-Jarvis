"""Unit tests for schema drift detection (no database)."""

from __future__ import annotations

import pytest

from app.core.schema_guard import expected_alembic_head, is_schema_drift_db_error

pytestmark = pytest.mark.unit


def test_is_schema_drift_detects_undefined_column_message() -> None:
    assert is_schema_drift_db_error(
        Exception('column "instance_id" of relation "workers" does not exist')
    )


def test_is_schema_drift_detects_undefined_table_message() -> None:
    assert is_schema_drift_db_error(Exception('relation "heartbeat_findings" does not exist'))


def test_is_schema_drift_false_for_unrelated() -> None:
    assert not is_schema_drift_db_error(Exception("connection refused"))


def test_alembic_head_is_single_revision_id() -> None:
    """Linear chain should expose one head (fails if migration graph breaks)."""
    head = expected_alembic_head()
    assert head
    assert "_" in head or head.isalnum()
