/**
 * Builds POST bodies for governed actions from catalog-driven field values.
 * Mirrors control-plane contract; validation messages match catalog hints where useful.
 */

import type {
  GitHubCreateIssueRequestBody,
  GitHubCreatePullRequestRequestBody,
  GitHubMergePullRequestRequestBody,
  GitHubMergeMethod,
  GmailCreateDraftRequestBody,
  GmailCreateReplyDraftRequestBody,
  GmailSendDraftRequestBody,
  GovernedActionKind,
} from "./types";

const REPO_RE = /^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/;

function parseCommaList(s: string): string[] {
  return s.split(/[,]/).map((x) => x.trim()).filter(Boolean);
}

function looseEmailOk(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}

export type GovernedPayloadResult =
  | { ok: true; payload: GitHubCreateIssueRequestBody | GitHubCreatePullRequestRequestBody | GitHubMergePullRequestRequestBody | GmailCreateDraftRequestBody | GmailCreateReplyDraftRequestBody | GmailSendDraftRequestBody }
  | { ok: false; error: string };

export function buildGovernedActionPayload(
  kind: GovernedActionKind,
  values: Record<string, string>,
  base: { requested_by: string; requested_via: "command_center"; source_mission_id: string }
): GovernedPayloadResult {
  const rb = base.requested_by.trim();
  if (!rb) return { ok: false, error: "Enter who is requesting (audit trail)." };

  const common = { ...base, requested_by: rb };

  switch (kind) {
    case "github_create_issue": {
      const repo = (values.repo ?? "").trim();
      const title = (values.title ?? "").trim();
      if (!REPO_RE.test(repo)) return { ok: false, error: "Repo must look like owner/name." };
      if (!title) return { ok: false, error: "Title is required." };
      const labels = parseCommaList(values.labels ?? "").slice(0, 20);
      const body: GitHubCreateIssueRequestBody = {
        ...common,
        repo,
        title,
        body: values.body ?? "",
        ...(labels.length ? { labels } : {}),
      };
      return { ok: true, payload: body };
    }
    case "github_create_pull_request": {
      const repo = (values.repo ?? "").trim();
      const title = (values.title ?? "").trim();
      const baseRef = (values.base ?? "").trim();
      const headRef = (values.head ?? "").trim();
      if (!REPO_RE.test(repo)) return { ok: false, error: "Repo must look like owner/name." };
      if (!baseRef || !headRef) return { ok: false, error: "Base and head are required." };
      if (!title) return { ok: false, error: "Title is required." };
      const draft = (values.draft ?? "true").toLowerCase() === "true";
      const body: GitHubCreatePullRequestRequestBody = {
        ...common,
        repo,
        base: baseRef,
        head: headRef,
        title,
        body: values.body ?? "",
        draft,
      };
      return { ok: true, payload: body };
    }
    case "github_merge_pull_request": {
      const repo = (values.repo ?? "").trim();
      const pn = parseInt((values.pull_number ?? "").trim(), 10);
      const mm = (values.merge_method ?? "squash").trim().toLowerCase() as GitHubMergeMethod;
      if (!REPO_RE.test(repo)) return { ok: false, error: "Repo must look like owner/name." };
      if (!Number.isFinite(pn) || pn < 1) return { ok: false, error: "PR number must be a positive integer." };
      if (!["merge", "squash", "rebase"].includes(mm)) {
        return { ok: false, error: "Merge method must be merge, squash, or rebase." };
      }
      const sha = (values.expected_head_sha ?? "").trim();
      const body: GitHubMergePullRequestRequestBody = {
        ...common,
        repo,
        pull_number: pn,
        merge_method: mm,
        ...(sha ? { expected_head_sha: sha } : {}),
      };
      return { ok: true, payload: body };
    }
    case "gmail_create_draft": {
      const to = parseCommaList(values.to ?? "").filter(looseEmailOk);
      const subj = (values.subject ?? "").trim();
      if (!to.length) return { ok: false, error: "At least one valid To address is required." };
      if (!subj) return { ok: false, error: "Subject is required." };
      const cc = parseCommaList(values.cc ?? "").filter(looseEmailOk);
      const bcc = parseCommaList(values.bcc ?? "").filter(looseEmailOk);
      const body: GmailCreateDraftRequestBody = {
        ...common,
        to,
        subject: subj,
        body: values.body ?? "",
        ...(cc.length ? { cc } : {}),
        ...(bcc.length ? { bcc } : {}),
      };
      return { ok: true, payload: body };
    }
    case "gmail_create_reply_draft": {
      const rid = (values.reply_to_message_id ?? "").trim();
      if (!rid) return { ok: false, error: "Reply-to message id is required." };
      const cc = parseCommaList(values.cc ?? "").filter(looseEmailOk);
      const bcc = parseCommaList(values.bcc ?? "").filter(looseEmailOk);
      const thread = (values.thread_id ?? "").trim();
      const subj = (values.subject ?? "").trim();
      const body: GmailCreateReplyDraftRequestBody = {
        ...common,
        reply_to_message_id: rid,
        body: values.body ?? "",
        ...(thread ? { thread_id: thread } : {}),
        ...(cc.length ? { cc } : {}),
        ...(bcc.length ? { bcc } : {}),
        ...(subj ? { subject: subj } : {}),
      };
      return { ok: true, payload: body };
    }
    case "gmail_send_draft": {
      const did = (values.draft_id ?? "").trim();
      if (!did) return { ok: false, error: "Draft id is required." };
      const body: GmailSendDraftRequestBody = { ...common, draft_id: did };
      return { ok: true, payload: body };
    }
    default:
      return { ok: false, error: "Unknown action." };
  }
}
