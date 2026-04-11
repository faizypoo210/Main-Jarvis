import type {
  Approval,
  CommandResponse,
  Mission,
  MissionBundle,
  MissionEvent,
  Receipt,
} from "./types";

const CP = import.meta.env.VITE_CONTROL_PLANE_URL;
if (!CP) throw new Error("VITE_CONTROL_PLANE_URL is not set. Check your .env file.");
const BASE = `${CP}/api/v1`;
const ORIGIN = CP;

/** Public for SSE client and health checks. */
export const CONTROL_PLANE_ORIGIN = ORIGIN;
export const CONTROL_PLANE_API_V1 = BASE;

export type LiveStreamMessage =
  | { type: "mission_event"; event: MissionEvent }
  | { type: "mission"; mission: Mission };

export type StreamConnectOptions = {
  /** HTTP 200 and body available — stream is open before first SSE line. */
  onOpen?: () => void;
  /** Reader finished (server closed or EOF). */
  onStreamEnd?: () => void;
};

/**
 * Fetch-based SSE reader (supports `x-api-key`; EventSource cannot set headers in browsers).
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
          "x-api-key": import.meta.env.VITE_CONTROL_PLANE_API_KEY ?? "",
        },
        signal,
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        onError(new Error(t || `stream HTTP ${res.status}`));
        return;
      }
      options?.onOpen?.();
      const reader = res.body?.getReader();
      if (!reader) {
        onError(new Error("stream has no body"));
        return;
      }
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const block of parts) {
          const dataLine = block.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const raw = dataLine.replace(/^data:\s*/, "").trim();
          if (!raw) continue;
          try {
            const j = JSON.parse(raw) as LiveStreamMessage;
            onMessage(j);
          } catch {
            /* ignore malformed chunk */
          }
        }
      }
      options?.onStreamEnd?.();
    } catch (e: unknown) {
      if (signal.aborted) return;
      onError(e instanceof Error ? e : new Error(String(e)));
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
        "x-api-key": import.meta.env.VITE_CONTROL_PLANE_API_KEY ?? "",
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

export async function getMissionBundle(missionId: string): Promise<MissionBundle> {
  return requestJson<MissionBundle>(
    `${BASE}/missions/${encodeURIComponent(missionId)}/bundle`
  );
}

export async function createCommand(text: string, source: string): Promise<CommandResponse> {
  return requestJson<CommandResponse>(`${BASE}/commands`, {
    method: "POST",
    body: JSON.stringify({ text, source }),
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

export async function getReceipt(id: string): Promise<Receipt> {
  return requestJson<Receipt>(`${BASE}/receipts/${encodeURIComponent(id)}`);
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${ORIGIN}/health`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "x-api-key": import.meta.env.VITE_CONTROL_PLANE_API_KEY ?? "",
      },
    });
    return res.ok;
  } catch {
    return false;
  }
}
