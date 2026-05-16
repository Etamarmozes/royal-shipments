# Deployment

## Local (the only mode the MVP officially supports)

See the root `README.md`. Two terminals: backend (uvicorn) + frontend (vite).

## Single-server production

Recommended for a single company / single store-chain deployment.

### 1. Server prerequisites

- Linux (Ubuntu 22.04 LTS) or Windows Server 2022
- Python 3.11+
- Node 20+
- Nginx (reverse proxy + static)
- A scheduler: systemd timers (Linux) or Task Scheduler (Windows) — though APScheduler inside the app is enough for MVP
- For PDF/JPG: `wkhtmltopdf` package, **or** Playwright + Chromium

### 2. Database

For production use PostgreSQL:

```
DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/sales_intel
```

The schema is portable. Migrations use Alembic — see `backend/alembic/` (added when you outgrow SQLite).

### 3. Backend

```
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn

# behind a process manager
gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
    -w 4 -b 127.0.0.1:8000 \
    --access-logfile - --error-logfile -
```

Wrap with `systemd`:

```ini
# /etc/systemd/system/sales-intel-api.service
[Unit]
Description=Sales Intelligence API
After=network.target

[Service]
WorkingDirectory=/opt/sales-intel/backend
EnvironmentFile=/opt/sales-intel/.env
ExecStart=/opt/sales-intel/backend/.venv/bin/gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000
Restart=always
User=salesintel

[Install]
WantedBy=multi-user.target
```

### 4. Frontend

```
cd frontend
npm install
npm run build           # outputs frontend/dist/
```

Serve `dist/` with Nginx (gzip + cache):

```nginx
server {
    listen 443 ssl http2;
    server_name sales.example.com;

    root /opt/sales-intel/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 5. The reports folder

`data/comax_reports/` should be a real folder on the server that you can drop files into via:

- **SMB / Samba share** — easiest for Windows users.
- **SFTP** — for IT-managed hand-off.
- **A scheduled script on the Comax PC** that copies files via `rsync`/`robocopy`.

In Phase 2 (Comax API) this folder becomes optional.

### 6. Backups

- Database: `pg_dump` nightly to encrypted off-site storage.
- Imported source files: keep `data/imported/` and `data/archive/` — they're the audit trail.
- Generated reports are reproducible from the database; no need to back them up.

### 7. Monitoring

- `/health` returns `{ status, db, last_import_age_seconds }`. Wire to UptimeRobot or similar.
- Log shipping: `journalctl` → Loki / CloudWatch / whatever you have.

### 8. Auth in production

The MVP ships with a local user table and a single admin password from `.env` (`ADMIN_PASSWORD`). Before exposing to the internet:

- Replace with SSO (Google / Microsoft) — FastAPI has `authlib` integrations
- Or front the app with an OIDC proxy (oauth2-proxy)

## Containerized

`docker-compose.yml` (provided in a future iteration) brings up:

- `db` — postgres:16
- `api` — built from `backend/Dockerfile`
- `web` — built from `frontend/Dockerfile`, served by nginx
- `proxy` — nginx with TLS

Volume-mount `./data/comax_reports` into the `api` container so users can drop files locally.

## Updates

```
git pull
backend: pip install -r requirements.txt && alembic upgrade head && systemctl restart sales-intel-api
frontend: npm install && npm run build
```

## Rollback

The combination of (a) idempotent imports keyed by `file_hash` and (b) `data/imported/` containing every source file means a full DB rebuild is `python -m app.rebuild_from_imported`. Plan to actually exercise this once.
