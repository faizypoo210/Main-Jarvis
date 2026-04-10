import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../lib/api";
import { AgentActivity } from "./AgentActivity";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";
import { UserMessage } from "./UserMessage";

type ThreadItem =
  | {
      id: string;
      kind: "jarvis";
      body: string;
      time: string;
      routing?: string;
      missionIdTag?: string;
    }
  | { id: string; kind: "user"; body: string }
  | { id: string; kind: "activity"; text: string };

const stagger = (i: number): CSSProperties => ({
  animationDelay: `${i * 50}ms`,
});

const INITIAL: ThreadItem[] = [
  {
    id: "seed-0",
    kind: "jarvis",
    body: "Got it. I'll start coordinating the offsite event for next month. I'll find a venue, plan the agenda, and update you as I go.",
    time: "10:02",
    routing: "→ Spar team",
  },
  { id: "seed-1", kind: "activity", text: "Finding venues that fit your team size..." },
  {
    id: "seed-2",
    kind: "jarvis",
    body: "I've found a few venue options that can accommodate your team. Would you like to see them, or should I proceed with one?",
    time: "10:03",
  },
  { id: "seed-3", kind: "user", body: "Proceed with the top pick and send invites" },
  {
    id: "seed-4",
    kind: "jarvis",
    body: "Understood. I'll book the top pick and start sending invitations. What dates should I use?",
    time: "10:04",
  },
];

const PHASE2_POLL_MS = 2000;
const PHASE2_MAX_TICKS = 90;

export function ConversationThread({ onVoiceClick }: { onVoiceClick: () => void }) {
  const [items, setItems] = useState<ThreadItem[]>(INITIAL);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPhase2Poll = useCallback((missionId: string) => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    let ticks = 0;
    pollRef.current = setInterval(async () => {
      ticks += 1;
      if (ticks > PHASE2_MAX_TICKS) {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        return;
      }
      try {
        const [mission, events] = await Promise.all([
          api.getMission(missionId),
          api.getMissionEvents(missionId),
        ]);
        const receipt = [...events]
          .reverse()
          .find(
            (e) =>
              e.event_type === "receipt_recorded" &&
              e.payload &&
              typeof (e.payload as Record<string, unknown>).summary === "string" &&
              String((e.payload as Record<string, unknown>).summary).trim().length > 0
          );
        if (receipt?.payload) {
          const text = String(
            (receipt.payload as Record<string, unknown>).summary
          ).trim();
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setItems((prev) => [
            ...prev,
            {
              id: `exec-${missionId}-${Date.now()}`,
              kind: "jarvis",
              body: text,
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              missionIdTag: missionId,
            },
          ]);
          return;
        }
        if (mission.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setItems((prev) => [
            ...prev,
            {
              id: `exec-fail-${missionId}-${Date.now()}`,
              kind: "jarvis",
              body: "Mission execution failed.",
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              missionIdTag: missionId,
            },
          ]);
        }
      } catch {
        /* next tick */
      }
    }, PHASE2_POLL_MS);
  }, []);

  const handleSubmit = useCallback(async (text: string) => {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const res = await api.createCommand(text, "command_center");
      const uid = crypto.randomUUID();
      const activityId = `activity-${uid}`;
      setItems((prev) => [
        ...prev,
        { id: `u-${uid}`, kind: "user", body: text },
        { id: activityId, kind: "activity", text: "Processing your request..." },
      ]);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => {
        timeoutRef.current = null;
        const mid = res.mission_id;
        setItems((prev) => {
          const without = prev.filter((x) => x.id !== activityId);
          return [
            ...without,
            {
              id: `j-${uid}`,
              kind: "jarvis",
              body: "Got it. Mission created — I'll update you as work progresses.",
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              missionIdTag: mid,
            },
          ];
        });
        startPhase2Poll(mid);
      }, 1500);
    } catch {
      setSubmitError("Could not reach Jarvis — try again");
    } finally {
      setSubmitting(false);
    }
  }, [startPhase2Poll]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 pb-4">
          {items.map((item, index) => {
            if (item.kind === "user") {
              return (
                <div key={item.id}>
                  <UserMessage body={item.body} />
                </div>
              );
            }
            if (item.kind === "activity") {
              return (
                <div key={item.id}>
                  <AgentActivity text={item.text} />
                </div>
              );
            }
            const delay = index < 5 ? stagger(index) : undefined;
            return (
              <div
                key={item.id}
                className={
                  index < 5
                    ? "animate-[fade-up_250ms_ease_forwards] opacity-0 [animation-fill-mode:forwards]"
                    : undefined
                }
                style={delay}
              >
                <MessageBubble
                  body={item.body}
                  time={item.time}
                  routing={item.routing}
                  missionIdTag={item.missionIdTag}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="pb-[env(safe-area-inset-bottom,0px)]">
        <Composer
          onVoiceClick={onVoiceClick}
          onSubmit={handleSubmit}
          submitError={submitError}
          submitting={submitting}
        />
      </div>
    </div>
  );
}
