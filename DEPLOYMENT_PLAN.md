# Royal Linen — Deployment Plan

מסמך זה מסביר איך מעלים את האפליקציה לסביבת ייצור (production), אחרי שלב Login + הרשאות + PWA כבר מוכן.

> **המסמך הזה הוא תכנון בלבד.** אין צורך לבצע את כל הצעדים מיד — אפשר להתחיל מ-MVP על שרת VPS אחד ולהתקדם בהדרגה.

---

## 1. סקירה — שתי גישות

### גישה A: Hosted (מהיר להתחיל, פחות שליטה)
| רכיב | שירות מומלץ | עלות חודשית מקורבת |
|---|---|---|
| Frontend | **Vercel** או **Netlify** | חינם (Hobby) → 20$ |
| Backend  | **Render** או **Railway** | 7–25$ |
| Database | Render Postgres / Neon / Supabase | 0–25$ |
| File storage | S3 / Cloudflare R2 / Backblaze B2 | ~1$ |
| Domain   | Namecheap / Cloudflare Registrar | ~10$/שנה |
| **סה"כ MVP** |  | **~30–60$/חודש** |

יתרונות: HTTPS אוטומטי, deploy אוטומטי מ-git, גיבויים מובנים, ללא תחזוקת OS.
חסרונות: עלות גוברת עם הסקייל, פחות שליטה.

### גישה B: Self-hosted VPS (יותר שליטה, יותר תחזוקה)
| רכיב | שירות מומלץ | עלות חודשית |
|---|---|---|
| VPS (4GB RAM, 80GB SSD) | Hetzner CX22 / DigitalOcean / Linode | ~6–12$ |
| Domain | Namecheap | ~10$/שנה |
| **סה"כ** |  | **~10$/חודש** |

