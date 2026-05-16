import React from "react";

/**
 * Top-level error boundary. Renders a visible fallback instead of leaving
 * the user with a blank white screen when a render throws.
 *
 * Class component because React's error boundary API requires it
 * (no hook equivalent yet).
 */
interface Props {
  children: React.ReactNode;
}
interface State {
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log so it's visible in the browser devtools even if the user can't
    // see what crashed.
    // eslint-disable-next-line no-console
    console.error("App crashed:", error, info.componentStack);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        dir="rtl"
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg,#f8fafc,#e2e8f0)",
          fontFamily: '"Heebo","Rubik",Arial,sans-serif',
          padding: "1rem",
        }}
      >
        <div
          style={{
            background: "#fff",
            borderRadius: "1rem",
            padding: "2rem 1.5rem",
            maxWidth: "32rem",
            width: "100%",
            boxShadow: "0 10px 30px rgba(15,23,42,0.08)",
          }}
        >
          <div style={{ fontSize: "2.5rem", textAlign: "center", marginBottom: "0.5rem" }}>
            ⚠️
          </div>
          <h1 style={{ fontSize: "1.25rem", margin: "0 0 0.5rem", textAlign: "center" }}>
            משהו השתבש
          </h1>
          <p style={{ color: "#64748b", fontSize: "0.95rem", textAlign: "center", margin: "0 0 1.25rem" }}>
            המערכת נתקלה בשגיאה לא צפויה. נסה לרענן את הדף או לבדוק את הקונסול לפרטים.
          </p>

          <details style={{ marginBottom: "1rem", fontSize: "0.8rem", color: "#475569" }}>
            <summary style={{ cursor: "pointer" }}>פרטי שגיאה</summary>
            <pre
              style={{
                background: "#f1f5f9",
                padding: "0.75rem",
                borderRadius: "0.5rem",
                overflow: "auto",
                marginTop: "0.5rem",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                direction: "ltr",
                textAlign: "left",
              }}
            >
              {this.state.error.message}
              {"\n"}
              {this.state.error.stack?.slice(0, 600)}
            </pre>
          </details>

          <div style={{ display: "flex", gap: "0.5rem", flexDirection: "column" }}>
            <button
              onClick={() => window.location.reload()}
              style={{
                background: "#2563eb",
                color: "#fff",
                border: 0,
                padding: "0.75rem 1.25rem",
                borderRadius: "0.75rem",
                fontWeight: 600,
                fontSize: "1rem",
                cursor: "pointer",
              }}
            >
              רענן דף
            </button>
            <button
              onClick={() => {
                try {
                  // Recover from a corrupt auth state without nuking shipment data.
                  localStorage.removeItem("rl.auth.token");
                  localStorage.removeItem("rl.auth.user");
                } catch {}
                window.location.assign("/login");
              }}
              style={{
                background: "#fff",
                color: "#475569",
                border: "1px solid #cbd5e1",
                padding: "0.65rem 1.25rem",
                borderRadius: "0.75rem",
                fontWeight: 500,
                fontSize: "0.9rem",
                cursor: "pointer",
              }}
            >
              נקה התחברות וחזור ל-Login
            </button>
          </div>
        </div>
      </div>
    );
  }
}
