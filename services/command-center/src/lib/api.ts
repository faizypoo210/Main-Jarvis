import type {
  ActivityFeedCategory,
  Approval,
  ApprovalBundleResponse,
  CommandResponse,
  GitHubCreateIssueRequestBody,
  GitHubCreatePullRequestRequestBody,
  GitHubMergePullRequestRequestBody,
  GmailCreateDraftRequestBody,
  GmailCreateReplyDraftRequestBody,
  GmailSendDraftRequestBody,
  GovernedActionCatalogResponse,
  HeartbeatOperatorResponse,
  MemoryCountsResponse,
  MemoryCreateBody,
  MemoryItemRead,
  MemoryListResponse,
  MemoryPatchBody,
  MissionMemoryPromoteBody,
  Mission,
  MissionBundle,
  MissionEvent,
  OperatorActivityResponse,
  OperatorCostEventsResponse,
  OperatorCostGuardrailsResponse,
  OperatorInboxResponse,
  OperatorIntegrationsResponse,
  OperatorUsageResponse,
  OperatorValueEvalsResponse,
  OperatorWorkersResponse,
  Receipt,
  SystemHealthResponse,
} from "./types";

/**
 * Empty VITE_CONTROL_PLANE_URL → same-origin /api/v1 (Vite dev proxy injects x-api-key; production: use nginx or similar).
 * Non-empty → absolute API origin (cross-origin: no browser secret; server must use local_trusted or an edge proxy).
 */
const cpEnv = (import.meta.env.VITE_CONTROL_PLANE_URL ?? "").trim();
const CP = cpEnv === "" ? "" : cpEnv;
const BASE = CP ? `${CP.replace(/\/$/, "")}/api/v1` : "/api/v1";
const ORIGIN = CP ? CP.replace(/\/$/, "") : "";

/** Public for hooks that need the stream path segment. */
export const CONTROL_PLANE_API_V1 = BASE;
/** Origin for health checks (relative in dev). */
export const CONTROL_PLANE_ORIGIN = ORIGIN;

export type LiveStreamMessage =
  | { type: "mission_event"; event: MissionEvent }
  | { type: "mission"; mission: Mission };

export type StreamConnectOptions = {
  /** HTTP 200 and body available — stream is open before first SSE line. */
  onOpen?: () => void;
  /** Reader finished (server closed or EOF). */
  onStreamEnd?: () => void;
};

/** Split buffered SSE into complete blocks; ignores comment-only blocks (e.g. `: keepalive`). */
export function parseSseDataPayloads(buffer: string): { payloads: string[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const payloads: string[] = [];
  for (const block of parts) {
    const dataLine = block.split("\n").find((l) => l.startsWith("data:"));
    if (!dataLine) continue;
    const raw = dataLine.replace(/^data:\s*/, "").trim();
    if (raw) payloads.push(raw);
  }
  return { payloads, rest };
}

function sseHttpErrorMessage(res: Response, body: string): string {
  const base = `SSE HTTP ${res.status} ${res.statusText || ""}`.trim();
  let hint = "";
  if (res.status === 401 || res.status === 403) {
    hint =
      " — auth failed (dev: CONTROL_PLANE_API_KEY must match control plane; Vite injects x-api-key)";
  } else if (res.status >= 500) {
    hint = " — server error";
  }
  const tail = body.trim() ? `: ${body.trim().slice(0, 200)}` : "";
  return `${base}${hint}${tail}`;
}

function wrapSseFetchError(e: unknown): Error {
  if (e instanceof TypeError) {
    return new Error(`SSE network error (${e.message})`);
  }
  return e instanceof Error ? e : new Error(String(e));
}

/**
 * Fetch-based SSE reader (dev proxy injects x-api-key; production should use same-origin + edge auth).
 */
export function connectControlPlaneStream(
  onMessage: (msg: LiveStreamMessage) => void,
  onError: (err: Error) => void,
  signal: AbortSignal,
  options?: StreamConnectOptions
): void {
  const url = `${BASE}/updates/stream`;
  void (async () => {
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: {
          Accept: "text/event-stream",
        },
        signal,
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        onError(new Error(sseHttpErrorMessage(res, t)));
        return;
      }
      options?.onOpen?.();
      const reader = res.body?.getReader();
      if (!reader) {
        onError(new Error("SSE stream has no body (unexpected response)"));
        return;
      }
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const { payloads, rest } = parseSseDataPayloads(buf);
        buf = rest;
        for (const raw of payloads) {
          try {
            const j = JSON.parse(raw) as LiveStreamMessage;
            onMessage(j);
          } catch {
            /* malformed JSON in data: line — skip without tearing down the stream */
          }
        }
      }
      options?.onStreamEnd?.();
    } catch (e: unknown) {
      if (signal.aborted) return;
      onError(wrapSseFetchError(e));
    }
  })();
}

