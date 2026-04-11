import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../../lib/api";
import { buildGovernedActionPayload } from "../../lib/governedPayload";
import { operatorCopy } from "../../lib/operatorCopy";
import type {
  GitHubCreateIssueRequestBody,
  GitHubCreatePullRequestRequestBody,
  GitHubMergePullRequestRequestBody,
  GmailCreateDraftRequestBody,
  GmailCreateReplyDraftRequestBody,
  GmailSendDraftRequestBody,
  GovernedActionCatalogEntryDTO,
  GovernedActionFieldDTO,
  GovernedActionKind,
} from "../../lib/types";

const STORAGE_KEY = "jarvis.operator_requested_by";

const inputClass =
  "w-full rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]";
const labelClass = "flex flex-col gap-1 text-[10px] text-[var(--text-muted)]";

type Props = { missionId: string };

function defaultValuesForEntry(entry: GovernedActionCatalogEntryDTO): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of entry.fields) {
    if (f.type === "checkbox") {
      out[f.name] = f.name === "draft" ? "true" : "false";
    } else if (f.type === "select" && f.name === "merge_method") {
      out[f.name] = "squash";
    } else {
      out[f.name] = "";
    }
  }
  return out;
}

function fieldByName(entry: GovernedActionCatalogEntryDTO, name: string): GovernedActionFieldDTO | undefined {
  return entry.fields.find((x) => x.name === name);
}

