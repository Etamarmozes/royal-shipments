/**
 * Auth state — token + current user + permission set.
 *
 * Stored in localStorage so the user stays logged in across page reloads.
 * Listeners are notified on changes via a tiny pub-sub (no Zustand dep
 * needed — keeps the bundle small).
 */

const TOKEN_KEY = "rl.auth.token";
const USER_KEY = "rl.auth.user";

export interface AuthUser {
  id: number;
  username: string | null;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  role: "admin" | "import_manager" | "warehouse" | "viewer" | string;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  permissions?: string[];
}

let _token: string | null = null;
let _user: AuthUser | null = null;
const listeners = new Set<() => void>();

// Load from localStorage on first import. Wrap each step so a corrupt
// JSON value can't crash the whole module load.
try {
  _token = localStorage.getItem(TOKEN_KEY);
} catch {
  _token = null;
}
try {
  const userStr = localStorage.getItem(USER_KEY);
  _user = userStr ? JSON.parse(userStr) : null;
} catch {
  // Corrupt user JSON → clear it so we don't get stuck in a half-auth state
  _user = null;
  try { localStorage.removeItem(USER_KEY); } catch {}
}
// Token without user (or vice versa) is meaningless — drop both.
if (!_token || !_user) {
  _token = null;
  _user = null;
}

// =====================================================================
// Stable snapshot for useSyncExternalStore.
//
// React's useSyncExternalStore calls getSnapshot on every render and uses
// Object.is to decide whether to re-render. If we return a fresh object
// literal each call, every render looks like a state change → infinite
// re-render loop ("Maximum update depth exceeded" + "getSnapshot should
// be cached"). We rebuild the snapshot ONLY when _token or _user actually
// change, otherwise return the cached reference.
// =====================================================================

interface AuthSnapshot {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
}

let _snapshot: AuthSnapshot = {
  token: _token,
  user: _user,
  isAuthenticated: !!_token && !!_user,
};

function rebuildSnapshot() {
  _snapshot = {
    token: _token,
    user: _user,
    isAuthenticated: !!_token && !!_user,
  };
}

// SSR / first-paint snapshot — must also be stable. Frozen so any caller
// that mutates it crashes loudly instead of corrupting state.
const SERVER_SNAPSHOT: AuthSnapshot = Object.freeze({
  token: null,
  user: null,
  isAuthenticated: false,
}) as AuthSnapshot;

function notify() {
  // Rebuild ONCE before notifying — every subscriber sees the same new ref.
  rebuildSnapshot();
  listeners.forEach((fn) => fn());
}

export function getToken(): string | null {
  return _token;
}

export function getUser(): AuthUser | null {
  return _user;
}

export function setAuth(token: string, user: AuthUser) {
  _token = token;
  _user = user;
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {}
  notify();
}

export function updateUser(patch: Partial<AuthUser>) {
  if (!_user) return;
  _user = { ..._user, ...patch };
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(_user));
  } catch {}
  notify();
}

export function clearAuth() {
  _token = null;
  _user = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {}
  notify();
}

export function isAuthenticated(): boolean {
  return !!_token && !!_user;
}

export function hasPermission(action: string): boolean {
  if (!_user) return false;
  if (_user.role === "admin") return true;
  return (_user.permissions || []).includes(action);
}

export function hasRole(...roles: string[]): boolean {
  if (!_user) return false;
  return roles.includes(_user.role);
}

// React hook to subscribe to auth changes
import { useSyncExternalStore } from "react";

// Module-level subscribe + getSnapshot — defining these inside useAuth would
// give every render new function identities and re-trigger the subscription.
function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot(): AuthSnapshot {
  return _snapshot;
}

function getServerSnapshot(): AuthSnapshot {
  return SERVER_SNAPSHOT;
}

export function useAuth(): AuthSnapshot {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