function isNetworkError(e: unknown): boolean {
  return e instanceof TypeError && typeof e.message === "string";
}

async function readErrorBody(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) return `HTTP ${res.status}`;
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return JSON.stringify(j.detail);
  } catch {
    /* not JSON */
  }
  return text;
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) {
    throw new Error(`Empty response (${res.status})`);
  }
  return JSON.parse(text) as T;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch (e: unknown) {
    if (isNetworkError(e)) {
      throw new Error("Control plane unreachable");
    }
    throw e;
  }
  if (!res.ok) {
    const detail = await readErrorBody(res);
    throw new Error(detail);
  }
  return parseJson<T>(res);
}

export async function getMissions(params?: {
  status?: string;
  created_by?: string;
  limit?: number;
  offset?: number;
}): Promise<Mission[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.created_by) q.set("created_by", params.created_by);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const path = `${BASE}/missions${q.toString() ? `?${q}` : ""}`;
  return requestJson<Mission[]>(path);
}

export async function getMission(id: string): Promise<Mission> {
  return requestJson<Mission>(`${BASE}/missions/${encodeURIComponent(id)}`);
}

export async function getMissionEvents(missionId: string): Promise<MissionEvent[]> {
  return requestJson<MissionEvent[]>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/events`
  );
}

export async function getMissionApprovals(missionId: string): Promise<Approval[]> {
  return requestJson<Approval[]>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/approvals`
  );
}

export async function getMissionReceipts(missionId: string): Promise<Receipt[]> {
  return requestJson<Receipt[]>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/receipts`
  );
}

export async function getReceipts(params?: { limit?: number; offset?: number }): Promise<Receipt[]> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return requestJson<Receipt[]>(`${BASE}/receipts${qs ? `?${qs}` : ""}`);
}

export async function getMissionBundle(missionId: string): Promise<MissionBundle> {
  return requestJson<MissionBundle>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/bundle`
  );
}

const COMMAND_SUBMIT_TIMEOUT_MS = 45_000;

export async function createCommand(text: string, source: string): Promise<CommandResponse> {
  const signal =
    typeof AbortSignal !== "undefined" && "timeout" in AbortSignal
      ? AbortSignal.timeout(COMMAND_SUBMIT_TIMEOUT_MS)
      : undefined;
  return requestJson<CommandResponse>(`${BASE}/commands`, {
    method: "POST",
    body: JSON.stringify({ text, source }),
    ...(signal ? { signal } : {}),
  });
}

export async function getPendingApprovals(): Promise<Approval[]> {
  return requestJson<Approval[]>(`${BASE}/approvals/pending`);
}

