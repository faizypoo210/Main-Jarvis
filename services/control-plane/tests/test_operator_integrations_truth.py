"""Integrations report: localhost / control-plane paths are not execution truth."""

from __future__ import annotations

from pathlib import Path

from app.services.operator_integrations import _CATALOG, _build_catalog_row


def _cat(cat_id: str):
    return next(c for c in _CATALOG if c.id == cat_id)


def test_openclaw_gateway_without_probe_url_is_unknown_not_execution_truth() -> None:
    row = _build_catalog_row(
        _cat("openclaw_gateway"),
        None,
        snapshot_iso="2020-01-01T00:00:00Z",
        paths={
            "openclaw_json": Path("/nonexistent/openclaw.json"),
            "auth_profiles": Path("/nonexistent/auth.json"),
            "composio_plugin": Path("/nonexistent/composio"),
        },
        workspace_readme=False,
        gateway_ok=None,
        gateway_code=None,
        gateway_scope="no_url_configured",
        composio_plugin=False,
    )
    assert row.status == "unknown"
    assert row.connection_source == "not_verifiable"
    assert "unknown" in row.summary.lower()
    assert "execution-plane" in row.summary.lower() or "execution" in row.summary.lower()


def test_openclaw_gateway_localhost_probe_is_degraded_not_green_execution() -> None:
    row = _build_catalog_row(
        _cat("openclaw_gateway"),
        None,
        snapshot_iso="2020-01-01T00:00:00Z",
        paths={
            "openclaw_json": Path("/nonexistent/openclaw.json"),
            "auth_profiles": Path("/nonexistent/auth.json"),
            "composio_plugin": Path("/nonexistent/composio"),
        },
        workspace_readme=False,
        gateway_ok=True,
        gateway_code=200,
        gateway_scope="control_plane_local",
        composio_plugin=False,
    )
    assert row.status == "degraded"
    assert "localhost" in row.summary.lower() or "127.0.0.1" in row.summary.lower()
    assert "execution" in row.summary.lower() or "worker" in row.summary.lower()


def test_composio_row_labels_control_plane_host_fs() -> None:
    row = _build_catalog_row(
        _cat("composio"),
        None,
        snapshot_iso="2020-01-01T00:00:00Z",
        paths={
            "openclaw_json": Path("/nonexistent/openclaw.json"),
            "auth_profiles": Path("/nonexistent/auth.json"),
            "composio_plugin": Path("/nonexistent/composio"),
        },
        workspace_readme=False,
        gateway_ok=None,
        gateway_code=None,
        gateway_scope="no_url_configured",
        composio_plugin=True,
    )
    assert row.connection_source == "control_plane_host_paths"
    assert "control-plane" in row.summary.lower()
