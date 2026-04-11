import { useCallback, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../../lib/api";
import { operatorCopy } from "../../lib/operatorCopy";
import type { GovernedActionKind, GitHubMergeMethod } from "../../lib/types";

const REPO_RE = /^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/;
const STORAGE_KEY = "jarvis.operator_requested_by";

const inputClass =
  "w-full rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]";
const labelClass = "flex flex-col gap-1 text-[10px] text-[var(--text-muted)]";

const ACTIONS: { id: GovernedActionKind; label: string; hint: string }[] = [
  {
    id: "github_create_issue",
    label: "Create approval request — GitHub issue",
    hint: "Opens a red-risk approval; issue is created only after approval.",
  },
  {
    id: "github_create_pull_request",
    label: "Create approval request — GitHub draft PR",
    hint: "Existing branches only; PR is created only after approval.",
  },
  {
    id: "github_merge_pull_request",
    label: "Create approval request — merge GitHub PR",
    hint: "Preflight runs server-side; merge executes only after approval.",
  },
  {
    id: "gmail_create_draft",
    label: "Create approval request — Gmail new draft",
    hint: "Draft is created only after approval; does not send.",
  },
  {
    id: "gmail_create_reply_draft",
    label: "Create approval request — Gmail reply draft",
    hint: "Reply draft in thread; does not send until approved and executed.",
  },
  {
    id: "gmail_send_draft",
    label: "Create approval request — Gmail send existing draft",
    hint: "Send runs only after approval.",
  },
];

function parseCommaList(s: string): string[] {
  return s
    .split(/[,]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function looseEmailOk(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}

type Props = { missionId: string };

export function GovernedActionLauncher({ missionId }: Props) {
  const navigate = useNavigate();
  const [kind, setKind] = useState<GovernedActionKind>("github_create_issue");
  const [requestedBy, setRequestedBy] = useState(() => sessionStorage.getItem(STORAGE_KEY) ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ghIssueRepo, setGhIssueRepo] = useState("");
  const [ghIssueTitle, setGhIssueTitle] = useState("");
  const [ghIssueBody, setGhIssueBody] = useState("");
  const [ghIssueLabels, setGhIssueLabels] = useState("");

  const [ghPrRepo, setGhPrRepo] = useState("");
  const [ghPrBase, setGhPrBase] = useState("");
  const [ghPrHead, setGhPrHead] = useState("");
  const [ghPrTitle, setGhPrTitle] = useState("");
  const [ghPrBody, setGhPrBody] = useState("");
  const [ghPrDraft, setGhPrDraft] = useState(true);

  const [ghMergeRepo, setGhMergeRepo] = useState("");
  const [ghMergePull, setGhMergePull] = useState("");
  const [ghMergeMethod, setGhMergeMethod] = useState<GitHubMergeMethod>("squash");
  const [ghMergeSha, setGhMergeSha] = useState("");

  const [gmTo, setGmTo] = useState("");
  const [gmSubj, setGmSubj] = useState("");
  const [gmBody, setGmBody] = useState("");
  const [gmCc, setGmCc] = useState("");
  const [gmBcc, setGmBcc] = useState("");

  const [gmReplyId, setGmReplyId] = useState("");
  const [gmThread, setGmThread] = useState("");
  const [gmReplyBody, setGmReplyBody] = useState("");
  const [gmReplyCc, setGmReplyCc] = useState("");
  const [gmReplyBcc, setGmReplyBcc] = useState("");
  const [gmReplySubj, setGmReplySubj] = useState("");

  const [gmDraftId, setGmDraftId] = useState("");

  const persistHandle = useCallback((v: string) => {
    setRequestedBy(v);
    sessionStorage.setItem(STORAGE_KEY, v);
  }, []);

  const validateRequestedBy = (): string | null => {
    const t = requestedBy.trim();
    if (!t) return "Enter who is requesting (audit trail).";
    return null;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const rbErr = validateRequestedBy();
    if (rbErr) {
      setError(rbErr);
      return;
    }
    const rb = requestedBy.trim();
    const base = { requested_by: rb, requested_via: "command_center" as const, source_mission_id: missionId };

    setSubmitting(true);
    try {
      let approval;
      switch (kind) {
        case "github_create_issue": {
          const repo = ghIssueRepo.trim();
          const title = ghIssueTitle.trim();
          if (!REPO_RE.test(repo)) setError("Repo must look like owner/name."); else if (!title)
            setError("Title is required.");
          else {
            const labels = parseCommaList(ghIssueLabels).slice(0, 20);
            approval = await api.postGithubCreateIssue(missionId, {
              ...base,
              repo,
              title,
              body: ghIssueBody,
              ...(labels.length ? { labels } : {}),
            });
          }
          break;
        }
        case "github_create_pull_request": {
          const repo = ghPrRepo.trim();
          const title = ghPrTitle.trim();
          const baseRef = ghPrBase.trim();
          const headRef = ghPrHead.trim();
          if (!REPO_RE.test(repo)) setError("Repo must look like owner/name.");
          else if (!baseRef || !headRef) setError("Base and head are required.");
          else if (!title) setError("Title is required.");
          else {
            approval = await api.postGithubCreatePullRequest(missionId, {
              ...base,
              repo,
              base: baseRef,
              head: headRef,
              title,
              body: ghPrBody,
              draft: ghPrDraft,
            });
          }
          break;
        }
        case "github_merge_pull_request": {
          const repo = ghMergeRepo.trim();
          const pn = parseInt(ghMergePull.trim(), 10);
          const sha = ghMergeSha.trim();
          if (!REPO_RE.test(repo)) setError("Repo must look like owner/name.");
          else if (!Number.isFinite(pn) || pn < 1) setError("PR number must be a positive integer.");
          else {
            approval = await api.postGithubMergePullRequest(missionId, {
              ...base,
              repo,
              pull_number: pn,
              merge_method: ghMergeMethod,
              ...(sha ? { expected_head_sha: sha } : {}),
            });
          }
          break;
        }
        case "gmail_create_draft": {
          const to = parseCommaList(gmTo).filter(looseEmailOk);
          const subj = gmSubj.trim();
          if (!to.length) setError("At least one valid To address is required.");
          else if (!subj) setError("Subject is required.");
          else {
            const cc = parseCommaList(gmCc).filter(looseEmailOk);
            const bcc = parseCommaList(gmBcc).filter(looseEmailOk);
            approval = await api.postGmailCreateDraft(missionId, {
              ...base,
              to,
              subject: subj,
              body: gmBody,
              ...(cc.length ? { cc } : {}),
              ...(bcc.length ? { bcc } : {}),
            });
          }
          break;
        }
        case "gmail_create_reply_draft": {
          const rid = gmReplyId.trim();
          if (!rid) setError("Reply-to message id is required.");
          else {
            const cc = parseCommaList(gmReplyCc).filter(looseEmailOk);
            const bcc = parseCommaList(gmReplyBcc).filter(looseEmailOk);
            const thread = gmThread.trim();
            const subj = gmReplySubj.trim();
            approval = await api.postGmailCreateReplyDraft(missionId, {
              ...base,
              reply_to_message_id: rid,
              body: gmReplyBody,
              ...(thread ? { thread_id: thread } : {}),
              ...(cc.length ? { cc } : {}),
              ...(bcc.length ? { bcc } : {}),
              ...(subj ? { subject: subj } : {}),
            });
          }
          break;
        }
        case "gmail_send_draft": {
          const did = gmDraftId.trim();
          if (!did) setError("Draft id is required.");
          else {
            approval = await api.postGmailSendDraft(missionId, {
              ...base,
              draft_id: did,
            });
          }
          break;
        }
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

  const currentHint = ACTIONS.find((a) => a.id === kind)?.hint ?? "";

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
            onChange={(e) => setKind(e.target.value as GovernedActionKind)}
            className={inputClass}
          >
            {ACTIONS.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
          {currentHint ? (
            <span className="text-[10px] leading-snug text-[var(--text-muted)]">{currentHint}</span>
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

        {kind === "github_create_issue" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>
              Repo <span className="text-[var(--text-muted)]">(owner/name)</span>
              <input
                value={ghIssueRepo}
                onChange={(e) => setGhIssueRepo(e.target.value)}
                className={inputClass}
                placeholder="org/repo"
              />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Title
              <input value={ghIssueTitle} onChange={(e) => setGhIssueTitle(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Body
              <textarea
                value={ghIssueBody}
                onChange={(e) => setGhIssueBody(e.target.value)}
                className={`${inputClass} min-h-[100px]`}
                rows={4}
              />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Labels <span className="text-[var(--text-muted)]">(optional, comma-separated)</span>
              <input
                value={ghIssueLabels}
                onChange={(e) => setGhIssueLabels(e.target.value)}
                className={inputClass}
                placeholder="bug, enhancement"
              />
            </label>
          </div>
        ) : null}

        {kind === "github_create_pull_request" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>
              Repo
              <input
                value={ghPrRepo}
                onChange={(e) => setGhPrRepo(e.target.value)}
                className={inputClass}
                placeholder="org/repo"
              />
            </label>
            <label className={labelClass}>
              Base
              <input value={ghPrBase} onChange={(e) => setGhPrBase(e.target.value)} className={inputClass} />
            </label>
            <label className={labelClass}>
              Head
              <input value={ghPrHead} onChange={(e) => setGhPrHead(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Title
              <input value={ghPrTitle} onChange={(e) => setGhPrTitle(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Body
              <textarea
                value={ghPrBody}
                onChange={(e) => setGhPrBody(e.target.value)}
                className={`${inputClass} min-h-[100px]`}
                rows={4}
              />
            </label>
            <label className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)] sm:col-span-2">
              <input
                type="checkbox"
                checked={ghPrDraft}
                onChange={(e) => setGhPrDraft(e.target.checked)}
                className="rounded border-[var(--bg-border)]"
              />
              Draft PR
            </label>
          </div>
        ) : null}

        {kind === "github_merge_pull_request" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>
              Repo
              <input
                value={ghMergeRepo}
                onChange={(e) => setGhMergeRepo(e.target.value)}
                className={inputClass}
                placeholder="org/repo"
              />
            </label>
            <label className={labelClass}>
              PR number
              <input
                value={ghMergePull}
                onChange={(e) => setGhMergePull(e.target.value)}
                className={inputClass}
                inputMode="numeric"
              />
            </label>
            <label className={labelClass}>
              Merge method
              <select
                value={ghMergeMethod}
                onChange={(e) => setGhMergeMethod(e.target.value as GitHubMergeMethod)}
                className={inputClass}
              >
                <option value="squash">squash</option>
                <option value="merge">merge</option>
                <option value="rebase">rebase</option>
              </select>
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Expected head SHA <span className="text-[var(--text-muted)]">(optional race guard)</span>
              <input value={ghMergeSha} onChange={(e) => setGhMergeSha(e.target.value)} className={inputClass} />
            </label>
          </div>
        ) : null}

        {kind === "gmail_create_draft" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>
              To <span className="text-[var(--text-muted)]">(comma-separated)</span>
              <input value={gmTo} onChange={(e) => setGmTo(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Subject
              <input value={gmSubj} onChange={(e) => setGmSubj(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Body
              <textarea
                value={gmBody}
                onChange={(e) => setGmBody(e.target.value)}
                className={`${inputClass} min-h-[100px]`}
                rows={4}
              />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Cc <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmCc} onChange={(e) => setGmCc(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Bcc <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmBcc} onChange={(e) => setGmBcc(e.target.value)} className={inputClass} />
            </label>
          </div>
        ) : null}

        {kind === "gmail_create_reply_draft" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>
              Reply-to message id <span className="text-[var(--text-muted)]">(Gmail API id)</span>
              <input value={gmReplyId} onChange={(e) => setGmReplyId(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Thread id <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmThread} onChange={(e) => setGmThread(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Body
              <textarea
                value={gmReplyBody}
                onChange={(e) => setGmReplyBody(e.target.value)}
                className={`${inputClass} min-h-[100px]`}
                rows={4}
              />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Subject override <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmReplySubj} onChange={(e) => setGmReplySubj(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Cc <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmReplyCc} onChange={(e) => setGmReplyCc(e.target.value)} className={inputClass} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Bcc <span className="text-[var(--text-muted)]">(optional)</span>
              <input value={gmReplyBcc} onChange={(e) => setGmReplyBcc(e.target.value)} className={inputClass} />
            </label>
          </div>
        ) : null}

        {kind === "gmail_send_draft" ? (
          <label className={labelClass}>
            Draft id
            <input value={gmDraftId} onChange={(e) => setGmDraftId(e.target.value)} className={inputClass} />
          </label>
        ) : null}

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
