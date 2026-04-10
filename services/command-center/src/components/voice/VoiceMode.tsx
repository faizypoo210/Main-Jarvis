import { Bell, Mic, Play, X } from "lucide-react";
import { VoiceOrb, type VoiceOrbState } from "./VoiceOrb";

export function VoiceMode({
  open,
  onClose,
  state,
  label,
  transcript,
}: {
  open: boolean;
  onClose: () => void;
  state: VoiceOrbState;
  label: string;
  transcript: string;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col bg-black"
      role="dialog"
      aria-modal="true"
      aria-label="Voice mode"
    >
      <div className="flex items-center justify-between px-4 py-4 md:px-8">
        <div className="flex items-center gap-2">
          <VoiceOrb state="idle" size="sm" />
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

      <div className="flex flex-1 flex-col items-center justify-center px-6 pb-12">
        <p className="font-display text-lg font-semibold text-[var(--accent-blue)] md:text-xl">{label}</p>
        <div className="mt-8">
          <VoiceOrb state={state} size="lg" />
        </div>
        <p className="mt-10 max-w-md text-center text-sm leading-relaxed text-[var(--text-secondary)]">
          {transcript}
        </p>
      </div>

      <div className="flex items-center justify-center gap-8 border-t border-white/10 px-6 py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
        <button
          type="button"
          className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/15"
          aria-label="Play or pause"
        >
          <Play className="h-5 w-5" />
        </button>
        <button type="button" className="text-sm font-medium text-[var(--text-secondary)] hover:text-white">
          Stop
        </button>
        <button
          type="button"
          className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/30"
          aria-label="Microphone"
        >
          <Mic className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex h-12 w-12 items-center justify-center rounded-full border border-white/20 text-white hover:bg-white/10"
          aria-label="Close voice mode"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
