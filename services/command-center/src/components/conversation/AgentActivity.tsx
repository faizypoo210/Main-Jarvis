export function AgentActivity({ text }: { text: string }) {
  return (
    <div className="ml-9 flex items-center gap-2 py-1">
      <span className="agent-dot-pulse h-2 w-2 shrink-0 rounded-full bg-[var(--accent-blue)]" />
      <span className="text-sm italic text-[var(--text-muted)]">{text}</span>
    </div>
  );
}
