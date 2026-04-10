export function UserMessage({ body }: { body: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[75%] rounded-full border border-[var(--bg-border)] px-4 py-2 text-sm text-[var(--text-primary)]"
        style={{ backgroundColor: "var(--bg-elevated)" }}
      >
        {body}
      </div>
    </div>
  );
}
