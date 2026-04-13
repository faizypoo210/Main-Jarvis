"""Operator integrations report: DB rows + honest machine/repo signals (no secrets)."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.integration import Integration
from app.repositories.worker_repo import WorkerRepository
from app.schemas.operator import IntegrationHubSummary, OperatorIntegrationRow, OperatorIntegrationsResponse
from app.services.system_execution_health import gather_gateway_urls


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.isoformat().replace("+00:00", "Z")


def _http_probe_ok(url: str, timeout: float = 2.0) -> tuple[bool, int | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            return isinstance(code, int) and code < 500, code
    except urllib.error.HTTPError as e:
        return e.code < 500, e.code
    except Exception:
        return False, None


def _repo_root() -> Path:
    # services/control-plane/app/services/this_file.py -> parents[4] = repo root
    return Path(__file__).resolve().parents[4]


def _openclaw_paths() -> dict[str, Path]:
    home = Path.home()
    oc = home / ".openclaw"
    return {
        "openclaw_json": oc / "openclaw.json",
        "auth_profiles": home
        / ".openclaw"
        / "agents"
        / "main"
        / "agent"
        / "auth-profiles.json",
        "composio_plugin": oc / "node_modules" / "@composio" / "openclaw-plugin",
    }


@dataclass(frozen=True)
class _CatalogEntry:
    id: str
    name: str
    kind: str
    provider: str
    db_name_match: frozenset[str]


_CATALOG: tuple[_CatalogEntry, ...] = (
    _CatalogEntry(
        id="openclaw_gateway",
        name="OpenClaw gateway",
        kind="execution_plane",
        provider="openclaw",
        db_name_match=frozenset({"openclaw gateway", "openclaw", "gateway"}),
    ),
    _CatalogEntry(
        id="openclaw_workspace_mirrors",
        name="OpenClaw workspace mirrors (repo)",
        kind="configuration",
        provider="openclaw",
        db_name_match=frozenset({"workspace", "openclaw workspace"}),
    ),
    _CatalogEntry(
        id="composio",
        name="Composio",
        kind="integration_platform",
        provider="composio",
        db_name_match=frozenset({"composio"}),
    ),
    _CatalogEntry(
        id="github",
        name="GitHub",
        kind="connector",
        provider="github",
        db_name_match=frozenset({"github"}),
    ),
    _CatalogEntry(
        id="gmail",
        name="Gmail",
        kind="connector",
        provider="google",
        db_name_match=frozenset({"gmail", "google mail"}),
    ),
    _CatalogEntry(
        id="google_drive",
        name="Google Drive",
        kind="connector",
        provider="google",
        db_name_match=frozenset({"google drive", "drive"}),
    ),
    _CatalogEntry(
        id="notion",
        name="Notion",
        kind="connector",
        provider="notion",
        db_name_match=frozenset({"notion"}),
    ),
    _CatalogEntry(
        id="slack",
        name="Slack",
        kind="connector",
        provider="slack",
        db_name_match=frozenset({"slack"}),
    ),
)


def _db_row_index(rows: list[Integration]) -> dict[str, Integration]:
    out: dict[str, Integration] = {}
    for r in rows:
        key = (r.name or "").strip().lower()
        if key:
            out[key] = r
    return out


def _map_db_to_status(integration: Integration) -> tuple[str, str]:
    """Return (ui_status, connection_source) from DB row."""
    s = (integration.status or "").strip().lower()
    a = (integration.auth_state or "").strip().lower() if integration.auth_state else ""
    if s in ("connected", "active", "ok") and a in ("ok", "connected", "authenticated", "valid"):
        return "connected", "db"
    if s in ("connected", "active") and not a:
        return "configured", "db"
    if s in ("needs_auth", "pending", "pending_auth") or a in (
        "oauth_required",
        "needs_login",
        "unauthenticated",
    ):
        return "needs_auth", "db"
    if s in ("error", "failed", "degraded"):
        return "degraded", "db"
    if s in ("inactive", "disabled"):
        return "not_configured", "db"
    if s:
        return "configured", "db"
    return "unknown", "db"


def _merge_catalog_with_db(
    cat: _CatalogEntry,
    db_by_name: dict[str, Integration],
) -> Integration | None:
    for key in cat.db_name_match:
        if key in db_by_name:
            return db_by_name[key]
    return None


def _build_catalog_row(
    cat: _CatalogEntry,
    db: Integration | None,
    *,
    snapshot_iso: str,
    paths: dict[str, Path],
    workspace_readme: bool,
    gateway_ok: bool | None,
    gateway_code: int | None,
    gateway_scope: str,
    composio_plugin: bool,
) -> OperatorIntegrationRow:
    """Honest row: prefer DB truth; augment with probes."""
    meta: dict[str, Any] = {"catalog_id": cat.id}
    last_activity: str | None = None
    last_checked: str | None = snapshot_iso

    if db is not None:
        st, src = _map_db_to_status(db)
        last_activity = _iso(db.last_checked_at)
        md = db.metadata_
        if isinstance(md, dict):
            meta["db_metadata_keys"] = sorted([k for k in md.keys() if isinstance(k, str)])[:20]
        summary = (
            f"Row in control plane integrations table (source: {src}). "
            f"Stored status={db.status!r}, auth_state={db.auth_state!r}."
        )
        next_action = (
            "If this looks stale, update integration state from the owning service or DB migration."
        )
        if st == "needs_auth":
            next_action = "Complete OAuth or provider login where that integration is managed (usually outside this API)."
        elif st == "connected":
            next_action = "No action required here unless workflows fail — check Activity and executor receipts."
        return OperatorIntegrationRow(
            id=cat.id,
            name=cat.name,
            kind=cat.kind,
            provider=cat.provider,
            status=st,
            connection_source=src,
            last_checked_at=last_checked,
            last_activity_at=last_activity,
            summary=summary,
            next_action=next_action,
            meta=meta,
        )

    # No DB row — inference + probes
    if cat.id == "openclaw_gateway":
        oj = paths["openclaw_json"].is_file()
        meta["openclaw_json_present"] = oj
        meta["gateway_http_ok"] = gateway_ok
        meta["gateway_http_status"] = gateway_code
        meta["gateway_probe_scope"] = gateway_scope
        if gateway_scope == "no_url_configured":
            st = "unknown"
            src = "not_verifiable"
            summ = (
                "No gateway URL configured for probing (set JARVIS_HEALTH_OPENCLAW_GATEWAY_URL) "
                "and no worker metadata gateway_health_url — execution-plane gateway state is unknown from here."
            )
            nxt = "Point health probes at the real gateway host or register workers with gateway_health_url in heartbeat metadata."
        elif gateway_ok is True:
            src = (
                "configured_remote_probe"
                if gateway_scope == "configured_remote"
                else (
                    "worker_registry_probe"
                    if gateway_scope == "worker_registry_inference"
                    else "control_plane_local_probe"
                )
            )
            if gateway_scope == "control_plane_local":
                st = "degraded"
                summ = (
                    "Gateway HTTP responded on a control-plane-local URL (localhost/127.0.0.1). "
                    "This is not proof the execution worker host is healthy."
                )
            else:
                st = "configured"
                summ = (
                    "Gateway HTTP responded at the probed URL (from env or worker registry). "
                    "Provider LLM/auth is not verified here."
                )
            nxt = "Confirm auth profiles on the execution machine; see Workers + System Health probe_source."
        elif gateway_ok is False:
            st = "degraded"
            src = (
                "configured_remote_probe"
                if gateway_scope == "configured_remote"
                else (
                    "worker_registry_probe"
                    if gateway_scope == "worker_registry_inference"
                    else "control_plane_local_probe"
                )
            )
            summ = "Gateway HTTP probe failed or unreachable from the control-plane process (see probe scope)."
            nxt = "Fix bind/port/firewall on the probed host, or correct JARVIS_HEALTH_OPENCLAW_GATEWAY_URL / worker metadata."
        else:
            st = "unknown"
            src = "not_verifiable"
            summ = "Could not classify gateway reachability."
            nxt = "Check network and gateway process on the probed host."
        if oj:
            summ += " openclaw.json is present on the control-plane host user profile (not the execution machine by default)."
        return OperatorIntegrationRow(
            id=cat.id,
            name=cat.name,
            kind=cat.kind,
            provider=cat.provider,
            status=st,
            connection_source=src,
            last_checked_at=last_checked,
            last_activity_at=None,
            summary=summ,
            next_action=nxt,
            meta=meta,
        )

    if cat.id == "openclaw_workspace_mirrors":
        st = "configured" if workspace_readme else "not_configured"
        src = "inferred"
        summ = (
            "Tracked workspace docs under config/workspace/ describe tools and policies; "
            "they are not mission authority."
        )
        if not workspace_readme:
            summ = "Could not find config/workspace/README.md at expected repo path from this deployment."
        return OperatorIntegrationRow(
            id=cat.id,
            name=cat.name,
            kind=cat.kind,
            provider=cat.provider,
            status=st,
            connection_source=src,
            last_checked_at=last_checked,
            last_activity_at=None,
            summary=summ,
            next_action="Run workspace sync script from docs when you change persona/tool policy; missions stay in control plane.",
            meta={**meta, "workspace_readme_found": workspace_readme},
        )

    if cat.id == "composio":
        meta["openclaw_plugin_dir_present"] = composio_plugin
        meta["observation_plane"] = "control_plane_host_fs"
        if composio_plugin:
            st = "configured"
            summ = (
                "Composio OpenClaw plugin directory present under ~/.openclaw on the control-plane host — "
                "not verified on the execution worker machine."
            )
            nxt = "OAuth and Composio API keys are manual per vendor docs — not verified here."
        else:
            st = "not_configured"
            summ = "Composio plugin path not found on the control-plane host user profile."
            nxt = "Install @composio/openclaw-plugin under ~/.openclaw on the execution machine if used there (see scripts/06-install-composio.ps1)."
        return OperatorIntegrationRow(
            id=cat.id,
            name=cat.name,
            kind=cat.kind,
            provider=cat.provider,
            status=st,
            connection_source="control_plane_host_paths",
            last_checked_at=last_checked,
            last_activity_at=None,
            summary=summ,
            next_action=nxt,
            meta=meta,
        )

    # Generic connectors (GitHub, Gmail, …): no DB, no probe — honest external
    return OperatorIntegrationRow(
        id=cat.id,
        name=cat.name,
        kind=cat.kind,
        provider=cat.provider,
        status="unknown",
        connection_source="external_unknown",
        last_checked_at=last_checked,
        last_activity_at=None,
        summary=(
            "No control-plane row and no automated probe for this vendor. "
            "Typical access is via Composio/OpenClaw OAuth on the operator machine, not stored here."
        ),
        next_action="Manage OAuth and tool grants in Composio/OpenClaw; this UI only reflects repo and DB truth.",
        meta=meta,
    )


def _extra_db_rows(
    db_rows: list[Integration],
    snapshot_iso: str,
) -> list[OperatorIntegrationRow]:
    """Surface DB integrations that did not map to catalog."""
    used = set()
    for cat in _CATALOG:
        db = _merge_catalog_with_db(cat, _db_row_index(db_rows))
        if db is not None:
            used.add((db.name or "").strip().lower())

    out: list[OperatorIntegrationRow] = []
    for r in db_rows:
        key = (r.name or "").strip().lower()
        if key in used:
            continue
        st, src = _map_db_to_status(r)
        md = getattr(r, "metadata_", None)
        prov = "unknown"
        if isinstance(md, dict) and isinstance(md.get("provider"), str):
            prov = md["provider"]
        out.append(
            OperatorIntegrationRow(
                id=str(r.id),
                name=r.name,
                kind="custom",
                provider=prov,
                status=st,
                connection_source=src,
                last_checked_at=snapshot_iso,
                last_activity_at=_iso(r.last_checked_at),
                summary=f"Integration row in DB without a fixed catalog mapping. status={r.status!r}, auth_state={r.auth_state!r}.",
                next_action="Align name/metadata with your integration registry or extend the catalog if this is first-class.",
                meta={"db_id": str(r.id)},
            )
        )
    return out


def _summarize(items: list[OperatorIntegrationRow]) -> IntegrationHubSummary:
    connected = sum(1 for i in items if i.status == "connected")
    needs_auth = sum(1 for i in items if i.status == "needs_auth")
    # Everything that is not explicitly connected or needs_auth (includes configured/degraded/unknown).
    not_configured_or_unknown = max(0, len(items) - connected - needs_auth)
    return IntegrationHubSummary(
        total=len(items),
        connected=connected,
        needs_auth=needs_auth,
        not_configured_or_unknown=not_configured_or_unknown,
    )


async def build_integrations_report(session: AsyncSession) -> OperatorIntegrationsResponse:
    result = await session.execute(select(Integration))
    db_rows = list(result.scalars().all())
    db_by_name = _db_row_index(db_rows)

    paths = _openclaw_paths()
    settings = get_settings()
    workers = await WorkerRepository.list_all(session)
    gw_candidates = gather_gateway_urls(settings.JARVIS_HEALTH_OPENCLAW_GATEWAY_URL, workers)
    if gw_candidates:
        gw_url, gw_scope = gw_candidates[0]
        gw_ok, gw_code = _http_probe_ok(gw_url)
    else:
        gw_ok, gw_code = None, None
        gw_scope = "no_url_configured"

    try:
        wr = (_repo_root() / "config" / "workspace" / "README.md").is_file()
    except OSError:
        wr = False

    composio_plugin = paths["composio_plugin"].is_dir()

    snap = _utc_now_iso()
    items: list[OperatorIntegrationRow] = []
    for cat in _CATALOG:
        db_hit = _merge_catalog_with_db(cat, db_by_name)
        items.append(
            _build_catalog_row(
                cat,
                db_hit,
                snapshot_iso=snap,
                paths=paths,
                workspace_readme=wr,
                gateway_ok=gw_ok,
                gateway_code=gw_code,
                gateway_scope=gw_scope,
                composio_plugin=composio_plugin,
            )
        )

    items.extend(_extra_db_rows(db_rows, snap))

    truth_notes = [
        "DB rows reflect integration state stored in the control plane database.",
        "Paths under ~/.openclaw on this host are control-plane-host observations unless workers are co-located; they are not execution-machine truth by default.",
        "Gateway HTTP probes run from the control-plane process. Use JARVIS_HEALTH_OPENCLAW_GATEWAY_URL for a remote URL and/or worker heartbeat metadata gateway_health_url for execution hints.",
        "Provider OAuth tokens and Composio secrets are not read or returned.",
        "Connector apps (GitHub, Gmail, etc.) are listed for context; connectivity is not verified without DB rows.",
    ]

    return OperatorIntegrationsResponse(
        generated_at=snap,
        summary=_summarize(items),
        items=items,
        truth_notes=truth_notes,
    )


def filter_items_by_tab(
    items: list[OperatorIntegrationRow],
    tab: str | None,
) -> list[OperatorIntegrationRow]:
    if not tab or tab == "all":
        return items
    if tab == "connected":
        return [i for i in items if i.status == "connected"]
    if tab == "needs_auth":
        return [i for i in items if i.status == "needs_auth"]
    if tab == "not_configured":
        return [i for i in items if i.status not in ("connected", "needs_auth")]
    return items
