# Production deployment — Royal Linen Shipments

Target environment: **Ubuntu 24.04 LTS on Hetzner** (CX22 / CX32 class
or higher). Two public DNS names, both pointing at the box's public IP:

| Subdomain | Purpose |
| --- | --- |
| `app.royallinenshipments.com` | Frontend SPA |
| `api.royallinenshipments.com` | FastAPI backend |

End-state architecture:

```
┌────────────────────── Hetzner Ubuntu 24.04 ──────────────────────┐
│                                                                  │
│  ┌─ nginx (host) ────────────────────────────────────────────┐   │
│  │   TLS termination via Let's Encrypt (certbot)             │   │
│  │   app.royallinenshipments.com → 127.0.0.1:8080            │   │
│  │   api.royallinenshipments.com → 127.0.0.1:8000            │   │
│  └────────────────────────────────────────────────────────────┘   │
│           ▲                                  ▲                   │
│           │ 127.0.0.1:8080                   │ 127.0.0.1:8000    │
│           │                                  │                   │
│  ┌────────────┐    docker-compose    ┌────────────┐    ┌──────┐  │
│  │  frontend  │ ───── /api → ──────▶ │  backend   │ ──▶│  db  │  │
│  │  (nginx +  │                      │  (uvicorn) │    │ (pg) │  │
│  │   SPA)     │                      └────────────┘    └──────┘  │
│  └────────────┘                                                   │
│       volume: backend_uploads / backend_data / backend_logs       │
│                                                       db_data    │
└──────────────────────────────────────────────────────────────────┘
```

The **backend and Postgres are NEVER exposed to the public internet** —
both bind only to `127.0.0.1` on the host, and only the host's nginx
(which terminates TLS) reaches them.

---

## Step 1 — Server prep (one-time)

```bash
# As root on the fresh Ubuntu box:
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx ca-certificates curl gnupg ufw fail2ban

# Docker (official repo, not the snap)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Firewall — only allow SSH + HTTP/S
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Create the deploy user (don't run docker as root long-term)
adduser --disabled-password --gecos "" royal
usermod -aG docker royal
mkdir -p /home/royal/.ssh
cp /root/.ssh/authorized_keys /home/royal/.ssh/   # if you SSH'd in as root
chown -R royal:royal /home/royal/.ssh
chmod 700 /home/royal/.ssh
chmod 600 /home/royal/.ssh/authorized_keys
```

From here on, log in as `royal` (`ssh royal@your-server`).

---

## Step 2 — DNS

Point both subdomains to the server's public IPv4:

```
app.royallinenshipments.com.  A  <SERVER_IP>
api.royallinenshipments.com.  A  <SERVER_IP>
```

Wait until `dig +short app.royallinenshipments.com` and `dig +short
api.royallinenshipments.com` return your server IP before continuing.

---

## Step 3 — Pull the repo + create .env

```bash
cd /home/royal
git clone https://github.com/<your-org>/royal-linen-shipments-app.git
cd royal-linen-shipments-app

cp deploy/.env.example .env
chmod 600 .env

# Generate strong secrets and edit .env:
echo "POSTGRES_PASSWORD=$(openssl rand -base64 36 | tr -d '=+/' | cut -c1-32)"
echo "AUTH_SECRET=$(openssl rand -hex 64)"
echo "AUTH_BOOTSTRAP_PASSWORD=$(openssl rand -base64 18)"
# Paste each into .env, replacing the placeholder values.

editor .env
```

Required fields to fill in `.env`:

- `POSTGRES_PASSWORD` — generated above
- `AUTH_SECRET` — generated above (64-hex)
- `AUTH_BOOTSTRAP_PASSWORD` — generated above; **save it** — you'll log in
  with this once, then change it from the UI.

Defaults that are usually fine:

- `FRONTEND_HOST=app.royallinenshipments.com`
- `BACKEND_HOST=api.royallinenshipments.com`
- `GMAIL_DISABLED=true` (until you configure OAuth — see step 7)

---

## Step 4 — Build and start the stack

```bash
cd /home/royal/royal-linen-shipments-app

# Validate the compose file resolves all env vars (will fail loudly if not).
docker compose config --quiet

# Build images.  First run downloads bases + builds ~3-5 min.
docker compose build

# Bring everything up.
docker compose up -d

# Verify all three containers became healthy.
docker compose ps
# Expect: royal-db (healthy), royal-backend (healthy), royal-frontend (healthy)

# Tail logs while debugging.
docker compose logs -f --tail=200 backend
```

The backend's startup runs `Base.metadata.create_all` against Postgres,
so all tables are created on first run. No data migration step is needed
for a fresh deploy.

Smoke-test from the host:

```bash
curl -fsS http://127.0.0.1:8000/health        # → {"status":"ok"}
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/   # → 200
```

---

## Step 5 — Host nginx + TLS

