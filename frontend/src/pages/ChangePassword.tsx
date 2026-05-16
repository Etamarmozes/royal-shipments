import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authChangePassword } from "../api/endpoints";
import { updateUser, useAuth, clearAuth } from "../auth/store";

/**
 * First-login forced password change.
 * Reachable from /change-password — also linked from menu (Settings).
 */
export default function ChangePassword() {
  const auth = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const change = useMutation({
    mutationFn: () => authChangePassword(current, next),
    onSuccess: () => {
      setError(null);
      setDone(true);
      updateUser({ must_change_password: false });
      // Wait a moment then redirect home
      setTimeout(() => nav("/", { replace: true }), 1200);
    },
    onError: (e: any) => setError(e?.message || "שגיאה"),
  });

  const submit = () => {
    setError(null);
    if (next.length < 4) {
      setError("הסיסמה החדשה חייבת להכיל לפחות 4 תווים");
      return;
    }
    if (next !== confirm) {
      setError("הסיסמאות החדשות לא תואמות");
      return;
    }
    change.mutate();
  };

  if (!auth.isAuthenticated) {
    nav("/login", { replace: true });
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 p-6 sm:p-8">
        <div className="text-center mb-6">
          <div className="text-3xl mb-2">🔑</div>
          <h1 className="text-xl font-bold text-slate-900">החלפת קוד כניסה</h1>
          {auth.user?.must_change_password && (
            <p className="text-sm text-amber-700 mt-2">
              חובה לשנות את הקוד הראשוני לפני המשך השימוש
            </p>
          )}
        </div>

        {done ? (
          <div className="text-center py-6">
            <div className="text-3xl mb-2">✅</div>
            <div className="text-emerald-700 font-medium">הסיסמה שונתה. מעביר...</div>
          </div>
        ) : (
          <form
            onSubmit={(e) => { e.preventDefault(); submit(); }}
            className="space-y-4"
          >
            <div>
              <label className="label">קוד נוכחי</label>
              <input
                type="password"
                className="input text-base py-3"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                dir="ltr"
                autoFocus
              />
            </div>
            <div>
              <label className="label">קוד חדש</label>
              <input
                type="password"
                className="input text-base py-3"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                dir="ltr"
              />
            </div>
            <div>
              <label className="label">אישור קוד חדש</label>
              <input
                type="password"
                className="input text-base py-3"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
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
              disabled={change.isPending}
            >
              {change.isPending ? "שומר..." : "החלף קוד"}
            </button>

            {!auth.user?.must_change_password && (
              <button
                type="button"
                className="btn-secondary w-full"
                onClick={() => nav("/", { replace: true })}
              >
                חזרה
              </button>
            )}
          </form>
        )}

        <button
          className="text-xs text-slate-400 mt-4 text-center w-full"
          onClick={() => { clearAuth(); nav("/login", { replace: true }); }}
        >
          התנתק
        </button>
      </div>
    </div>
  );
}
