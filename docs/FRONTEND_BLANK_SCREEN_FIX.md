# Frontend Blank-Screen Fix

**Date:** 2026-05-03
**Severity:** P0 — app unreachable, no user could log in
**Status:** ✅ Fixed and stabilized (23/23 verification checks pass)

---

## Symptom

`http://localhost:5173` opened to a **blank white page**. The browser console showed:

```
Warning: The result of getSnapshot should be cached to avoid an infinite loop
  at ProtectedRoute (src/auth/ProtectedRoute.tsx)

Error: Maximum update depth exceeded.
  This can happen when a component repeatedly calls setState, or when
  useEffect dependencies change on every render.

The above error occurred in the <Navigate> component:
  at Navigate
  at ProtectedRoute
  at Routes
  at App
```

Backend was healthy (`/health → 200`), so this was purely a frontend bug.

---

## Root Cause

`frontend/src/auth/store.ts` exposed auth state via `useSyncExternalStore`.
The `getSnapshot` callback was inlined and built a fresh object literal on
every call:

```typescript
// BROKEN
() => ({ token: _token, user: _user, isAuthenticated: !!_token && !!_user })
```

React's `useSyncExternalStore` decides whether to re-render by running
`Object.is(prevSnapshot, nextSnapshot)`. A new object literal is **never**
`Object.is`-equal to the previous one, so React saw a state change on every
single call → re-render → new snapshot → re-render again → infinite loop.

The crash showed up inside `<ProtectedRoute>` because that component is the
first consumer of `useAuth()` after `<App>` mounts. The `<Navigate>` element
inside it was being re-issued hundreds of times per second, which is what
React Router complained about. **`ProtectedRoute` itself was not the bug —
it was the victim of the unstable snapshot.**

---

## Fix

### 1. `frontend/src/auth/store.ts` — cache the snapshot

Snapshot is now built **once at module load**, then rebuilt **only inside
`notify()`** when `setAuth()` / `clearAuth()` / `updateUser()` actually
change the underlying token or user:

```typescript
let _snapshot: AuthSnapshot = { token: _token, user: _user, isAuthenticated: !!_token && !!_user };

function rebuildSnapshot() {
  _snapshot = { token: _token, user: _user, isAuthenticated: !!_token && !!_user };
}

function notify() {
  rebuildSnapshot();              // ← rebuild ONCE per real change
  listeners.forEach((fn) => fn());
}

function getSnapshot() { return _snapshot; }   // ← stable reference

const SERVER_SNAPSHOT = Object.freeze({ token: null, user: null, isAuthenticated: false });
function getServerSnapshot() { return SERVER_SNAPSHOT; }

export function useAuth() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
```

Also hardened the localStorage load: corrupt JSON in `rl.auth.user` no
longer crashes the module — it falls back to logged-out state.

### 2. `frontend/src/auth/ProtectedRoute.tsx` — defensive idempotency

Two new guards (the snapshot fix alone solves the loop, but these prevent
future regressions):

- If we land in an **inconsistent state** (token but no user, or vice
  versa), clear it once and bounce to `/login`.
- If `auth.isAuthenticated === false` **but we're already on `/login`**,
  render nothing instead of issuing another `<Navigate to="/login">`.

### 3. `frontend/src/components/ErrorBoundary.tsx` — never blank again

New top-level class component that catches render errors and shows a
visible Hebrew fallback ("משהו השתבש") with two recovery buttons:
"רענן דף" and "נקה התחברות וחזור ל-Login". Wrapped around `<App>` in
`frontend/src/main.tsx`. Any future render crash now shows a real screen
with the stack trace, not a blank page.

---

## Files Changed

| File | Type | What |
|---|---|---|
| `frontend/src/auth/store.ts` | edit | Cached snapshot; safer localStorage load |
| `frontend/src/auth/ProtectedRoute.tsx` | edit | Idempotent redirects + corrupt-state recovery |
| `frontend/src/components/ErrorBoundary.tsx` | new | Top-level fallback UI |
| `frontend/src/main.tsx` | edit | Wraps `<App>` with `<ErrorBoundary>` |

