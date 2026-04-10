import { Avatar } from "../common/Avatar";

export function MessageBubble({
  body,
  time,
  routing,
  missionIdTag,
}: {
  body: string;
  time: string;
  routing?: string;
  missionIdTag?: string;
}) {
  return (
    <div className="flex max-w-[75%] gap-3">
      <Avatar size={24} />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-baseline gap-2">
          <span className="font-display text-sm font-semibold text-[var(--text-primary)]">Jarvis</span>
          <span className="font-mono text-[10px] text-[var(--text-muted)]">{time}</span>
          {routing ? (
            <span className="text-[10px] text-[var(--text-secondary)]">{routing}</span>
          ) : null}
        </div>
        <div
          className="rounded-xl border border-solid border-[var(--bg-border)] py-[14px] pl-[18px] pr-[18px] text-sm leading-relaxed text-[var(--text-primary)]"
          style={{ backgroundColor: "var(--bg-surface)" }}
        >
          {body}
          {missionIdTag ? (
            <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">{missionIdTag}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
