import { Bell, PanelRight } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { checkHealth } from "../../lib/api";
import { Avatar } from "../common/Avatar";

const titles: Record<string, string> = {
  "/": "Overview",
  "/missions": "Missions",
  "/approvals": "Approvals",
  "/activity": "Activity",
  "/integrations": "Integrations",
  "/workers": "Workers",
  "/cost": "Cost & Usage",
  "/system": "System Health",
};

export function CenterPane({
  children,
  onToggleRightPanel,
  showRightToggle,
}: {
  children: ReactNode;
  onToggleRightPanel?: () => void;
  showRightToggle?: boolean;
}) {
  const loc = useLocation();
  const title = titles[loc.pathname] ?? "Command Center";
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const ok = await checkHealth();
      if (!cancelled) setReachable(ok);
    };
    void run();
    const id = window.setInterval(() => void run(), 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col border-[var(--bg-border)] lg:border-r">
      <header
        className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--bg-border)] px-3 py-3 md:px-5"
        style={{ backgroundColor: "var(--bg-void)" }}
      >
        <div className="min-w-0 flex-1">
          <nav className="font-mono text-[10px] text-[var(--text-muted)]">
            <Link to="/" className="hover:text-[var(--text-secondary)]">
              Grok Plan
            </Link>
            <span className="mx-1">/</span>
            <span className="text-[var(--text-secondary)]">Sop and sre</span>
          </nav>
          <h1 className="font-display text-lg font-semibold text-[var(--text-primary)] md:text-xl">
            {title}
          </h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full border border-[var(--bg-border)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">
              Mission context
            </span>
            <span className="rounded-full border border-[var(--bg-border)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">
              Workspace
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 md:gap-3">
          {showRightToggle ? (
            <button
              type="button"
              onClick={onToggleRightPanel}
              className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] lg:hidden"
              aria-label="Toggle context panel"
            >
              <PanelRight className="h-5 w-5" />
            </button>
          ) : null}
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${reachable ? "bg-[var(--status-green)]" : "bg-[var(--status-amber)]"}`}
              title={reachable ? "Control plane online" : "Control plane offline"}
            />
            {!reachable ? (
              <span className="font-mono text-[10px] text-[var(--text-muted)]">offline</span>
            ) : null}
          </span>
          <span className="hidden rounded-full border border-[var(--bg-border)] px-2 py-1 font-mono text-[10px] text-[var(--text-muted)] sm:inline">
            $1.48 / d
          </span>
          <span className="hidden font-mono text-[10px] text-[var(--text-muted)] md:inline">10 wk</span>
          <span className="hidden font-mono text-[10px] text-[var(--text-muted)] lg:inline">3 tasks</span>
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
          </button>
          <Avatar size={32} />
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
