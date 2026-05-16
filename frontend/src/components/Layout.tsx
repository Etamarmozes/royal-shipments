import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import clsx from "clsx";
import AIAssistant from "./AIAssistant";
import { Icon, type IconName } from "./Icon";
import { useAuth, clearAuth } from "../auth/store";
import { authLogout } from "../api/endpoints";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  /** If set, only these roles see this nav item */
  roles?: string[];
}

const NAV: NavItem[] = [
  { to: "/", label: "דשבורד", icon: "dashboard" },
  { to: "/shipments", label: "משלוחים פעילים", icon: "carton" },
  { to: "/containers-in-transit", label: "מכולות בדרך", icon: "container" },
  { to: "/categories", label: "קטגוריות בדרך", icon: "tag" },
  { to: "/receiving", label: "קבלת סחורה", icon: "receiving" },
  { to: "/forecast-daily", label: "תחזית משטחים", icon: "pallet" },
  { to: "/email-updates", label: "מרכז עדכונים ממייל", icon: "email",
    roles: ["admin", "import_manager"] },
  { to: "/documents", label: "מסמכי מקור", icon: "document" },
  { to: "/pending-shipments", label: "משלוחים חדשים לאישור", icon: "star",
    roles: ["admin", "import_manager"] },
  { to: "/alerts", label: "התראות", icon: "alert" },
  { to: "/history", label: "היסטוריה", icon: "history" },
  { to: "/users", label: "משתמשים והרשאות", icon: "users",
    roles: ["admin"] },
  { to: "/import-excel", label: "ייבוא מאקסל", icon: "excel",
    roles: ["admin", "import_manager"] },
  { to: "/import-batches", label: "Import Batches", icon: "rollback",
    roles: ["admin", "import_manager"] },
  { to: "/data-review", label: "בדיקת נתונים קיימים", icon: "test_tube",
    roles: ["admin", "import_manager"] },
  { to: "/document-review", label: "בדיקת שיוכי מסמכים", icon: "search",
    roles: ["admin", "import_manager"] },
  { to: "/help/supplier", label: "מדריך לספקים", icon: "info" },
];

/** Bottom-nav quick actions on mobile. "More" opens the full drawer. */
const MOBILE_QUICK: NavItem[] = [
  { to: "/", label: "בית", icon: "home" },
  { to: "/containers-in-transit", label: "מכולות", icon: "container" },
  { to: "/receiving", label: "קבלה", icon: "receiving" },
  { to: "/documents", label: "מסמכים", icon: "document" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "מנהל", import_manager: "מנהל יבוא",
  warehouse: "מחסן", viewer: "צופה",
};

export default function Layout() {
  const auth = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const role = auth.user?.role || "";
  const visibleNav = NAV.filter((it) => !it.roles || it.roles.includes(role));

  // Close mobile drawer whenever the route changes
  useEffect(() => { setDrawerOpen(false); }, [loc.pathname]);

  const doLogout = async () => {
    await authLogout();
    clearAuth();
    nav("/login", { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-slate-50">
      {/* ========== Mobile top bar ========== */}
      <header className="lg:hidden sticky top-0 z-30 bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setDrawerOpen(true)}
          className="p-2 -mr-2 rounded-lg hover:bg-slate-100"
          aria-label="פתח תפריט"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <div className="text-center">
          <div className="text-base font-bold text-brand-700 leading-none">Royal Linen</div>
          <div className="text-[10px] text-slate-500 mt-0.5">מרכז שליטה משלוחים</div>
        </div>
        <div className="w-10" />
      </header>

      {/* ========== Drawer (mobile) ========== */}
      {drawerOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm"
          onClick={() => setDrawerOpen(false)}
        >
          <aside
            className="absolute right-0 top-0 bottom-0 w-72 max-w-[85vw] bg-white shadow-xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <div className="text-lg font-bold text-brand-700">Royal Linen</div>
                <div className="text-xs text-slate-500">מרכז שליטה</div>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="text-slate-400 hover:text-slate-700 text-2xl leading-none p-1"
                aria-label="סגור"
              >×</button>
            </div>
            <nav className="flex-1 overflow-y-auto p-2">
              {visibleNav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    clsx(
                      "flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium",
                      isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-50"
                    )
                  }
                >
                  <Icon name={item.icon} size={20} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
            {auth.user && (
              <div className="border-t border-slate-200 p-4">
                <div className="text-sm font-semibold text-slate-800 truncate">
                  {auth.user.full_name || auth.user.username}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  <span className="badge-blue text-[10px]">{ROLE_LABELS[role] || role}</span>
                </div>
                <div className="mt-3 flex gap-2">
                  <NavLink
                    to="/change-password"
                    className="flex-1 text-center text-xs btn-secondary py-2"
                  >החלף קוד</NavLink>
                  <button onClick={doLogout} className="flex-1 text-xs btn-danger py-2">
                    התנתק
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {/* ========== Desktop sidebar ========== */}
      <aside className="hidden lg:flex lg:w-64 lg:min-h-screen bg-white border-l border-slate-200 lg:fixed lg:right-0 lg:top-0 flex-col">
        <div className="p-5 border-b border-slate-200">
          <div className="text-xl font-bold text-brand-700">Royal Linen</div>
          <div className="text-xs text-slate-500 mt-1">מרכז שליטה משלוחים</div>
        </div>
        <nav className="p-3 grid grid-cols-1 gap-1 flex-1 overflow-y-auto">
          {visibleNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-50"
                )
              }
            >
              <Icon name={item.icon} size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        {auth.user && (
          <div className="border-t border-slate-200 p-3">
            <div className="text-sm font-medium text-slate-800 truncate">
              {auth.user.full_name || auth.user.username}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              <span className="badge-blue text-[10px]">{ROLE_LABELS[role] || role}</span>
            </div>
            <div className="mt-2 flex gap-1">
              <NavLink to="/change-password" className="text-xs text-slate-600 hover:text-slate-900 flex-1">
                החלף קוד
              </NavLink>
              <button onClick={doLogout} className="text-xs text-red-600 hover:text-red-800">
                התנתק
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* ========== Main content ========== */}
      <main className="flex-1 lg:mr-64 p-4 lg:p-6 with-bottom-nav-padding lg:!pb-6">
        <Outlet />
      </main>

      {/* ========== Bottom nav (mobile only) ========== */}
      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-slate-200 grid grid-cols-5"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {MOBILE_QUICK.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex flex-col items-center justify-center py-2 text-[10px] font-medium",
                isActive ? "text-brand-700" : "text-slate-500"
              )
            }
          >
            <Icon name={item.icon} size={22} />
            <span className="mt-1">{item.label}</span>
          </NavLink>
        ))}
        <button
          onClick={() => setDrawerOpen(true)}
          className="flex flex-col items-center justify-center py-2 text-[10px] font-medium text-slate-500"
        >
          <span className="text-2xl leading-none" aria-hidden>≡</span>
          <span className="mt-1">עוד</span>
        </button>
      </nav>

      <AIAssistant />
    </div>
  );
}
