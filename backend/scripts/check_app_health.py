"""Royal Linen — local-dev health check.

Pure stdlib. Run from shell — does NOT depend on any browser/MCP tool.
Use this as the source of truth when something looks broken.

Usage:
    python backend/scripts/check_app_health.py
    python backend/scripts/check_app_health.py --backend http://localhost:8000 --frontend http://localhost:5173
    python backend/scripts/check_app_health.py --skip-auth   # don't try test login

Exit code:
    0  HEALTHY   — backend + frontend + auth all pass
    1  PARTIAL   — backend down OR frontend down OR auth failed
    2  DOWN      — both backend and frontend unreachable
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request


GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

# Disable colors on Windows old terminals if not supported
import os
if os.name == "nt" and not os.environ.get("ANSICON") and not os.environ.get("WT_SESSION"):
    GREEN = YELLOW = RED = RESET = ""


def _http(method: str, url: str, *, body: bytes | None = None,
          headers: dict | None = None, timeout: float = 5.0):
    """Run an HTTP request. Returns (status_code, body_str, error_message_or_None)."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        # 4xx/5xx are reachable — return the status so caller can decide
        try:
            content = e.read().decode("utf-8", errors="replace")
        except Exception:
            content = ""
        return e.code, content, None
    except urllib.error.URLError as e:
        return None, "", f"URLError: {e.reason}"
    except (socket.timeout, TimeoutError):
        return None, "", "timeout"
    except ConnectionRefusedError:
        return None, "", "connection refused"
    except Exception as e:
        return None, "", f"{type(e).__name__}: {e}"


class Check:
    def __init__(self, name: str):
        self.name = name
        self.status = "?"     # OK / DOWN / FAILED / SKIPPED
        self.detail = ""

    def ok(self, detail=""):     self.status = "OK";      self.detail = detail
    def down(self, detail=""):   self.status = "DOWN";    self.detail = detail
    def failed(self, detail=""): self.status = "FAILED";  self.detail = detail
    def skipped(self, detail=""): self.status = "SKIPPED"; self.detail = detail

    def line(self) -> str:
        color = {"OK": GREEN, "DOWN": RED, "FAILED": RED,
                 "SKIPPED": YELLOW, "?": YELLOW}.get(self.status, "")
        pad = self.name.ljust(28)
        return f"  {pad}{color}{self.status:<8}{RESET}{self.detail}"


