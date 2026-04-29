interface AgentActivityProps {
  label: string;
}
export function AgentActivity({ label }: AgentActivityProps) {
  return (
    <div className="ml-9 flex items-center gap-3 py-1">
      <div className="flex items-center gap-[3px]">
        <span className="agent-wave-dot" />
        <span className="agent-wave-dot" />
        <span className="agent-wave-dot" />
      </div>
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
    </div>
  );
}
