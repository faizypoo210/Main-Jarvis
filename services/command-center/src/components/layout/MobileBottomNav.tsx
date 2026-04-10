import { Activity, LayoutDashboard, Plug, ShieldCheck, Target } from "lucide-react";
import { NavLink } from "react-router-dom";

const mobileNav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/missions", label: "Missions", icon: Target },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/integrations", label: "Integrations", icon: Plug },
];

export function MobileBottomNav() {
  return (
    <nav
      className="flex shrink-0 border-t border-[var(--bg-border)] px-1 pb-[env(safe-area-inset-bottom)] pt-1 md:hidden"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      {mobileNav.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex min-w-0 flex-1 flex-col items-center gap-0.5 py-2 text-[9px] ${
                isActive ? "text-[var(--accent-blue)]" : "text-[var(--text-muted)]"
              }`
            }
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