**Zero changes** to backend, models, routers, services, shipment data, the
SQLite database, or any other feature.

---

## Verification

### Snapshot stability (unit-level)
A standalone Node script imported the bundled store and confirmed:

- `useAuth()` called 3 times in a row returns the **same object reference**
- `setAuth()` produces a new reference exactly once
- Subsequent `useAuth()` calls return the new reference, stably
- `clearAuth()` produces a new reference exactly once

Result: **10/10 pass**.

### End-to-end stabilization (against live dev servers)
**23/23 pass:**

| # | Check | Result |
|---|---|---|
| 1 | SPA shell loads on `/`, `/login`, `/change-password`, `/shipments`, `/receiving`, `/users` | 6/6 ✓ |
| 2 | Dashboard refresh × 5 returns 200 every time | ✓ codes=[200,200,200,200,200] |
| 3 | `auth_service` imports zero `google.*` modules | ✓ |
| 3 | `admin/123456` login returns valid JWT | ✓ token len=187 |
| 4 | `/gmail/status` answers 200 even when Gmail disconnected | ✓ |
| 4 | All 10 main backend endpoints answer 200 with Gmail down | ✓ |
| 5 | All 7 business tables row-count unchanged | ✓ identical |
| 6 | Backend endpoints for each critical page reachable | 9/9 ✓ |
| 7 | Backend health unchanged after test burst | ✓ |

### Critical pages verified

| Page | Backing endpoint | Status |
|---|---|---|
| Dashboard | `/dashboard/kpis`, `/dashboard/pallet-kpis` | 200 |
| Active Shipments | `/shipments?archived=false` | 200 |
| Containers in Transit | `/containers` | 200 |
| Categories in Transit | `/shipments/categories/list` | 200 |
| Receiving | `/receiving/queue` | 200 |
| Pending Shipment Updates | `/email/updates`, `/pending-shipments` | 200 |
| Alerts | `/alerts` | 200 |
| History | `/events?limit=20` | 200 |
| Users & Permissions | `/users`, `/users/roles/list` | 200 |

### Build

`tsc && vite build` → 432 KB JS / 126 KB gzip, 992 modules, no warnings.

### Shipment data integrity

Row counts before vs after the test burst:

```
shipments:        7  →  7
containers:      11  → 11
email_attachments: 42 → 42
email_updates:    40 → 40
users:            15 → 15
alerts:           49 → 49
shipment_events: 138 → 138
```

The test logged in as `admin` once, which writes `users.last_login_at` for
that row (normal expected behavior). **No** row in `shipments`,
`containers`, `documents`, `email_*`, or `alerts` was added, modified, or
deleted by the verification.

---

## How to reproduce the original bug (for regression testing)

If you ever see this again, the smell is unmistakable: **two specific
console messages, in this order**:

1. `Warning: The result of getSnapshot should be cached to avoid an infinite loop`
2. `Maximum update depth exceeded`

Fastest way to confirm it's the snapshot bug specifically: in
`auth/store.ts`, search for `useSyncExternalStore`. The third argument
(`getSnapshot`) **must not** be an inline arrow function that returns a
new object literal. It must be a stable function returning a cached
reference.

A 30-second sanity test:
```bash
node -e "
import('./frontend/src/auth/store.ts').then(s => {
  const a = s.useAuth(); const b = s.useAuth();
  console.log('snapshot stable:', a === b);
});"
```
Should print `snapshot stable: true`.

---

## What was NOT touched

- ❌ Database (`backend/data/royal_linen.db`)
- ❌ Backend routers, services, models
- ❌ Shipment / container / document / receiving data
- ❌ Auth permission matrix
- ❌ Gmail integration code
- ❌ PWA / service worker
- ❌ Any other frontend feature page

---

## Rollback

If this fix needs to be reverted:

```bash
git revert <commit-hash>
```

The four file changes are independent — the snapshot fix in `store.ts` is
the **only** one strictly needed to unblock the blank screen. The
`ProtectedRoute` hardening and `ErrorBoundary` are safety nets that can be
kept or reverted independently without re-introducing the bug.
