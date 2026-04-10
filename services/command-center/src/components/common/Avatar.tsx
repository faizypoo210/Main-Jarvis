export function Avatar({ size = 24 }: { size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full bg-[var(--accent-blue-glow)] ring-1 ring-[var(--accent-blue)]/30"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <div
        className="rounded-full bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-blue-dim)]"
        style={{ width: size * 0.55, height: size * 0.55 }}
      />
    </div>
  );
}
