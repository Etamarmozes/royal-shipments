import { Navigate, useLocation } from "react-router-dom";
import { useAuth, clearAuth } from "./store";

/**
 * Wrap protected routes. Redirects to /login if not authenticated.
 * If user must_change_password and we're not already on /change-password,
 * force them there first.
 *
 * Defensive design (these all matter for breaking redirect loops):
 *  - useAuth() returns a CACHED snapshot (see auth/store.ts), so this
 *    component re-renders only when token/user actually change.
 *  - We never redirect while already on the target route.
 *  - If the snapshot is internally inconsistent (token but no user, or
 *    user with no role), we clear and redirect to /login exactly once.
 */
export default function ProtectedRoute({
  children, requireRole, requirePermission,
}: {
  children: React.ReactNode;
  requireRole?: string[];
  requirePermission?: string;
}) {
  const auth = useAuth();
  const loc = useLocation();

  // Internally inconsistent state — clear it ONCE and bounce to /login.
  // Without this, a corrupt half-auth state could thrash forever.
  if (auth.token && !auth.user) {
    clearAuth();
    if (loc.pathname !== "/login") {
      return <Navigate to="/login" replace />;
    }
    return null;
  }

  if (!auth.isAuthenticated) {
    // Already on /login → don't redirect (would loop).
    if (loc.pathname === "/login") return null;
    return <Navigate to="/login" state={{ from: loc }} replace />;
  }

  if (auth.user?.must_change_password && loc.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  if (requireRole && !requireRole.includes(auth.user?.role || "")) {
    return (
      <div className="p-8 text-center">
        <div className="text-2xl mb-2">🔒</div>
        <div className="font-semibold">אין הרשאה</div>
        <div className="text-sm text-slate-500 mt-1">
          הדף הזה זמין רק ל: {requireRole.join(", ")}
        </div>
      </div>
    );
  }
  if (requirePermission
      && !auth.user?.permissions?.includes(requirePermission)
      && auth.user?.role !== "admin") {
    return (
      <div className="p-8 text-center">
        <div className="text-2xl mb-2">🔒</div>
        <div className="font-semibold">אין הרשאה</div>
        <div className="text-sm text-slate-500 mt-1">חסרה הרשאה: {requirePermission}</div>
      </div>
    );
  }
  return <>{children}</>;
}
