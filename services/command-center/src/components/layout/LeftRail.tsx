import {
  Activity,
  BarChart2,
  Brain,
  Cpu,
  Heart,
  LayoutDashboard,
  Plug,
  Settings,
  ShieldCheck,
  Target,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import type { StreamPhase } from "../../contexts/ControlPlaneLiveContext";
import { LiveLinkIndicator } from "./LiveLinkIndicator";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/missions", label: "Missions", icon: Target, badge: "missions" as const },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck, badge: "approvals" as const },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/memory", label: "Memory", icon: Brain },
  { to: "/integrations", label: "Integrations", icon: Plug },
  { to: "/workers", label: "Workers", icon: Cpu },
  { to: "/cost", label: "Cost & Usage", icon: BarChart2 },
  { to: "/system", label: "System Health", icon: Heart },
];

export function LeftRail({
  missionActiveCount,
  pendingApprovalCount,
  streamPhase,
}: {
  missionActiveCount: number;
  pendingApprovalCount: number;
  streamPhase: StreamPhase;
}) {
  const badge = (key: "missions" | "approvals") => {
    if (key === "missions") return missionActiveCount > 0 ? missionActiveCount : null;
    if (key === "approvals") return pendingApprovalCount > 0 ? pendingApprovalCount : null;
    return null;
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 ease-linear md:justify-center md:px-2 lg:justify-start lg:px-3 ${
      isActive
        ? "border-l-2 border-[var(--accent-blue)] bg-[var(--accent-blue-glow)] text-[var(--accent-blue)] md:border-l-0 md:border-b-2 lg:border-b-0 lg:border-l-2"
        : "border-l-2 border-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
    }`;

  return (
    <aside
      className="hidden shrink-0 border-r border-[var(--bg-border)] md:flex md:w-14 md:flex-col lg:w-[220px]"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex flex-col gap-6 p-3 lg:p-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2 lg:gap-3">
          <div className="relative flex h-8 w-8 shrink-0 items-center justify-center">
            <div
              className="absolute inset-0 rounded-full opacity-60 blur-md"
              style={{ background: "var(--accent-blue-glow)" }}
            />
            <div
              className="relative h-8 w-8 rounded-full bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-blue-dim)] ring-2 ring-[var(--accent-blue)]/40"
              style={{
                boxShadow:
                  "0 0 20px 6px var(--accent-blue-glow), 0 0 40px 10px rgba(79,142,247,0.08)",
              }}
            />
          </div>
          <span className="font-display hidden text-lg font-bold tracking-tight text-[var(--text-primary)] lg:block">
            JARVIS
          </span>
          <div className="ml-auto min-w-0">
            <LiveLinkIndicator phase={streamPhase} />
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const b = item.badge ? badge(item.badge) : null;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={linkClass}
                title={item.label}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span className="hidden min-w-0 flex-1 lg:inline">{item.label}</span>
                {b != null ? (
                  <span
                    className={`ml-auto hidden rounded-full px-1.5 py-0.5 text-[10px] font-bold lg:inline ${
                      item.badge === "approvals"
                        ? "bg-[var(--status-amber)]/20 text-[var(--status-amber)]"
                        : "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                    }`}
                  >
                    {b}
                  </span>
                ) : null}
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto flex flex-col gap-2 border-t border-[var(--bg-border)] p-3 lg:p-4">
        <p className="hidden text-[10px] leading-tight text-[var(--text-muted)] lg:block">
          $1.48 / day
        </p>
        <p className="hidden text-[var(--text-muted)] lg:block text-[10px]">10 workers</p>
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] md:mx-auto lg:mx-0"
          aria-label="Settings"
        >
          <Settings className="h-5 w-5" />
        </button>
      </div>
    </aside>
  );
}
