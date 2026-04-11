import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { RouteErrorBoundary } from "./components/layout/RouteErrorBoundary";
import { Activity } from "./pages/Activity";
import { Approvals } from "./pages/Approvals";
import { MissionDetail } from "./pages/MissionDetail";
import { Missions } from "./pages/Missions";
import { Overview } from "./pages/Overview";
import { PlaceholderPage } from "./pages/PlaceholderPage";

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
        <Route path="integrations" element={<PlaceholderPage title="Integrations" />} />
        <Route path="workers" element={<PlaceholderPage title="Workers" />} />
        <Route path="cost" element={<PlaceholderPage title="Cost & Usage" />} />
        <Route path="system" element={<PlaceholderPage title="System Health" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </RouteErrorBoundary>
  );
}