```bash
# Drop the site files into nginx's sites-available
sudo cp deploy/nginx/app.royallinenshipments.com.conf  /etc/nginx/sites-available/
sudo cp deploy/nginx/api.royallinenshipments.com.conf  /etc/nginx/sites-available/

# Enable them
sudo ln -sf /etc/nginx/sites-available/app.royallinenshipments.com.conf  /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/api.royallinenshipments.com.conf  /etc/nginx/sites-enabled/

# The bundled configs reference cert paths that don't exist yet — temporarily
# disable the HTTPS server blocks so `nginx -t` passes, OR run certbot in
# "--nginx" mode which adds the cert lines automatically:

sudo nginx -t || echo "expected on first run before certbot creates certs"

# Issue certs.  certbot will detect the server_name blocks, prove control
# via HTTP-01, and rewrite the configs with the live cert paths.
sudo certbot --nginx -d app.royallinenshipments.com -d api.royallinenshipments.com \
             --agree-tos --no-eff-email --email ops@royallinenshipments.com \
             --redirect

# Verify renewal is set up — certbot installs a systemd timer automatically.
sudo systemctl status certbot.timer
sudo certbot renew --dry-run

# Reload nginx
sudo nginx -t && sudo systemctl reload nginx
```

Browser test — both URLs should now serve over HTTPS:

- `https://app.royallinenshipments.com/` → React login screen
- `https://api.royallinenshipments.com/health` → `{"status":"ok"}`
- `https://api.royallinenshipments.com/docs` → Swagger UI

---

## Step 6 — First login

1. Open `https://app.royallinenshipments.com/`.
2. Log in with `admin` + the `AUTH_BOOTSTRAP_PASSWORD` from your `.env`.
3. The app forces a password change — pick something strong, save it in
   your password manager.
4. From `/users`, create the real user accounts (Adi / Israel / Shani / Itamar)
   with roles `import_manager`, `warehouse`, etc.

---

## Step 7 — (Optional) Re-enable Gmail OAuth for production

Until you do this, the email sync is disabled and the app is fully
operable with manual + Excel imports.

1. In Google Cloud Console for the project, **create a new OAuth client**
   (web application) with these settings:
   - Authorised JavaScript origins: `https://app.royallinenshipments.com`
   - Authorised redirect URIs: `https://api.royallinenshipments.com/gmail/callback`
2. Download the `credentials.json` and copy it onto the server:
   `/home/royal/royal-linen-shipments-app/deploy/secrets/gmail_credentials.json`
3. In `docker-compose.yml`, uncomment the volume line under `backend.volumes`:

       - ./deploy/secrets/gmail_credentials.json:/app/credentials.json:ro

4. Edit `.env`:

       GMAIL_DISABLED=false
       GMAIL_REDIRECT_URI=https://api.royallinenshipments.com/gmail/callback

5. `docker compose up -d backend` to pick up the changes.
6. In the UI, navigate to **Dashboard → "חבר Gmail"** and complete the OAuth
   flow.

---

## Step 8 — Backups

Two things must be backed up:

| What | Where | Recommended cadence |
| --- | --- | --- |
| Postgres data | volume `royal_db_data` | Daily logical dump (`pg_dump`) + weekly snapshot |
| Uploaded documents | volume `royal_backend_uploads` | Nightly tarball |

Suggested cron (host crontab as `royal`):

```cron
# 03:00 nightly Postgres dump → /var/backups/royal/<date>.sql.gz, keep 30 days
0 3 * * *  docker exec royal-db pg_dump -U $POSTGRES_USER -d $POSTGRES_DB | gzip > /var/backups/royal/db_$(date +\%F).sql.gz && find /var/backups/royal -name 'db_*.sql.gz' -mtime +30 -delete

# 03:15 uploads tarball, keep 14 days
15 3 * * * tar -C /var/lib/docker/volumes/royal_backend_uploads/_data -czf /var/backups/royal/uploads_$(date +\%F).tar.gz . && find /var/backups/royal -name 'uploads_*.tar.gz' -mtime +14 -delete
```

Off-site copy: `rsync` to Hetzner Storage Box / B2 / S3.

---

## Day-2 operations

| Task | Command |
| --- | --- |
| View logs | `docker compose logs -f backend` |
| Restart a service | `docker compose restart backend` |
| Apply config change | edit `.env`, then `docker compose up -d` |
| Deploy new image | `git pull && docker compose build && docker compose up -d` |
| psql shell | `docker exec -it royal-db psql -U $POSTGRES_USER -d $POSTGRES_DB` |
| Open backend shell | `docker exec -it royal-backend bash` |
| Stop everything | `docker compose down` (data volumes preserved) |
| **Nuke data** (irreversible!) | `docker compose down -v` |

---

## Security checklist before going live

- [ ] DNS A-records resolve to the server IP for both subdomains
- [ ] `ufw status` shows only 22, 80, 443 open
- [ ] `.env` is `chmod 600` and not in git (`.gitignore` already lists it)
- [ ] `AUTH_SECRET` was generated fresh (NOT the dev fallback)
- [ ] `POSTGRES_PASSWORD` is a 32-char random string
- [ ] First-time admin password was changed via the UI
- [ ] `EMERGENCY_ADMIN_*` are either set (and saved in a password manager) or empty
- [ ] `https://app.royallinenshipments.com/` returns 200 over TLS
- [ ] `https://api.royallinenshipments.com/health` returns 200 over TLS
- [ ] Backups cron is installed and the first dump succeeded
- [ ] fail2ban is monitoring `auth.log` for SSH brute force
- [ ] SSH key auth only (`PasswordAuthentication no` in `/etc/ssh/sshd_config`)
