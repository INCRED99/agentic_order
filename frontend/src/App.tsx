import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import AppLayout from "./components/layout/AppLayout";
import { AgentActivity } from "./pages/AgentActivity";
import { Approvals } from "./pages/Approvals";
import { Emails } from "./pages/Emails";
import { Login } from "./pages/Login";
import { Menu } from "./pages/Menu";
import Orders from "./pages/Orders";
import { Payments } from "./pages/Payments";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/orders" replace />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/menu" element={<Menu />} />
          <Route path="/payments" element={<Payments />} />
          <Route path="/agent-activity" element={<AgentActivity />} />
          <Route path="/emails" element={<Emails />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/orders" replace />} />
    </Routes>
  );
}