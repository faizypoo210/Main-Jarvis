import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { RouteErrorBoundary } from "./components/layout/RouteErrorBoundary";
import { Activity } from "./pages/Activity";
import { Approvals } from "./pages/Approvals";
import { CostUsage } from "./pages/CostUsage";
import { MissionDetail } from "./pages/MissionDetail";
import { Missions } from "./pages/Missions";
import { Overview } from "./pages/Overview";
import { Integrations } from "./pages/Integrations";
import { Memory } from "./pages/Memory";
import { SystemHealth } from "./pages/SystemHealth";
import { Workers } from "./pages/Workers";

export default function App() {
  return (
    <RouteErrorBoundary>
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="missions/:missionId" element={<MissionDetail />} />
        <Route path="missions" element={<Missions />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="activity" element={<Activity />} />
        <Route path="memory" element={<Memory />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="workers" element={<Workers />} />
        <Route path="cost" element={<CostUsage />} />
        <Route path="system" element={<SystemHealth />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </RouteErrorBoundary>
  );
}
