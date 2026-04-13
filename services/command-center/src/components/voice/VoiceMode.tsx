import { Bell, Mic, Pause, Play, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { StreamPhase } from "../../contexts/ControlPlaneLiveContext";
import { useControlPlaneLive, usePendingApprovals, useResolveApprovalAction } from "../../hooks/useControlPlane";
import { deriveOperatorMissionPhase } from "../../lib/missionPhase";
import { countPendingElsewhere, getFocusedPendingApproval } from "../../lib/voiceApproval";
import { VoiceApprovalBrief } from "./VoiceApprovalBrief";
import { VoiceOrb, type VoiceOrbState } from "./VoiceOrb";

type WsState = "connecting" | "open" | "closed" | "error";

function getVoiceWsUrl(): string {
  const raw = import.meta.env.VITE_VOICE_SERVER_URL?.trim();
  if (raw) {
    const u = new URL(raw);
    const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${u.host}/ws`;
  }
  const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProto}//${window.location.hostname}:8000/ws`;
}

function pickRecorderMime(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "audio/webm";
}

export function VoiceMode({
  open,
  onClose,
  threadMissionId = null,
  activeMissionCount = 0,
  liveStreamError = null,
  streamPhase = "live",
}: {
  open: boolean;
  onClose: () => void;
  /** Same anchor as thread / right panel / mission detail (`AppShell`). */
  threadMissionId?: string | null;
  activeMissionCount?: number;
  liveStreamError?: string | null;
  streamPhase?: StreamPhase;
}) {
  const navigate = useNavigate();
  const live = useControlPlaneLive();
  const { approvals } = usePendingApprovals();
  const {
    resolve,
    resolvingApprovalId,
    resolveErrorApprovalId,
    clearResolveError,
    recentlyResolvedDecisionFor,
  } = useResolveApprovalAction();

  const mission = threadMissionId ? live.missionById[threadMissionId] ?? null : null;
  const events = threadMissionId ? live.eventsByMissionId[threadMissionId] ?? [] : [];
  const threadMissionStatus = mission?.status ?? null;

  const focusedPending = useMemo(
    () => getFocusedPendingApproval(threadMissionId ?? null, approvals),
    [threadMissionId, approvals]
  );
  const otherPendingCount = useMemo(
    () => countPendingElsewhere(threadMissionId ?? null, approvals),
    [threadMissionId, approvals]
  );
  const focusedPhase = useMemo(
    () =>
      mission
        ? deriveOperatorMissionPhase(mission, events, approvals, null)
        : null,
    [mission, events, approvals]
  );

  const totalPending = useMemo(
    () => approvals.filter((a) => a.status === "pending").length,
    [approvals]
  );

  const [wsState, setWsState] = useState<WsState>("closed");
  const [serverOrb, setServerOrb] = useState<"idle" | "thinking" | "speaking">("idle");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const mimeRef = useRef<string>(pickRecorderMime());
  const audioCtxRef = useRef<AudioContext | null>(null);

  const governanceOrb = Boolean(
    focusedPending || (threadMissionStatus === "awaiting_approval" && !focusedPending)
  );

  const orbState: VoiceOrbState = useMemo(() => {
    if (recording) return "listening";
    if (error) return "error";
    if (serverOrb === "thinking") return "thinking";
    if (serverOrb === "speaking") return "speaking";
    if (governanceOrb) return "awaiting_approval";
    return "idle";
  }, [error, recording, serverOrb, governanceOrb]);

  const label = useMemo(() => {
    if (wsState === "connecting") return "Connecting...";
    if (recording) return "Listening...";
    if (serverOrb === "thinking") return "Thinking...";
    if (serverOrb === "speaking") return "Speaking...";
    if (governanceOrb) return "Governance";
    if (wsState === "open") return "Jarvis";
    return "Disconnected";
  }, [wsState, recording, serverOrb, governanceOrb]);

  const missionLoopLine = useMemo(() => {
    if (!mission || !focusedPhase) return null;
    if (focusedPending) return null;
    return focusedPhase.label;
  }, [mission, focusedPhase, focusedPending]);

  const stopRecordingTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    setRecording(false);
  }, []);

  const stopRecordingSend = useCallback(() => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
    } else {
      stopRecordingTracks();
    }
  }, [stopRecordingTracks]);

  const handleResolve = useCallback(
    (decision: "approved" | "denied") => {
      if (!focusedPending) return;
      void resolve(focusedPending.id, decision, {
        onSuccess: async () => {
          if (threadMissionId?.trim()) {
            await live.bootstrapMission(threadMissionId);
          }
        },
      });
    },
    [focusedPending, resolve, live, threadMissionId]
  );

  const voiceResolving = Boolean(
    focusedPending && resolvingApprovalId === focusedPending.id
  );
  const voiceResolveError = Boolean(
    focusedPending && resolveErrorApprovalId === focusedPending.id
  );
  const voiceRecentlyResolvedDecision = focusedPending
    ? recentlyResolvedDecisionFor(focusedPending.id)
    : null;

  const handleViewMission = useCallback(() => {
    if (!threadMissionId?.trim()) return;
    navigate(`/missions/${encodeURIComponent(threadMissionId)}`);
    onClose();
  }, [navigate, onClose, threadMissionId]);

  useEffect(() => {
    if (!open) return;

    setTranscript("");
    setReply("");
    setError(null);
    clearResolveError();
    setWsState("connecting");
    setServerOrb("idle");

    const surfaceSessionId = crypto.randomUUID();
    const base = getVoiceWsUrl();
    const u = new URL(base);
    u.searchParams.set("surface_session_id", surfaceSessionId);
    const tm = threadMissionId?.trim();
    if (tm) {
      u.searchParams.set("thread_mission_id", tm);
    }
    let cancelled = false;
    const ws = new WebSocket(u.toString());
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      if (cancelled) return;
      setWsState("open");
      setError(null);
    };

    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      try {
        const data = JSON.parse(ev.data) as {
          type?: string;
          state?: string;
          text?: string;
          message?: string;
          audio_b64?: string;
          kind?: string;
        };
        const t = data.type;
        if (t === "status" && data.state) {
          const s = data.state;
          if (s === "thinking" || s === "speaking" || s === "idle") {
            setServerOrb(s);
          }
          return;
        }
        if (t === "heard" && typeof data.text === "string") {
          setTranscript(data.text);
          setError(null);
          return;
        }
        if (t === "reply" && typeof data.text === "string") {
          setReply(data.text);
          setError(null);
          return;
        }
        if (t === "tts" && typeof data.audio_b64 === "string") {
          const audioB64 = data.audio_b64;
          void (async () => {
            try {
              let ctx = audioCtxRef.current;
              if (!ctx) {
                ctx = new AudioContext();
                audioCtxRef.current = ctx;
              }
              const binary = atob(audioB64);
              const len = binary.length;
              const bytes = new Uint8Array(len);
              for (let i = 0; i < len; i++) {
                bytes[i] = binary.charCodeAt(i);
              }
              const audioBuffer = await ctx.decodeAudioData(
                bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
              );
              const src = ctx.createBufferSource();
              src.buffer = audioBuffer;
              src.connect(ctx.destination);
              src.start();
            } catch (e) {
              console.warn("VoiceMode TTS playback failed:", e);
            }
          })();
          return;
        }
        if (t === "error") {
          const msg = typeof data.message === "string" ? data.message : "Voice error";
          setError(msg);
          return;
        }
      } catch {
        /* ignore non-JSON */
      }
    };

    ws.onerror = () => {
      if (cancelled) return;
      setWsState("error");
      setError("WebSocket connection failed");
    };

    ws.onclose = () => {
      if (cancelled) return;
      wsRef.current = null;
      setWsState("closed");
    };

    return () => {
      cancelled = true;
      const rec = mediaRecorderRef.current;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        rec.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      mediaRecorderRef.current = null;
      chunksRef.current = [];
      setRecording(false);

      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, [open, clearResolveError, threadMissionId]);

  const startRecording = useCallback(async () => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      setError("Not connected to voice server");
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      mimeRef.current = pickRecorderMime();
      chunksRef.current = [];
      let rec: MediaRecorder;
      try {
        rec = new MediaRecorder(stream, { mimeType: mimeRef.current });
      } catch {
        rec = new MediaRecorder(stream);
        mimeRef.current = rec.mimeType || "audio/webm";
      }
      mediaRecorderRef.current = rec;

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeRef.current });
        chunksRef.current = [];
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        mediaRecorderRef.current = null;
        setRecording(false);

        if (wsRef.current?.readyState === WebSocket.OPEN && blob.size > 0) {
          wsRef.current.send(blob);
        }
      };

      rec.start();
      setRecording(true);
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "Microphone access denied or unavailable";
      setError(msg);
      setRecording(false);
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (recording) {
      stopRecordingSend();
    } else {
      void startRecording();
    }
  }, [recording, startRecording, stopRecordingSend]);

  const handleClose = useCallback(() => {
    stopRecordingSend();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
    setWsState("closed");
    onClose();
  }, [onClose, stopRecordingSend]);

  if (!open) return null;

  const canUseMic = wsState === "open";
  const showGlobalPendingLine = totalPending > 0 && !focusedPending;

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col bg-black"
      role="dialog"
      aria-modal="true"
      aria-label="Voice mode"
    >
      <div className="flex items-center justify-between px-4 py-4 md:px-8">
        <div className="flex items-center gap-2">
          <VoiceOrb state={orbState} size="sm" />
          <span className="font-display text-sm font-semibold tracking-wide text-[var(--text-primary)]">
            JARVIS
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-white/5"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
          </button>
          <div className="h-8 w-8 rounded-full bg-[var(--bg-surface)] ring-1 ring-[var(--bg-border)]" />
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 pb-8">
        <p className="font-display text-lg font-semibold text-[var(--accent-blue)] md:text-xl">{label}</p>
        <div className="mt-2 max-w-sm space-y-1 text-center text-xs">
          {streamPhase === "reconnecting" ? (
            <p className="text-[var(--text-muted)]">Live updates reconnecting.</p>
          ) : null}
          {streamPhase === "offline" ? (
            <p className="text-[var(--status-amber)]/85">
              Live stream offline — periodic sync
              {liveStreamError ? ` (${liveStreamError})` : ""}.
            </p>
          ) : null}
          {focusedPending ? (
            <p className="text-white/55">Decision required on this mission.</p>
          ) : null}
          {showGlobalPendingLine ? (
            <p className="text-[var(--status-amber)]/90">
              {threadMissionId?.trim()
                ? totalPending === 1
                  ? "One approval pending elsewhere."
                  : `${totalPending} approvals pending elsewhere.`
                : totalPending === 1
                  ? "One approval pending."
                  : `${totalPending} approvals pending.`}
            </p>
          ) : null}
          {activeMissionCount > 0 ? (
            <p className="text-[var(--text-muted)]">
              {activeMissionCount === 1 ? "1 active mission." : `${activeMissionCount} active missions.`}
            </p>
          ) : null}
          {missionLoopLine ? <p className="text-white/50">{missionLoopLine}</p> : null}
        </div>

        {focusedPending ? (
          <VoiceApprovalBrief
            approval={focusedPending}
            otherPendingCount={otherPendingCount}
            onViewMission={handleViewMission}
            onApprove={() => void handleResolve("approved")}
            onDeny={() => void handleResolve("denied")}
            resolving={voiceResolving}
            resolveError={voiceResolveError}
            recentlyResolvedDecision={voiceRecentlyResolvedDecision}
          />
        ) : null}

        <div className="mt-8">
          <VoiceOrb state={orbState} size="lg" />
        </div>
        <div className="mt-10 max-w-md space-y-3 text-center text-sm leading-relaxed">
          {transcript ? (
            <p className="text-[var(--accent-blue)]/90">{transcript}</p>
          ) : null}
          {reply ? <p className="text-[var(--text-primary)]">{reply}</p> : null}
          {error ? <p className="text-red-400">{error}</p> : null}
        </div>
      </div>

      <div className="flex items-center justify-center gap-8 border-t border-white/10 px-6 py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
        <button
          type="button"
          disabled={!canUseMic}
          onClick={() => void toggleRecording()}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label={recording ? "Pause recording" : "Start recording"}
        >
          {recording ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </button>
        <button
          type="button"
          disabled={!recording}
          onClick={() => stopRecordingSend()}
          className="text-sm font-medium text-[var(--text-secondary)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Stop
        </button>
        <button
          type="button"
          disabled={!canUseMic}
          onClick={() => void toggleRecording()}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/30 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Microphone"
        >
          <Mic className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={handleClose}
          className="flex h-12 w-12 items-center justify-center rounded-full border border-white/20 text-white hover:bg-white/10"
          aria-label="Close voice mode"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
