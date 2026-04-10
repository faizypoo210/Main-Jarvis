export type VoiceOrbState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "awaiting_approval"
  | "error";

const animationClass: Record<VoiceOrbState, string> = {
  idle: "voice-orb-idle",
  listening: "voice-orb-listening",
  thinking: "voice-orb-thinking",
  speaking: "voice-orb-speaking",
  awaiting_approval: "voice-orb-awaiting_approval",
  error: "voice-orb-error",
};

export function VoiceOrb({
  state,
  size = "sm",
}: {
  state: VoiceOrbState;
  size?: "sm" | "lg";
}) {
  const dim = size === "lg" ? 220 : 32;
  const anim = animationClass[state];

  return (
    <div
      className={`relative flex items-center justify-center rounded-full ${anim}`}
      style={{ width: dim, height: dim }}
    >
      <div
        className="absolute inset-0 rounded-full opacity-90"
        style={{
          background:
            state === "error"
              ? "radial-gradient(circle at 50% 50%, #450a0a 0%, #0a0a0a 55%, #1a0505 100%)"
              : state === "awaiting_approval"
                ? "radial-gradient(circle at 50% 50%, #422006 0%, #0a0a0a 50%, #1c1917 100%)"
                : "radial-gradient(circle at 50% 50%, #0a0a12 0%, #07080d 45%, #0f172a 100%)",
          boxShadow:
            state === "error"
              ? "0 0 24px rgba(248,113,113,0.25)"
              : "0 0 32px rgba(79,142,247,0.2), inset 0 0 40px rgba(79,142,247,0.08)",
        }}
      />
      <div
        className="orb-gradient-spin absolute inset-[12%] rounded-full opacity-80"
        style={{
          background:
            "conic-gradient(from 180deg, rgba(79,142,247,0.15), rgba(255,255,255,0.08), rgba(79,142,247,0.25), rgba(79,142,247,0.05))",
        }}
      />
      <div
        className="relative z-[1] rounded-full"
        style={{
          width: dim * 0.35,
          height: dim * 0.35,
          background:
            "radial-gradient(circle at 40% 35%, rgba(255,255,255,0.25), rgba(79,142,247,0.4) 40%, transparent 70%)",
          boxShadow: "0 0 20px rgba(79,142,247,0.35)",
        }}
      />
    </div>
  );
}
