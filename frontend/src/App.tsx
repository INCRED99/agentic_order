import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import { PlaceholderPage } from "./components/ui/PlaceholderPage";
import Orders from "./pages/Orders";
import { Approvals } from "./pages/Approvals";
import { Menu } from "./pages/Menu"
import { Payments } from "./pages/Payments"
import { AgentActivity } from "./pages/AgentActivity";
import { Emails } from "./pages/Emails"
import { Settings } from "./pages/Settings"
export default function App() {
  return (

    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/orders" replace />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/menu" element={<Menu />} />
        <Route path="/payments" element={<Payments />} />
        <Route path="/agent-activity" element={<AgentActivity />} />
        <Route path="/emails" element={<Emails />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/orders" replace />} />
      </Route>
    </Routes>
  );
}