הכל רץ על שרת אחד: Nginx (reverse proxy + HTTPS via Let's Encrypt) → Backend (uvicorn/gunicorn) + PostgreSQL + קבצים על דיסק.

> **המלצה ראשונית:** מתחילים עם **גישה B** על Hetzner CX22 בתל אביב/פרנקפורט — פשוט, זול, מהיר. עוברים ל-A כשמתחילים להגיע ליותר מ-10 משתמשים פעילים.

---

## 2. ארכיטקטורה בייצור

```
                        ┌─────────────────────┐
                        │  app.royal-linen.com │  ← Frontend (HTTPS)
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │     Nginx           │  ← reverse proxy + TLS
                        │  /         → static │
                        │  /api/*    → :8000  │
                        │  /auth/*   → :8000  │
                        │  /gmail/*  → :8000  │
                        │  /uploads/ → :8000  │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼─────────────────┐
              │                    │                 │
        ┌─────▼─────┐       ┌──────▼──────┐    ┌─────▼─────┐
        │ FastAPI   │       │ PostgreSQL  │    │  /uploads │
        │ + APsched │       │             │    │ on disk   │
        └───────────┘       └─────────────┘    └───────────┘
```

---

## 3. Frontend hosting

### Vercel (מומלץ אם בוחרים גישה A)

1. צור חשבון, התחבר ל-GitHub.
2. New Project → Import את הריפו.
3. הגדרות:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Environment Variables:
   ```
   VITE_API_BASE = https://api.royal-linen.com
   ```
5. Deploy → תקבל URL בסגנון `royal-linen.vercel.app`. הוסף custom domain.

### חלופית: Netlify
זהה — `npm run build` → `dist`, אותם env vars, יש להוסיף `_redirects`:
```
/*    /index.html   200
```
(נדרש כי React Router משתמש ב-history mode)

### חלופית: VPS עם Nginx
ראה סעיף 9 — Nginx serve-ים את `dist/` כסטטי.

---

## 4. Backend hosting

### Render (גישה A)

1. New Web Service → connect GitHub repo.
2. הגדרות:
   - **Root Directory**: `backend`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Environment Variables (ראה סעיף 6).
4. Add Disk: 10GB mounted at `/var/data` (קבצים שלא רוצים שייעלמו).
5. עדכן `FILE_STORAGE_PATH=/var/data/uploads`.

### חלופית: Railway
דומה — auto-detect של Python, רק להגדיר start command + env.

### גישה B (VPS) — systemd service
ראה סעיף 9.

---

## 5. PostgreSQL במקום SQLite

SQLite טוב למשתמש יחיד מקומי, אבל בייצור עם מספר משתמשים בו-זמנית — חייבים PostgreSQL.

### שלבי המעבר

1. **התקן את ה-driver:**
   הוסף ל-`backend/requirements.txt`:
   ```
   psycopg2-binary==2.9.9
   ```

2. **הגדר את DATABASE_URL:**
   ```
   DATABASE_URL=postgresql+psycopg2://royal:STRONG@db.internal:5432/royal_linen
   ```
   ה-`config.py` כבר תומך בכל URL ש-SQLAlchemy מבין.

3. **העברת הסכמה:**
   - `Base.metadata.create_all(bind=engine)` ב-`init_db` יוצר את כל הטבלאות.
   - `add_missing_columns()` ב-`utils/migrations.py` נכון רק ל-SQLite — **חובה לעבור ל-Alembic** אם הולכים לפרודקשן עם Postgres.

4. **התקן Alembic (חד-פעמי):**
   ```bash
   pip install alembic
   alembic init migrations
   # configure migrations/env.py to use Base.metadata + DATABASE_URL
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```

5. **העברת נתונים מ-SQLite (אם רוצים):**
   ```bash
   # dev only
   pip install pgloader  # או:
   python -m app.export_excel  # ייצוא ל-Excel וייבוא ידני
   ```

6. **Bootstrap:** ב-Postgres הריק, `auth_service.bootstrap_admin()` עדיין יוצר את `admin/123456` בכניסה ראשונה.

### חלופי: Managed Postgres
- **Render Postgres** — $7/חודש, גיבוי יומי כלול.
- **Neon** (serverless) — חינם עד 0.5GB.
- **Supabase** — חינם עד 500MB.

---

## 6. Environment variables — production

### Backend (`backend/.env` או env vars של ה-host)

```bash
# Database
DATABASE_URL=postgresql+psycopg2://royal:STRONG_RANDOM_PASSWORD@db.internal:5432/royal_linen

# Auth — חובה לייצר חדש לפני production!
AUTH_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(64))">
AUTH_TOKEN_TTL_HOURS=24
AUTH_BOOTSTRAP_USERNAME=admin
AUTH_BOOTSTRAP_PASSWORD=<random-strong-password>     # יוחלף בכניסה הראשונה

# Public URLs
FRONTEND_URL=https://app.royal-linen.com
BACKEND_URL=https://api.royal-linen.com

# CORS — ONLY the production frontend origin(s). NO localhost in prod.
CORS_ALLOWED_ORIGINS=https://app.royal-linen.com

# Gmail OAuth
GMAIL_CREDENTIALS_FILE=/etc/royal-linen/credentials.json
GMAIL_REDIRECT_URI=https://api.royal-linen.com/gmail/callback
GMAIL_FRONTEND_RETURN_URL=https://app.royal-linen.com/email-updates
GMAIL_SYNC_DAYS=7
GMAIL_PREFER_UNREAD=false

# File storage
FILE_STORAGE_PATH=/var/data/royal-linen/uploads

# Background jobs
EMAIL_SYNC_INTERVAL_MINUTES=60
```

### Frontend (`frontend/.env.production` — נטען בזמן build)
```bash
VITE_API_BASE=https://api.royal-linen.com
VITE_BACKEND_URL=https://api.royal-linen.com
```

### חוקים
- **לעולם לא** לשים secrets בקוד או ב-`.env.example`.
- `.env` לא נכנס ל-git (כבר ב-`.gitignore`).
- ב-Render/Vercel — להגדיר env vars ב-UI, לא בקובץ.
- שינוי `AUTH_SECRET` ב-prod ינתק את כל המשתמשים (ה-JWT שלהם יהפוך לא תקף) — זה תכונה.

---

## 7. Gmail OAuth — production redirect URI

### Google Cloud Console:
1. APIs & Services → Credentials → ה-OAuth 2.0 client (existing).
2. הוסף ל-**Authorized redirect URIs**:
   ```
   https://api.royal-linen.com/gmail/callback
   ```
   (השאר את ה-`http://localhost:8000/gmail/callback` לסביבת dev.)
3. הורד את ה-`credentials.json` המעודכן והעתק ל-`/etc/royal-linen/credentials.json` בשרת.
4. הגדר `GMAIL_CREDENTIALS_FILE=/etc/royal-linen/credentials.json`.
5. בכניסה הראשונה ל-`/email-updates` בייצור — האפליקציה תפנה ל-OAuth, המשתמש מאשר, וה-token נשמר ב-`/var/data/royal-linen/data/gmail_token.json`.

> **OAuth consent screen:** לפני העלאה לכל משתמש שאינו "test user", חובה להעביר את ה-app ל-"Production" ב-OAuth consent. ל-Google scope של `gmail.readonly` נדרש Verification (לוקח 1–4 שבועות). **חלופית:** השארת המצב כ-"Internal" אם ה-Workspace הוא של החברה — זה לא דורש verification.

---

## 8. HTTPS חובה

- **חובה** — JWT ו-cookies לא בטוחים על http לא מוצפן.
- ב-Vercel / Netlify / Render — HTTPS אוטומטי, אין מה לעשות.
- ב-VPS — Let's Encrypt דרך Nginx (ראה סעיף 9).
- ה-Service Worker (PWA) **לא ירשם** ב-iOS/Android אם האתר לא https.

### redirect http→https (Nginx):
```nginx
server {
    listen 80;
    server_name app.royal-linen.com api.royal-linen.com;
    return 301 https://$host$request_uri;
}
```

---

## 9. VPS deploy מלא (גישה B) — צעד אחר צעד

### דרישות
- Ubuntu 22.04 LTS (Hetzner / Linode / DigitalOcean)
- 4GB RAM, 80GB SSD
- 2 רשומות DNS A: `app.royal-linen.com` ו-`api.royal-linen.com` ל-IP של השרת

### שלב 1 — התקנות בסיס
```bash
ssh root@<SERVER_IP>
apt update && apt upgrade -y
apt install -y nginx postgresql postgresql-contrib python3 python3-venv \
               python3-pip git certbot python3-certbot-nginx ufw

ufw allow OpenSSH
ufw allow "Nginx Full"
ufw enable
```

### שלב 2 — PostgreSQL
```bash
sudo -u postgres psql <<EOF
CREATE USER royal WITH PASSWORD 'STRONG_RANDOM_PASSWORD';
CREATE DATABASE royal_linen OWNER royal;
EOF
```

### שלב 3 — Backend
```bash
useradd -m -s /bin/bash royal
mkdir -p /var/data/royal-linen/{uploads,data}
chown -R royal:royal /var/data/royal-linen

su - royal
git clone https://github.com/<your-org>/royal-linen-shipments-app.git
cd royal-linen-shipments-app/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt psycopg2-binary
nano .env    # paste production env vars
exit
```

### שלב 4 — systemd service ל-backend
`/etc/systemd/system/royal-linen.service`:
```ini
[Unit]
Description=Royal Linen FastAPI
After=network.target postgresql.service

[Service]
User=royal
WorkingDirectory=/home/royal/royal-linen-shipments-app/backend
EnvironmentFile=/home/royal/royal-linen-shipments-app/backend/.env
ExecStart=/home/royal/royal-linen-shipments-app/backend/.venv/bin/uvicorn \
          app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable royal-linen
systemctl start royal-linen
journalctl -u royal-linen -f   # logs
```

### שלב 5 — Frontend build
```bash
su - royal
cd royal-linen-shipments-app/frontend
echo 'VITE_API_BASE=https://api.royal-linen.com' > .env.production
echo 'VITE_BACKEND_URL=https://api.royal-linen.com' >> .env.production
npm install
npm run build
exit

# Move build output to nginx static dir
mkdir -p /var/www/royal-linen
cp -r /home/royal/royal-linen-shipments-app/frontend/dist/* /var/www/royal-linen/
```

### שלב 6 — Nginx
`/etc/nginx/sites-available/royal-linen`:
```nginx
# Frontend (PWA)
server {
    listen 443 ssl http2;
    server_name app.royal-linen.com;

    root /var/www/royal-linen;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # PWA: don't cache index.html / sw.js, cache assets long
    location = /index.html { add_header Cache-Control "no-cache, no-store, must-revalidate"; }
    location = /sw.js      { add_header Cache-Control "no-cache, no-store, must-revalidate"; }
    location /assets/      { expires 1y; add_header Cache-Control "public, immutable"; }
    location /icons/       { expires 30d; }

    ssl_certificate     /etc/letsencrypt/live/app.royal-linen.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.royal-linen.com/privkey.pem;
}

# Backend (API)
server {
    listen 443 ssl http2;
    server_name api.royal-linen.com;

    client_max_body_size 25M;   # PDF/Excel uploads

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    ssl_certificate     /etc/letsencrypt/live/api.royal-linen.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.royal-linen.com/privkey.pem;
}

# http → https redirect (both subdomains)
server {
    listen 80;
    server_name app.royal-linen.com api.royal-linen.com;
    return 301 https://$host$request_uri;
}
```

```bash
ln -s /etc/nginx/sites-available/royal-linen /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### שלב 7 — TLS עם Let's Encrypt
```bash
certbot --nginx -d app.royal-linen.com -d api.royal-linen.com
# Auto-renew already configured by certbot package
```

---

## 10. File storage

### בשלב ראשון: דיסק מקומי
- `FILE_STORAGE_PATH=/var/data/royal-linen/uploads`
- גיבוי יומי דרך rsync (סעיף 11).

### כשמתפצלים ל-2+ שרתים: object storage
מומלץ **S3** או **Cloudflare R2** (זול יותר, אין egress fees).

ה-`routers/documents.py` ו-`routers/shipments.py` כותבים לקובץ ב-`UPLOADS_DIR`. כדי לעבור ל-S3:
1. `pip install boto3`
2. צור `services/storage.py` עם `save_file(path, bytes)` ו-`get_file_url(path)` שמכוונים ל-S3 / boto3.
3. החלף את הכתיבות ב-`documents.py` / `shipments.py` לקריאה ל-`save_file()`.
4. החלף `documentDownloadUrl()` בצד הלקוח לקרוא ל-pre-signed URL מ-`/documents/{id}/url`.

> בשלב הנוכחי **לא חייבים** לעשות את זה. דיסק מקומי + גיבוי טוב מספיק עד 100GB ועד 5 משתמשים פעילים.

---

## 11. Backup strategy

### Database (Postgres)
**יומי, אוטומטי, ל-S3 / R2:**

`/etc/cron.daily/royal-linen-backup`:
```bash
#!/bin/bash
set -euo pipefail
DATE=$(date +%F)
DIR=/var/backups/royal-linen
mkdir -p $DIR
sudo -u postgres pg_dump royal_linen | gzip > $DIR/db-$DATE.sql.gz

# Keep 30 days locally, then push to S3 (optional)
find $DIR -name "db-*.sql.gz" -mtime +30 -delete

# Optional: aws s3 cp $DIR/db-$DATE.sql.gz s3://royal-linen-backups/
```

```bash
chmod +x /etc/cron.daily/royal-linen-backup
```

### Files (uploads)
שבועי, snapshot של `/var/data/royal-linen/uploads`:
```bash
tar czf /var/backups/royal-linen/uploads-$(date +%F).tar.gz /var/data/royal-linen/uploads
```

### בדיקת שחזור — חובה לתרגל פעם בחודש
```bash
gunzip -c db-2026-05-03.sql.gz | psql royal_linen_test
```

### Managed: אם בוחרים Render/Neon/Supabase Postgres — הם עושים גיבוי אוטומטי + point-in-time recovery.

---

## 12. Logs

### Backend
- ה-`logging.basicConfig` ב-`main.py` כבר כותב ל-stdout בפורמט סטנדרטי.
- ב-systemd: `journalctl -u royal-linen -f`
- ב-Render: יש לוגים מובנים ב-UI.
- לחיפוש מתקדם: שלח ל-Better Stack / Logtail / Datadog.

### Nginx
- `/var/log/nginx/access.log` ו-`error.log`
- logrotate מובנה ב-Ubuntu

### בקרת שגיאות (Sentry)
מומלץ אחרי ההעלאה הראשונה:
```bash
pip install sentry-sdk[fastapi]
```
```python
# main.py
import sentry_sdk
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""), traces_sample_rate=0.1)
```

---

## 13. Restart policy / High availability

- **systemd Restart=always** דואג שה-backend יקום אם הוא קורס.
- **APScheduler** מאתחל את עצמו עם ה-process — אם ה-backend קופץ, ה-job ימשיך מהפעם הבאה.
- **בעיה אפשרית:** עם `--workers 2`, ה-APScheduler ירוץ פעמיים. לתקן בעתיד עם:
  ```python
  if os.environ.get("RUN_SCHEDULER") == "1":
      scheduler.start()
  ```
  ולהריץ instance אחד ייעודי עם `RUN_SCHEDULER=1` ושאר ה-workers בלי.

- **2 שרתים** (HA): נדרש Postgres חיצוני + S3 לקבצים + load balancer. לא נדרש בשלב הנוכחי.

---

## 14. User access — production

### יצירת משתמשים
1. כניסה ראשונה כ-`admin` עם הסיסמה הזמנית מ-`AUTH_BOOTSTRAP_PASSWORD`.
2. כפיית החלפת סיסמה.
3. דרך מסך "משתמשים והרשאות" — יצירת משתמשים אמיתיים:
   - מנהל יבוא: `import_manager`
   - מחסנאים: `warehouse`
   - צופים (אם רלוונטי): `viewer`
4. לכל משתמש להשאיר ✓ "חובה להחליף סיסמה בכניסה ראשונה".
5. **למחוק / להשבית את `admin` או לפחות להחליף סיסמה חזקה** — לא להשאיר את `admin/123456` חיים.

### תמיכה במספר חברות / מולטי-טננט
לא נתמך כרגע (single-tenant). אם נדרש — צריך להוסיף `tenant_id` לכל הטבלאות ולסנן בכל query.

---

## 15. Domain

מומלץ:
- `app.royal-linen.com` → frontend
- `api.royal-linen.com` → backend

אם רק דומיין אחד:
- `royal-linen.com` → frontend
- ו-Nginx mountid את ה-API תחת `royal-linen.com/api/*` (proxy_pass ל-127.0.0.1:8000) — אז `VITE_API_BASE=https://royal-linen.com/api`.

---

## 16. Pre-launch checklist

לפני העלאה ראשונה לפרודקשן — לעבור על הרשימה:

- [ ] `AUTH_SECRET` הוגדר לערך אקראי חדש (`token_urlsafe(64)`)
- [ ] `AUTH_BOOTSTRAP_PASSWORD` הוגדר לסיסמה חזקה (ייאלץ ייחודי בכניסה הראשונה)
- [ ] `CORS_ALLOWED_ORIGINS` מכיל **רק** את הדומיין הציבורי, ללא localhost
- [ ] `DATABASE_URL` מצביע ל-Postgres, לא SQLite
- [ ] `GMAIL_REDIRECT_URI` רשום ב-Google Cloud Console **ובדיוק** תואם ל-env
- [ ] HTTPS פעיל (`certbot` או Vercel/Render)
- [ ] תעודת SSL מתחדשת אוטומטית (`certbot renew --dry-run`)
- [ ] `FILE_STORAGE_PATH` מצביע על Volume שגיבוייו פעילים
- [ ] קרון יומי של `pg_dump` עובד (לבדוק ידנית)
- [ ] השבתה / מחיקה של ה-admin הזמני אחרי שהמשתמשים האמיתיים הוקמו
- [ ] `npm run build` ירוק ללא warnings
- [ ] `curl https://api.royal-linen.com/health` מחזיר 200
- [ ] PWA installable מהפלאפון (Lighthouse → PWA → "Installable" ירוק)
- [ ] Login + logout + change-password עובדים מהפלאפון
- [ ] Receiving Mode עובד למחסנאי בטלפון

---

## 17. הערכת זמן

| משימה | זמן |
|---|---|
| הקמת VPS + Nginx + Postgres + TLS | 2–3 שעות |
| מעבר SQLite→Postgres + Alembic | 3–5 שעות |
| Deploy ראשון של backend + frontend | 1 שעה |
| Gmail OAuth production setup + verification | יום-יומיים (לרוב המתנה) |
| בדיקות Pre-launch | 2–3 שעות |
| **סה"כ עד go-live** | **1–2 ימי עבודה** + המתנה ל-Google verification |
