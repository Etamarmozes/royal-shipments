import { useState } from "react";
import { Navigate, useNavigate, useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authLogin } from "../api/endpoints";
import { setAuth, useAuth } from "../auth/store";

/**
 * Login page. RTL, mobile-friendly, full-screen.
 * - Submits to /auth/login
 * - Stores token + user in localStorage
 * - On must_change_password=true → redirects to /change-password
 * - Otherwise → redirects to /
 */
export default function Login() {
  const auth = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: () => authLogin(username.trim(), password),
    onSuccess: (data) => {
      setError(null);
      setAuth(data.access_token, data.user);
      // Redirect: must_change_password → /change-password, else original target or /
      const from = (loc.state as any)?.from?.pathname || "/";
      if (data.user.must_change_password) {
        nav("/change-password", { replace: true });
      } else {
        nav(from, { replace: true });
      }
    },
    onError: (e: any) => {
      setError(e?.message || "שם משתמש או קוד שגויים");
    },
  });

  if (auth.isAuthenticated && !auth.user?.must_change_password) {
    const from = (loc.state as any)?.from?.pathname || "/";
    return <Navigate to={from} replace />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 p-6 sm:p-8">
        <div className="text-center mb-6">
          <div className="text-3xl mb-2">🚢</div>
          <h1 className="text-2xl font-bold text-slate-900">Royal Linen</h1>
          <p className="text-sm text-slate-500 mt-1">מערכת ניהול משלוחים</p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!username.trim() || !password) {
              setError("שם משתמש וקוד נדרשים");
              return;
            }
            login.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <label className="label">שם משתמש</label>
            <input
              className="input text-base py-3"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              dir="ltr"
            />
          </div>

          <div>
            <label className="label">קוד כניסה / סיסמה</label>
            <input
              type="password"
              className="input text-base py-3"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              dir="ltr"
            />
          </div>

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary w-full py-3 text-base"
            disabled={login.isPending}
          >
            {login.isPending ? "מתחבר..." : "כניסה"}
          </button>
        </form>

        <p className="text-xs text-slate-400 text-center mt-6">
          גרסה ראשונית — מנהל אחראי על הקמת משתמשים נוספים.
          <br />
          <span className="text-slate-300">
            ההתחברות מקומית ואינה תלויה ב-Google.
          </span>
        </p>
      </div>
    </div>
  );
}
