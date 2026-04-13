"""Unit tests for shared.worker_readiness (no Redis/OpenClaw)."""

from __future__ import annotations

from shared.worker_readiness import (
    coordinator_readiness_snapshot,
    executor_readiness_snapshot,
)


def test_coordinator_ready_when_config_and_redis_ok() -> None:
    m = coordinator_readiness_snapshot(
        machine_label="box-a",
        control_plane_api_key_configured=True,
        dashclaw_base_configured=True,
        dashclaw_api_key_configured=True,
        redis_ping_ok=True,
        streams=["jarvis.commands"],
        groups=["g1"],
        consumer_name="c-1",
    )
    assert m["ready_state"] == "ready"
    assert m["config_present"] is True
    assert m["dependency_reachable"] is True
    assert m["role"] == "coordinator"


def test_coordinator_not_ready_when_dashclaw_missing() -> None:
    m = coordinator_readiness_snapshot(
        machine_label="x",
        control_plane_api_key_configured=True,
        dashclaw_base_configured=False,
        dashclaw_api_key_configured=True,
        redis_ping_ok=True,
        streams=[],
        groups=[],
        consumer_name="c",
    )
    assert m["ready_state"] == "not_ready"
    assert m["config_present"] is False


def test_coordinator_not_ready_when_redis_ping_fails() -> None:
    m = coordinator_readiness_snapshot(
        machine_label="x",
        control_plane_api_key_configured=True,
        dashclaw_base_configured=True,
        dashclaw_api_key_configured=True,
        redis_ping_ok=False,
        streams=[],
        groups=[],
        consumer_name="c",
    )
    assert m["ready_state"] == "not_ready"
    assert m["dependency_reachable"] is False


def test_executor_not_ready_when_cli_missing() -> None:
    m = executor_readiness_snapshot(
        machine_label="e1",
        control_plane_api_key_configured=True,
        openclaw_cmd="/no/such/openclaw",
        openclaw_cmd_exists=False,
        openclaw_json_exists=True,
        auth_profiles_configured=True,
        gateway_model_lane="gateway",
        redis_ping_ok=True,
        stream="jarvis.execution",
        group="g",
        consumer_name="ex",
        gateway_health_url=None,
        ollama_health_url=None,
    )
    assert m["ready_state"] == "not_ready"
    assert m["config_present"] is False


def test_executor_degraded_when_auth_profiles_missing() -> None:
    m = executor_readiness_snapshot(
        machine_label="e1",
        control_plane_api_key_configured=True,
        openclaw_cmd="/x/openclaw",
        openclaw_cmd_exists=True,
        openclaw_json_exists=True,
        auth_profiles_configured=False,
        gateway_model_lane="local",
        redis_ping_ok=True,
        stream="jarvis.execution",
        group="g",
        consumer_name="ex",
        gateway_health_url="http://127.0.0.1:18789/health",
        ollama_health_url=None,
    )
    assert m["ready_state"] == "degraded"
    assert "gateway_health_url" in m
