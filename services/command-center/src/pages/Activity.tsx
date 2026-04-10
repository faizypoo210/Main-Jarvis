import { Activity as ActivityIcon } from "lucide-react";

export function Activity() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <ActivityIcon className="h-10 w-10 text-[var(--accent-blue)]" />
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">
        Stream timeline will appear here — connectors, workers, and mission events in one governed feed.
      </p>
    </div>
  );
}
