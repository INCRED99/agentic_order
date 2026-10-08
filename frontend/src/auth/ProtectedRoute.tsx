import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
    const { session, loading } = useAuth();
    const location = useLocation();

    // Saved session still loading. Do not redirect yet.
    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-cream text-espresso/70">
                Loading...
            </div>
        );
    }

    if (!session) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <Outlet />;
}