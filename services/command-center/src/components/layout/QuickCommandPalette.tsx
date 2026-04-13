import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";

type QuickCommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  /** Submit command text; throw or reject on failure — surfaced in the palette. */
  onSubmit: (text: string) => Promise<void>;
};

/**
 * Global quick mission intake: same control-plane path as the Overview composer, without replacing the full thread.
 */
export function QuickCommandPalette({ open, onClose, onSubmit }: QuickCommandPaletteProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setText("");
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const t = text.trim();
      if (!t || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        await onSubmit(t);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
    },
    [onSubmit, submitting, text]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/55 p-4 pt-[min(20vh,8rem)]"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${id}-title`}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)] p-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={`${id}-title`} className="text-sm font-semibold text-[var(--text-primary)]">
          Quick command
        </h2>
        <p className="mt-1 text-[10px] leading-relaxed text-[var(--text-muted)]">
          Sends a short command to the control plane and opens Overview with that mission in focus.
        </p>
        <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What should Jarvis do?"
            disabled={submitting}
            autoComplete="off"
            className="w-full rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-3 py-2.5 font-mono text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
            aria-label="Command text"
          />
          {error ? (
            <p className="text-xs text-[var(--status-amber)]" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-[var(--bg-border)] px-3 py-2 text-xs text-[var(--text-muted)]"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !text.trim()}
              className="rounded-lg border border-[var(--accent-blue)]/50 bg-[var(--accent-blue)]/15 px-3 py-2 text-xs font-medium text-[var(--accent-blue)] disabled:opacity-50"
            >
              {submitting ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** Register global shortcuts: Cmd/Ctrl+K toggles; "/" opens when focus is not in an editable field. */
export function useQuickCommandShortcuts(
  isOpen: boolean,
  onOpen: () => void,
  onClose: () => void
) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        if (e.key.toLowerCase() === "k") {
          e.preventDefault();
          if (isOpen) onClose();
          else onOpen();
        }
        return;
      }
      if (e.key === "/") {
        if (isOpen) return;
        const el = document.activeElement;
        if (el instanceof HTMLElement) {
          const tag = el.tagName;
          if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable) {
            return;
          }
        }
        e.preventDefault();
        onOpen();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onOpen, onClose]);
}
