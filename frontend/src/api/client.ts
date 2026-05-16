import axios from "axios";
import { getToken, clearAuth } from "../auth/store";

export const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) || "/api";

export const api = axios.create({
  baseURL: apiBase,
  headers: { "Content-Type": "application/json" },
});

// Attach Authorization header on every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any)["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Auto-logout on 401 (except for the login endpoint itself)
    const status = err?.response?.status;
    const url: string = err?.config?.url || "";
    if (status === 401 && !url.endsWith("/auth/login")) {
      clearAuth();
      // Avoid redirect loops if we're already on /login
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    const message =
      err?.response?.data?.detail ||
      err?.message ||
      "אירעה שגיאה לא ידועה";
    return Promise.reject(new Error(typeof message === "string" ? message : JSON.stringify(message)));
  }
);
