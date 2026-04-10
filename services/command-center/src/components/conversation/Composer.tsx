import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Mic, Paperclip, Search, Send } from "lucide-react";

export function Composer({
  onVoiceClick,
  onSubmit,
  submitError,
  submitting,
}: {
  onVoiceClick: () => void;
  onSubmit: (text: string) => void | Promise<void>;
  submitError?: string | null;
  submitting?: boolean;
}) {
  const [value, setValue] = useState("");

  const send = async () => {
    const t = value.trim();
    if (!t || submitting) return;
    try {
      await onSubmit(t);
      setValue("");
    } catch {
      /* parent sets submitError */
    }
  };

  const onFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div
      className="flex shrink-0 flex-col gap-1 border-t border-[var(--bg-border)] px-3 py-3 md:px-4"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <form onSubmit={onFormSubmit} className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--text-secondary)] transition-opacity duration-150 ease-linear hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          aria-label="Search"
        >
          <Search className="h-5 w-5" />
        </button>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={submitting}
          placeholder="Send a message..."
          className="min-w-0 flex-1 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none ring-[var(--accent-blue)]/40 focus:ring-2 disabled:opacity-60"
        />
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--text-secondary)] transition-opacity duration-150 ease-linear hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          aria-label="Attach"
        >
          <Paperclip className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={onVoiceClick}
          className="rounded-lg p-2 text-[var(--accent-blue)] transition-opacity duration-150 ease-linear hover:bg-[var(--accent-blue-glow)]"
          aria-label="Voice mode"
        >
          <Mic className="h-5 w-5" />
        </button>
        <button
          type="submit"
          disabled={submitting || !value.trim()}
          className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full bg-[var(--accent-blue)] text-white transition-opacity duration-150 ease-linear hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ boxShadow: "0 0 12px rgba(79,142,247,0.4)" }}
          aria-label="Send"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
      {submitError ? (
        <p className="px-1 text-center text-xs text-[var(--status-red)]">{submitError}</p>
      ) : null}
    </div>
  );
}
