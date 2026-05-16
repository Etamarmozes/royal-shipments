# Royal Linen — מערכת ניהול משלוחים אוטומטית

מערכת תפעולית לניהול משלוחים ומכולות עבור Royal Linen Ltd.
המטרה: להוריד מהמנהלים את עבודת המזכירות. המערכת אוספת מידע ממיילים, מבינה אותו, מכינה טיוטות, והמשתמש מאשר.

## הפעלה מהירה (מקומי)

צריך 2 טרמינלים — אחד ל-Backend ואחד ל-Frontend.

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed                     # טוען 6 משלוחים + 8 מכולות (פעם אחת)
cp .env.example .env                   # עורכים לפי הצורך
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local             # אופציונלי — לרוב לא צריך לערוך
npm run dev
```

פתח דפדפן: http://localhost:5173

**משתמש ראשון:** `admin / 123456` — האפליקציה תכריח החלפת סיסמה.

---

## הפעלה מהפלאפון (אותו Wi-Fi)

האפליקציה תוכננה כ-PWA — אפשר להוסיף אותה למסך הבית בטלפון ולפתוח כמו אפליקציה אמיתית.

### 1. הרץ את שני השרתים על ה-PC עם `--host 0.0.0.0`

ה-`vite.config.ts` כבר מוגדר ל-`host: true` (כלומר 0.0.0.0), ולכן `npm run dev` כבר מאזין על כל הממשקים.
ל-Backend פשוט תוסיף `--host 0.0.0.0`:

```bash
# Backend
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (כבר מאזין על 0.0.0.0)
cd frontend
npm run dev
```

### 2. מצא את ה-IP של ה-PC ברשת המקומית

**Windows:**
```powershell
ipconfig
# חפש "IPv4 Address" תחת "Wireless LAN adapter Wi-Fi"
# לדוגמה: 192.168.1.20
```

**macOS / Linux:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
# או
ipconfig getifaddr en0
```

### 3. ודא שה-Firewall של Windows מאפשר את הפורטים 5173 ו-8000

```powershell
# פעם אחת, מ-PowerShell עם הרשאות אדמין:
New-NetFirewallRule -DisplayName "Royal Linen Frontend" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow
New-NetFirewallRule -DisplayName "Royal Linen Backend"  -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### 4. הוסף את ה-IP ל-CORS של ה-Backend

ערוך את `backend/.env`:
```
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://192.168.1.20:5173
```
ואת ה-Backend אתחל מחדש.

### 5. בטלפון — פתח דפדפן וגלוש ל:
```
http://192.168.1.20:5173
```
(החלף את ה-IP ב-IP שלך)

### 6. הוסף למסך הבית כאפליקציה

**iPhone (Safari):**
- לחץ על Share (☐ עם חץ למעלה)
- בחר "Add to Home Screen" / "הוסף למסך הבית"
- לחץ Add — עכשיו האייקון של Royal Linen נמצא במסך הבית

**Android (Chrome):**
- בתפריט (⋮) בחר "Install app" / "התקן אפליקציה"
- או בכניסה הראשונה תופיע הצעה "Add to Home Screen"

> **חשוב:** ב-iOS, PWA דורש שהאתר ייטען מ-https — מקומית עובד עם IP אבל בלי מסך פתיחה מותאם. בפרודקשן (https) חוויית ה-PWA תהיה מלאה.

---

## אדריכלות

```
royal-linen-shipments-app/
├── backend/                 # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── models/          # 10+ טבלאות (User, Shipment, Container, ...)
│   │   ├── schemas/         # Pydantic
│   │   ├── routers/         # auth, shipments, containers, gmail, documents, ...
│   │   ├── services/        # logic + alert engine + email parser + auth
│   │   ├── utils/migrations.py  # auto-add missing columns at startup
│   │   ├── seed.py          # demo data
│   │   └── main.py          # FastAPI + APScheduler (hourly Gmail sync)
│   └── .env.example         # all env vars documented
├── frontend/                # React + TS + Tailwind RTL + PWA
│   ├── public/              # PWA: manifest, sw.js, offline.html, icons/
│   └── src/
│       ├── pages/           # Login, Dashboard, ContainersInTransit, Receiving, ...
│       ├── components/      # Layout (sidebar + bottom-nav), AIAssistant, ...
│       ├── auth/            # store.ts (token+user), ProtectedRoute
│       ├── api/             # axios + endpoints
│       └── utils/           # format עברית RTL
├── DEPLOYMENT_PLAN.md       # איך מעלים לשרת מסודר
└── README.md
```

---

## עקרונות מוצריים מיושמים

1. **Automation-first, Human approval when needed** — מיילים נסרקים אוטומטית, אבל עדכונים קריטיים (ETA / משלוח חדש / ניירת) דורשים אישור.
2. **משלוח חדש ממייל לא נכנס לרשימה הפעילה** — נוצר `PendingShipment`. רק אישור משתמש פותח Shipment עם SHP-ID אוטומטי.
3. **תוספת עבודה היא Opt-in** — שדות תוספת עבודה מופיעים רק כשהמשתמש מסמן `extra_work_required=true`.
4. **כל שינוי נרשם ב-ShipmentEvent** — לוג מלא לכל ישות.
5. **מכולה ללא ETA יורשת מהמשלוח** — `effective_eta_israel` מחושב בכל קריאה.
6. **הרשאות מבוססות-תפקיד (RBAC)** — admin / import_manager / warehouse / viewer, JWT, bcrypt, ProtectedRoute.

---

## Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2, SQLite (dev) / PostgreSQL (prod), Pydantic v2, APScheduler, bcrypt + python-jose
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Axios, PWA (manifest + service worker)

ל-deploy לשרת אמיתי ראה [`DEPLOYMENT_PLAN.md`](./DEPLOYMENT_PLAN.md).