export async function createApproval(data: {
  mission_id: string;
  action_type: string;
  risk_class: string;
  reason?: string;
  requested_by: string;
  requested_via: string;
}): Promise<Approval> {
  return requestJson<Approval>(`${BASE}/approvals`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function resolveApproval(
  id: string,
  decision: {
    decision: "approved" | "denied";
    decided_by: string;
    decided_via: string;
    decision_notes?: string;
  }
): Promise<Approval> {
  return requestJson<Approval>(`${BASE}/approvals/${encodeURIComponent(id)}/decision`, {
    method: "POST",
    body: JSON.stringify({
      decision: decision.decision,
      decided_by: decision.decided_by,
      decided_via: decision.decided_via,
      decision_notes: decision.decision_notes ?? null,
    }),
  });
}

export async function getApprovalBundle(approvalId: string): Promise<ApprovalBundleResponse> {
  return requestJson<ApprovalBundleResponse>(
    `${BASE}/approvals/${encodeURIComponent(approvalId)}/bundle`
  );
}

export async function getReceipt(id: string): Promise<Receipt> {
  return requestJson<Receipt>(`${BASE}/receipts/${encodeURIComponent(id)}`);
}

export async function checkHealth(): Promise<boolean> {
  try {
    const healthUrl = CP ? `${ORIGIN}/health` : "/health";
    const res = await fetch(healthUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getSystemHealth(): Promise<SystemHealthResponse> {
  return requestJson<SystemHealthResponse>(`${BASE}/system/health`);
}

export async function getOperatorUsage(): Promise<OperatorUsageResponse> {
  return requestJson<OperatorUsageResponse>(`${BASE}/operator/usage`);
}

export async function getOperatorCostGuardrails(): Promise<OperatorCostGuardrailsResponse> {
  return requestJson<OperatorCostGuardrailsResponse>(`${BASE}/operator/cost-guardrails`);
}

export async function getOperatorCostEvents(params?: {
  provider?: string;
  cost_status?: string;
  mission_id?: string;
  limit?: number;
  offset?: number;
}): Promise<OperatorCostEventsResponse> {
  const q = new URLSearchParams();
  if (params?.provider) q.set("provider", params.provider);
  if (params?.cost_status) q.set("cost_status", params.cost_status);
  if (params?.mission_id) q.set("mission_id", params.mission_id);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return requestJson<OperatorCostEventsResponse>(`${BASE}/operator/cost-events${qs ? `?${qs}` : ""}`);
}

export async function getOperatorWorkers(): Promise<OperatorWorkersResponse> {
  return requestJson<OperatorWorkersResponse>(`${BASE}/operator/workers`);
}

export async function getOperatorIntegrations(): Promise<OperatorIntegrationsResponse> {
  return requestJson<OperatorIntegrationsResponse>(`${BASE}/operator/integrations`);
}

export async function getMemoryCounts(): Promise<MemoryCountsResponse> {
  return requestJson<MemoryCountsResponse>(`${BASE}/operator/memory/counts`);
}

export async function getOperatorHeartbeat(): Promise<HeartbeatOperatorResponse> {
  return requestJson<HeartbeatOperatorResponse>(`${BASE}/operator/heartbeat`);
}

export async function getMemoryList(params?: {
  memory_type?: string;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<MemoryListResponse> {
  const q = new URLSearchParams();
  if (params?.memory_type) q.set("memory_type", params.memory_type);
  if (params?.status) q.set("status", params.status);
  if (params?.q) q.set("q", params.q);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return requestJson<MemoryListResponse>(`${BASE}/operator/memory${qs ? `?${qs}` : ""}`);
}

export async function getMemory(id: string): Promise<MemoryItemRead> {
  return requestJson<MemoryItemRead>(
    `${BASE}/operator/memory/${encodeURIComponent(id)}`
  );
}

export async function createMemory(data: MemoryCreateBody): Promise<MemoryItemRead> {
  return requestJson<MemoryItemRead>(`${BASE}/operator/memory`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function patchMemory(id: string, data: MemoryPatchBody): Promise<MemoryItemRead> {
  return requestJson<MemoryItemRead>(
    `${BASE}/operator/memory/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    }
  );
}

export async function promoteMemoryFromMission(
  data: MissionMemoryPromoteBody
): Promise<MemoryItemRead> {
  return requestJson<MemoryItemRead>(`${BASE}/operator/memory/promote-from-mission`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getOperatorActionCatalog(): Promise<GovernedActionCatalogResponse> {
  return requestJson<GovernedActionCatalogResponse>(`${BASE}/operator/action-catalog`);
}

export async function getOperatorEvals(params?: {
  window_hours?: number;
  group_by?: "day";
}): Promise<OperatorValueEvalsResponse> {
  const q = new URLSearchParams();
  if (params?.window_hours != null) q.set("window_hours", String(params.window_hours));
  if (params?.group_by) q.set("group_by", params.group_by);
  const qs = q.toString();
  return requestJson<OperatorValueEvalsResponse>(
    `${BASE}/operator/evals${qs ? `?${qs}` : ""}`
  );
}

export async function getOperatorActivity(params?: {
  limit?: number;
  before?: string;
  mission_id?: string;
  category?: ActivityFeedCategory;
}): Promise<OperatorActivityResponse> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.before) q.set("before", params.before);
  if (params?.mission_id) q.set("mission_id", params.mission_id);
  if (params?.category) q.set("category", params.category);
  const qs = q.toString();
  return requestJson<OperatorActivityResponse>(
    `${BASE}/operator/activity${qs ? `?${qs}` : ""}`
  );
}

export async function getOperatorInbox(params?: {
  group?: string;
  severity?: string;
  source_kind?: string;
  status?: string;
  limit?: number;
}): Promise<OperatorInboxResponse> {
  const q = new URLSearchParams();
  if (params?.group) q.set("group", params.group);
  if (params?.severity) q.set("severity", params.severity);
  if (params?.source_kind) q.set("source_kind", params.source_kind);
  if (params?.status) q.set("status", params.status);
  if (params?.limit != null) q.set("limit", String(params.limit));
  const qs = q.toString();
  return requestJson<OperatorInboxResponse>(`${BASE}/operator/inbox${qs ? `?${qs}` : ""}`);
}

export async function postOperatorInboxAcknowledge(itemKey: string): Promise<{ ok: boolean; item_key: string }> {
  const enc = encodeURIComponent(itemKey);
  return requestJson<{ ok: boolean; item_key: string }>(
    `${BASE}/operator/inbox/${enc}/acknowledge`,
    { method: "POST", body: "{}" }
  );
}

export async function postOperatorInboxSnooze(
  itemKey: string,
  minutes: number
): Promise<{ ok: boolean; item_key: string }> {
  const enc = encodeURIComponent(itemKey);
  return requestJson<{ ok: boolean; item_key: string }>(
    `${BASE}/operator/inbox/${enc}/snooze`,
    { method: "POST", body: JSON.stringify({ minutes }) }
  );
}

export async function postOperatorInboxDismiss(itemKey: string): Promise<{ ok: boolean; item_key: string }> {
  const enc = encodeURIComponent(itemKey);
  return requestJson<{ ok: boolean; item_key: string }>(
    `${BASE}/operator/inbox/${enc}/dismiss`,
    { method: "POST", body: "{}" }
  );
}

/** Governed integration workflows — each POST creates a pending approval (no immediate external side effects until approved). */
export async function postGithubCreateIssue(
  missionId: string,
  body: GitHubCreateIssueRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/github/create-issue`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function postGithubCreatePullRequest(
  missionId: string,
  body: GitHubCreatePullRequestRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/github/create-pull-request`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function postGithubMergePullRequest(
  missionId: string,
  body: GitHubMergePullRequestRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/github/merge-pull-request`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function postGmailCreateDraft(
  missionId: string,
  body: GmailCreateDraftRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/gmail/create-draft`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function postGmailCreateReplyDraft(
  missionId: string,
  body: GmailCreateReplyDraftRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/gmail/create-reply-draft`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function postGmailSendDraft(
  missionId: string,
  body: GmailSendDraftRequestBody
): Promise<Approval> {
  return requestJson<Approval>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/integrations/gmail/send-draft`,
    { method: "POST", body: JSON.stringify(body) }
  );
}