export function GovernedActionLauncher({ missionId }: Props) {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Awaited<ReturnType<typeof api.getOperatorActionCatalog>> | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [kind, setKind] = useState<GovernedActionKind>("github_create_issue");
  const [values, setValues] = useState<Record<string, string>>({});
  const [requestedBy, setRequestedBy] = useState(() => sessionStorage.getItem(STORAGE_KEY) ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const c = await api.getOperatorActionCatalog();
        if (cancelled) return;
        setCatalog(c);
        setCatalogError(null);
        const first = c.actions.find((a) => a.surfaces.command_center !== false && a.enabled);
        if (first) {
          setKind(first.action_kind);
          setValues(defaultValuesForEntry(first));
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setCatalogError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ccActions = useMemo(() => {
    if (!catalog) return [];
    return catalog.actions.filter((a) => a.surfaces.command_center !== false && a.enabled);
  }, [catalog]);

  const entry = useMemo(() => {
    const e = ccActions.find((a) => a.action_kind === kind);
    return e ?? ccActions[0];
  }, [ccActions, kind]);

  useEffect(() => {
    if (!ccActions.length) return;
    if (!ccActions.some((a) => a.action_kind === kind)) {
      const first = ccActions[0];
      if (!first) return;
      setKind(first.action_kind);
      setValues(defaultValuesForEntry(first));
    }
  }, [ccActions, kind]);

  const persistHandle = useCallback((v: string) => {
    setRequestedBy(v);
    sessionStorage.setItem(STORAGE_KEY, v);
  }, []);

  const setField = useCallback((name: string, v: string) => {
    setValues((prev) => ({ ...prev, [name]: v }));
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const rb = requestedBy.trim();
    if (!rb) {
      setError("Enter who is requesting (audit trail).");
      return;
    }
    const base = { requested_by: rb, requested_via: "command_center" as const, source_mission_id: missionId };

    setSubmitting(true);
    try {
      const built = buildGovernedActionPayload(kind, values, base);
      if (!built.ok) {
        setError(built.error);
        return;
      }
      let approval;
      switch (kind) {
        case "github_create_issue":
          approval = await api.postGithubCreateIssue(missionId, built.payload as GitHubCreateIssueRequestBody);
          break;
        case "github_create_pull_request":
          approval = await api.postGithubCreatePullRequest(
            missionId,
            built.payload as GitHubCreatePullRequestRequestBody
          );
          break;
        case "github_merge_pull_request":
          approval = await api.postGithubMergePullRequest(
            missionId,
            built.payload as GitHubMergePullRequestRequestBody
          );
          break;
        case "gmail_create_draft":
          approval = await api.postGmailCreateDraft(missionId, built.payload as GmailCreateDraftRequestBody);
          break;
        case "gmail_create_reply_draft":
          approval = await api.postGmailCreateReplyDraft(
            missionId,
            built.payload as GmailCreateReplyDraftRequestBody
          );
          break;
        case "gmail_send_draft":
          approval = await api.postGmailSendDraft(missionId, built.payload as GmailSendDraftRequestBody);
          break;
        default:
          setError("Unknown action.");
      }
      if (approval) {
        navigate(`/approvals?approval=${encodeURIComponent(approval.id)}`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const currentDescription = entry?.description ?? "";

  const renderField = (name: string) => {
    if (!entry) return null;
    const f = fieldByName(entry, name);
    if (!f) return null;
    const v = values[f.name] ?? "";
    const help = f.help_hint ? (
      <span className="text-[var(--text-muted)]">({f.help_hint})</span>
    ) : null;

    if (f.type === "textarea") {
      return (
        <label key={f.name} className={`${labelClass} sm:col-span-2`}>
          {f.label} {help}
          <textarea
            value={v}
            onChange={(e) => setField(f.name, e.target.value)}
            className={`${inputClass} min-h-[100px]`}
            rows={4}
            placeholder={f.placeholder ?? undefined}
          />
        </label>
      );
    }
    if (f.type === "checkbox") {
      const checked = v.toLowerCase() === "true";
      return (
        <label key={f.name} className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)] sm:col-span-2">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setField(f.name, e.target.checked ? "true" : "false")}
            className="rounded border-[var(--bg-border)]"
          />
          {f.label}
          {f.help_hint ? <span className="text-[var(--text-muted)]">({f.help_hint})</span> : null}
        </label>
      );
    }
    if (f.type === "select" && f.options?.length) {
      const span = f.name === "merge_method" ? "" : "sm:col-span-2";
      return (
        <label key={f.name} className={`${labelClass} ${span}`.trim()}>
          {f.label} {help}
          <select value={v} onChange={(e) => setField(f.name, e.target.value)} className={inputClass}>
            {f.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (f.type === "number") {
      const span = f.name === "pull_number" ? "" : "sm:col-span-2";
      return (
        <label key={f.name} className={`${labelClass} ${span}`.trim()}>
          {f.label} {help}
          <input
            value={v}
            onChange={(e) => setField(f.name, e.target.value)}
            className={inputClass}
            inputMode="numeric"
            placeholder={f.placeholder ?? undefined}
          />
        </label>
      );
    }
    // text, comma_list, email_list — narrow row for base/head side-by-side; PR number + merge method pair
    const narrowPair = new Set(["base", "head"]);
    const span =
      f.type === "comma_list" || f.type === "email_list" || !narrowPair.has(f.name)
        ? "sm:col-span-2"
        : "";
    return (
      <label key={f.name} className={`${labelClass} ${span}`.trim()}>
        {f.label} {help}
        <input
          value={v}
          onChange={(e) => setField(f.name, e.target.value)}
          className={inputClass}
          placeholder={f.placeholder ?? undefined}
        />
      </label>
    );
  };

  if (catalogError) {
    return (
      <section className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 p-4">
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Request a governed action
        </h2>
        <p className="mt-2 text-xs text-[var(--status-amber)]">Could not load action catalog: {catalogError}</p>
      </section>
    );
  }

  if (!catalog) {
    return (
      <section className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 p-4">
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Request a governed action
        </h2>
        <p className="mt-2 text-xs text-[var(--text-secondary)]">Loading governed actions…</p>
      </section>
    );
  }

  if (!ccActions.length || !entry) {
    return (
      <section className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 p-4">
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Request a governed action
        </h2>
        <p className="mt-2 text-xs text-[var(--status-amber)]">No governed actions are available from the catalog.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 p-4">
      <h2 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        Request a governed action
      </h2>
      <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{operatorCopy.governedLauncherIntro}</p>
      <p className="mt-1 text-[10px] text-[var(--text-muted)]">Mission: {missionId}</p>

      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        <label className={labelClass}>
          Action
          <select
            value={kind}
            onChange={(e) => {
              const next = e.target.value as GovernedActionKind;
              setKind(next);
              const nextEntry = ccActions.find((a) => a.action_kind === next);
              if (nextEntry) setValues(defaultValuesForEntry(nextEntry));
            }}
            className={inputClass}
          >
            {ccActions.map((a) => (
              <option key={a.action_kind} value={a.action_kind}>
                {a.title}
              </option>
            ))}
          </select>
          {currentDescription ? (
            <span className="text-[10px] leading-snug text-[var(--text-muted)]">{currentDescription}</span>
          ) : null}
        </label>

        <label className={labelClass}>
          Requested by (audit)
          <input
            value={requestedBy}
            onChange={(e) => persistHandle(e.target.value)}
            className={inputClass}
            placeholder="Name or handle"
            autoComplete="username"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">{entry.field_order.map((name) => renderField(name))}</div>

        {error ? (
          <p className="rounded-lg border border-[var(--status-amber)]/40 bg-[var(--status-amber)]/10 px-2 py-1.5 text-xs text-[var(--status-amber)]">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg border border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/15 px-3 py-2 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--accent-blue)]/25 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Create approval request"}
          </button>
          <Link
            to="/approvals"
            className="text-xs font-medium text-[var(--accent-blue)] hover:underline"
          >
            Open approvals queue
          </Link>
        </div>
      </form>
    </section>
  );
}