def run_checks(backend: str, frontend: str, *, skip_auth: bool,
               username: str, password: str) -> list[Check]:
    checks: list[Check] = []

    # 1. Backend /health
    c = Check("BACKEND /health")
    code, body, err = _http("GET", f"{backend}/health")
    if err: c.down(f"  ({err})")
    elif code == 200 and '"ok"' in body: c.ok(f"  HTTP {code}")
    else: c.failed(f"  HTTP {code} body={body[:80]!r}")
    checks.append(c)
    backend_up = c.status == "OK"

    # 2. Backend /docs (FastAPI swagger HTML)
    c = Check("BACKEND /docs")
    code, body, err = _http("GET", f"{backend}/docs")
    if err: c.down(f"  ({err})")
    elif code == 200 and "swagger" in body.lower(): c.ok(f"  HTTP {code}")
    elif code == 200: c.ok(f"  HTTP {code} (non-swagger)")
    else: c.failed(f"  HTTP {code}")
    checks.append(c)

    # 3. Frontend root
    c = Check("FRONTEND /")
    code, body, err = _http("GET", f"{frontend}/")
    if err: c.down(f"  ({err})")
    elif code == 200 and ('<div id="root">' in body or "<title>" in body): c.ok(f"  HTTP {code}")
    else: c.failed(f"  HTTP {code}")
    checks.append(c)
    frontend_up = c.status == "OK"

    # 4. Frontend /login
    c = Check("FRONTEND /login")
    code, body, err = _http("GET", f"{frontend}/login")
    if err: c.down(f"  ({err})")
    elif code == 200: c.ok(f"  HTTP {code}")
    else: c.failed(f"  HTTP {code}")
    checks.append(c)

    # 5. Backend login endpoint
    c = Check("AUTH /auth/login")
    if skip_auth:
        c.skipped("  (--skip-auth)")
        token = None
    elif not backend_up:
        c.skipped("  (backend down)")
        token = None
    else:
        payload = json.dumps({"username": username, "password": password}).encode()
        code, body, err = _http("POST", f"{backend}/auth/login",
                                 body=payload,
                                 headers={"Content-Type": "application/json"})
        token = None
        if err: c.down(f"  ({err})")
        elif code == 200:
            try:
                data = json.loads(body)
                token = data.get("access_token")
                role = data.get("user", {}).get("role", "?")
                c.ok(f"  HTTP 200, role={role}, token_len={len(token or '')}")
            except Exception as e:
                c.failed(f"  HTTP 200 but bad JSON: {e}")
        elif code == 401:
            c.failed(f"  HTTP 401 (wrong creds — try --username / --password)")
        else:
            c.failed(f"  HTTP {code}")
    checks.append(c)

    # 6. Protected route
    c = Check("PROTECTED /auth/me")
    if not token:
        c.skipped("  (no token)")
    else:
        code, body, err = _http("GET", f"{backend}/auth/me",
                                 headers={"Authorization": f"Bearer {token}"})
        if err: c.down(f"  ({err})")
        elif code == 200:
            try:
                data = json.loads(body)
                perms = len(data.get("permissions", []))
                c.ok(f"  HTTP 200, perms={perms}")
            except Exception:
                c.failed(f"  HTTP 200 but bad JSON")
        else:
            c.failed(f"  HTTP {code}")
    checks.append(c)

    # 7. Protected endpoint that exercises the DB read path
    c = Check("PROTECTED /shipments")
    if not token:
        c.skipped("  (no token)")
    else:
        code, body, err = _http("GET", f"{backend}/shipments?limit=1",
                                 headers={"Authorization": f"Bearer {token}"})
        if err: c.down(f"  ({err})")
        elif code == 200:
            try:
                n = len(json.loads(body).get("items", []))
                c.ok(f"  HTTP 200, {n} sample item(s)")
            except Exception:
                c.failed(f"  HTTP 200 but bad JSON")
        else:
            c.failed(f"  HTTP {code}")
    checks.append(c)

    # 8. QC summary (if endpoint is wired — it's optional)
    c = Check("QC /qc/summary")
    if not token:
        c.skipped("  (no token)")
    else:
        code, body, err = _http("GET", f"{backend}/qc/summary",
                                 headers={"Authorization": f"Bearer {token}"})
        if err: c.down(f"  ({err})")
        elif code == 404:
            c.skipped("  (QC not wired yet)")
        elif code == 200:
            try:
                d = json.loads(body)
                c.ok(f"  HTTP 200, open={d.get('open_total', '?')}")
            except Exception:
                c.failed(f"  HTTP 200 but bad JSON")
        else:
            c.failed(f"  HTTP {code}")
    checks.append(c)

    return checks, backend_up, frontend_up


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://localhost:8000")
    ap.add_argument("--frontend", default="http://localhost:5173")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="123456")
    ap.add_argument("--skip-auth", action="store_true",
                    help="don't try logging in")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of human output")
    args = ap.parse_args()

    started = time.time()
    checks, backend_up, frontend_up = run_checks(
        args.backend, args.frontend, skip_auth=args.skip_auth,
        username=args.username, password=args.password,
    )
    elapsed = time.time() - started

    # Aggregate
    has_failure = any(c.status in ("DOWN", "FAILED") for c in checks)
    auth_ok = any(c.name.startswith("AUTH") and c.status == "OK" for c in checks)
    protected_ok = any(c.name.startswith("PROTECTED") and c.status == "OK" for c in checks)

    if backend_up and frontend_up and (auth_ok or args.skip_auth) and (protected_ok or args.skip_auth):
        app_status = "HEALTHY"
        exit_code = 0
    elif backend_up or frontend_up:
        app_status = "PARTIAL"
        exit_code = 1
    else:
        app_status = "DOWN"
        exit_code = 2

    if args.json:
        out = {
            "app_status": app_status,
            "elapsed_sec": round(elapsed, 2),
            "backend_up": backend_up,
            "frontend_up": frontend_up,
            "auth_ok": auth_ok,
            "protected_ok": protected_ok,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail.strip()}
                       for c in checks],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return exit_code

    print("=" * 64)
    print(f"  Royal Linen — local-dev health check ({elapsed:.1f}s)")
    print("=" * 64)
    for c in checks:
        print(c.line())
    print("=" * 64)

    color = {"HEALTHY": GREEN, "PARTIAL": YELLOW, "DOWN": RED}[app_status]
    print(f"  APP STATUS:  {color}{app_status}{RESET}")
    print()

    # Actionable hints
    if app_status == "DOWN":
        print("  Both servers unreachable. Most likely:")
        print("    - Neither uvicorn nor vite is running.")
        print("    - Ports 8000 / 5173 not bound (check `netstat -ano`).")
        print("    Run the commands in docs/RUNBOOK_LOCAL_DEV.md.")
    elif app_status == "PARTIAL":
        if not backend_up:
            print("  Backend down — start it with:")
            print("    cd backend && .venv\\Scripts\\activate")
            print("    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        if not frontend_up:
            print("  Frontend down — start it with:")
            print("    cd frontend && npm run dev")
    else:
        print("  Everything green.")
        print("  If a Claude tool reports an API error, it's the TOOL — the app is fine.")
    print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
