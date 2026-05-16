# Royal Linen Shipments — Backend (FastAPI)

API שמטרתו ניהול אוטומטי של משלוחים ומכולות.

## דרישות
- Python 3.11 ומעלה
- pip

## התקנה והרצה

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# יצירת DB וטעינת seed
python -m app.seed

# הפעלת שרת
uvicorn app.main:app --reload --port 8000
```

לאחר מכן ה-API זמין ב:
- http://localhost:8000
- http://localhost:8000/docs (Swagger UI)

## מבנה
```
backend/
  app/
    main.py            # FastAPI + lifespan + scheduler
    config.py          # config וקבועים
    database.py        # SQLAlchemy engine + session
    seed.py            # טעינת 6 משלוחים + 8 מכולות
    models/            # 10 טבלאות
    schemas/           # Pydantic
    routers/           # API endpoints
    services/          # לוגיקה עסקית + email parser + alert engine
  data/                # SQLite יווצר כאן
  uploads/             # קבצים מצורפים
  requirements.txt
```

## נקודות קצה עיקריות

| Method | Path | תיאור |
|--------|------|--------|
| GET    | /shipments | רשימת משלוחים פעילים |
| GET    | /shipments/{id} | משלוח בודד |
| GET    | /shipments/{id}/events | לוג שינויים למשלוח |
| GET    | /containers | רשימת מכולות |
| GET    | /extra-work | תוספות עבודה |
| GET    | /dashboard/kpis | מדדי דשבורד |
| GET    | /dashboard/forecast-8-weeks | תחזית 8 שבועות |
| GET    | /dashboard/action-items | פעולות שמחכות |
| POST   | /email/sync-now | סנכרון מייל ידני |
| POST   | /email/inject | הזרקת מייל לבדיקה (DEMO) |
| GET    | /email/updates | עדכוני מייל |
| PUT    | /email/updates/{id}/approve | אישור עדכון |
| GET    | /pending-shipments | טיוטות לאישור |
| POST   | /pending-shipments/{id}/approve | אישור טיוטה והפיכה למשלוח |
| GET    | /alerts | התראות |
| GET    | /export/excel | ייצוא לאקסל (10 גיליונות) |

## אינטגרציית מייל
ב-MVP, סורק המייל פועל כ-stub:
- POST /email/sync-now — מסמן `last_sync` (פלייסהולדר ל-Gmail/Outlook)
- POST /email/inject — מאפשר הזרקת מייל ידנית לבדיקת ה-parser

ה-parser ב-`services/email_parser_service.py` משתמש ב-regex לזיהוי:
- SHP-IDs, מספרי מכולות, BOL, Booking, Invoice, PO
- ETA / ETD בעברית ובאנגלית
- מילות מפתח של עיכוב או משלוח חדש

החלפה ל-LLM/Gmail API:
- שכבת Gmail/Outlook → ב-`email_sync_service.sync_now`
- שכבת Parser → ב-`email_parser_service.parse_email`

## Scheduler
APScheduler מריץ אחת לשעה (ניתן לשינוי ב-`config.py`):
- `alert_service.scan_alerts` — סורק התראות מערכת
- `email_sync_service.sync_now` — מעדכן זמן סנכרון אחרון

## חוקי אוטומציה (מתוך הבריף)
- שינוי ETA > 3 ימים → התראה אוטומטית
- ניירת חסרה בשלב 5+ → התראה
- delay_status=true בלי delay_reason → 400 (גם בעדכון מייל אוטומטי)
- מכולה ללא ETA יורשת מהמשלוח (לוגיקה ב-effective_eta)
- כל שינוי שדה נשמר ב-ShipmentEvent
- soft delete בלבד (Shipment.archived=true)
- PendingShipment לא הופך למשלוח פעיל בלי אישור משתמש
