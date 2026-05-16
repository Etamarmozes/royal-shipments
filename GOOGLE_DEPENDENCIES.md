# Google Dependencies — Royal Linen Shipments

מסמך מקור-אמת עבור כל מה שקשור ל-Google באפליקציה. נשמר עדכני בכל פעם שמשנים תלות.

---

## TL;DR

> **Login לאפליקציה אינו תלוי ב-Google.**
> Google משמש **רק** לתכונה אחת אופציונלית: סנכרון מיילי משלוחים מ-Gmail.
> כשחשבון Google מושעה / לא זמין: **כל** שאר המערכת ממשיכה לעבוד (login, ניהול שילוחים/מכולות, מסמכים, מחסן, AI, היסטוריה, היררכיית הרשאות).

---

## 1. אילו שירותי Google בשימוש

| שירות | חובה? | מטרה | ללא זה? |
|---|---|---|---|
| **Gmail API (read-only)** | אופציונלי | משיכה אוטומטית של מיילי ספקים + הורדת attachments | סנכרון אוטומטי מושבת. הזנה ידנית עובדת רגיל. |
| **Google OAuth 2.0** | אופציונלי | הסכמה חד-פעמית של חשבון Gmail לשימוש ה-API | אין יכולת לחבר Gmail חדש |
| **Google Drive API** | ❌ לא בשימוש | — | לא רלוונטי |
| **Google Sign-In / Identity** | ❌ לא בשימוש | — | לא רלוונטי. ה-login מקומי. |
| **Google Workspace SSO** | ❌ לא בשימוש | — | לא רלוונטי |

ה-Google scope היחיד שמבוקש: `https://www.googleapis.com/auth/gmail.readonly`

---

## 2. אילו קבצים / חשבונות נדרשים

### קובץ credentials.json
- **מיקום:** `backend/credentials.json` (configurable דרך `GMAIL_CREDENTIALS_FILE`)
- **מקור:** Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID (Web application)
- **לא נכלל ב-git** (נמצא ב-`.gitignore`)
- **תוכן רגיש:** client_id + client_secret של ה-OAuth app
- **אם נמחק/חסר:** `/gmail/connect` יחזיר 500 עם הודעה ברורה. אין השפעה על login או על שאר התכונות.

### קובץ token (refresh + access)
- **מיקום:** `backend/data/gmail_token.json` (configurable דרך `GMAIL_TOKEN_FILE`)
- **נוצר אחרי:** הסכמת המשתמש ב-OAuth flow (`/gmail/connect` → callback)
- **לא נכלל ב-git**
- **תוכן רגיש:** refresh_token + access_token של חשבון ה-Gmail המחובר
- **אם נמחק/חסר:** `/gmail/status` יחזיר `connected: false`. הפתרון: לחץ "חבר Gmail" שוב.
- **אם פג תוקף בלי refresh_token:** אותו דבר.

### חשבון Google
- **התחבר אליו פעם אחת:** המשתמש שמחזיק במייל ההזמנות של Royal Linen
- **דורש:** הרשאת קריאה לתיבה הזאת בלבד (גם תיבה משנית/Workspace user עובד)
- **אם החשבון מושעה / נחסם:** `/gmail/sync` יחזיר 503. אפשר:
  1. להמתין לשחרור Google
  2. להחליף לחשבון Google אחר ולהריץ `/gmail/connect` מחדש
  3. להגדיר `GMAIL_DISABLED=true` ולעבור למצב ידני

---

## 3. מה עובד במצב Google-down

### עובד תמיד (לא תלוי Google):
- ✅ Login + Logout + Change Password
- ✅ ניהול משתמשים והרשאות (admin/import_manager/warehouse/viewer)
- ✅ צפייה ועריכה של משלוחים, מכולות, קטגוריות, ETA, ספקים, BOL/Booking/Invoice/PO
- ✅ העלאת מסמכים ידנית (PDF/Excel/Image)
- ✅ Preview + Download של מסמכים שכבר קיימים
- ✅ Receiving Mode (קליטת סחורה במחסן)
- ✅ AI Assistant (משתמש רק בנתוני DB מקומיים, ללא קריאות חיצוניות)
- ✅ דשבורד, Timeline, Forecast, Alerts, History
- ✅ ייצוא לאקסל
- ✅ PWA / mobile / bottom-nav

### לא עובד / מושבת:
- ❌ סנכרון אוטומטי של מיילי ספקים מ-Gmail
- ❌ Backfill של attachments ממיילים ישנים
- ❌ Re-download של attachments פגומים מ-Gmail
- ❌ הצעות אוטומטיות "משלוח חדש זוהה ממייל"

> **חשוב:** המסמכים שכבר הורדו ל-`backend/uploads/documents/` ממשיכים להיות זמינים גם במצב Google-down.

---

## 4. איך לעבור למצב ידני (Google מושעה)

### שלב 1 — כבה את Gmail integration
```bash
# בקובץ backend/.env (או as OS env var):
GMAIL_DISABLED=true
```
הפעל מחדש את ה-backend.

### שלב 2 — אמת שה-login עדיין עובד
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your password>"}'
```
אמור להחזיר 200 + access_token.

### שלב 3 — בדוק את ה-UI
- פתח http://localhost:5173
- היכנס עם המשתמש הרגיל שלך
- בדשבורד תראה באנר אפור: "🛑 Gmail מנותק זמנית — מצב ידני בלבד"
- **כל** השאר עובד רגיל.

### שלב 4 — חזרה למצב רגיל
כשהחשבון משוחרר/הוחלף:
1. הסר `GMAIL_DISABLED=true` מה-env (או `GMAIL_DISABLED=false`)
2. הפעל מחדש את ה-backend
3. ב-Dashboard לחץ "חבר Gmail" → אישור Google → חזרה
4. לחץ "Sync Gmail" כדי למשוך את המיילים שהצטברו

---

## 5. Emergency Admin (Break-Glass)

אם **גם** אובדה הסיסמה של ה-admin הרגיל, או שהטבלת users נמחקה / נעולה:

### הפעלה
```bash
# בקובץ backend/.env:
EMERGENCY_ADMIN_USERNAME=ceo_emergency
EMERGENCY_ADMIN_PASSWORD=Tt7K$pQ9wXm2vN8r-changeme!
```
הפעל מחדש את ה-backend.

### שימוש
- היכנס עם השם והסיסמה שהגדרת
- עובד **גם** אם ה-DB ריק / corrupted / נעול
- מקבל הרשאת `admin` מלאה
- **לא** נשמר בטבלת users (id = -1, סינתטי)
- כל שינוי שעושה הוא מקבל attribution `Emergency Admin` בלוג

### נקודות חשובות
- **אל תשאיר משתמש זה דלוק** ביום-יום — יוצר חור אבטחה. הסר את ה-env vars אחרי השימוש.
- מומלץ סיסמה ארוכה אקראית: `python -c "import secrets; print(secrets.token_urlsafe(24))"`
- אם תשנה את ה-env בזמן שמישהו מחובר עם החשבון הזה — ה-token שלו יבוטל מיידית בקריאה הבאה.
- ה-bcrypt לא משחק כאן — ההשוואה היא string מול env var. לכן ה-password חייב להיות חזק אקראי.
- מתועד ב-warning log בכל login.

---

## 6. רשימת תרחישים נפוצים

| תרחיש | מה לעשות |
|---|---|
| חשבון Google הושעה זמנית | `GMAIL_DISABLED=true` עד שמשוחרר |
| חשבון Google הוחלף | `/gmail/disconnect` → `/gmail/connect` עם החשבון החדש |
| Token Gmail פג תוקף | `/gmail/connect` שוב — refresh אוטומטי |
| credentials.json נמחק | הורד מחדש מ-Google Cloud Console והעלה ל-`backend/` |
| OAuth client_id נחסם ע״י Google | צור OAuth client חדש ב-Console + הורד credentials חדש |
| Quota exceeded ב-Gmail API | המתן (איפוס יומי) או הגדל ב-Google Cloud Console |
| אין אינטרנט | הכל עובד מקומית. Gmail sync יחזיר 503. |
| DB נעול / corrupted | הפעל emergency admin (סעיף 5) |
| שכחת סיסמה של admin | הפעל emergency admin → היכנס → Reset Password למשתמש |

---

## 7. נקודות חיבור בקוד (לא לגעת בלי הבנה)

| קובץ | מה הוא עושה |
|---|---|
| `backend/app/services/auth_service.py` | **לא** קורא ל-Google. Local bcrypt+JWT בלבד. |
| `backend/app/services/auth_service.py::_emergency_admin()` | בונה משתמש סינתטי מ-env. id=-1 קבוע. |
| `backend/app/routers/auth.py` | `/auth/login`, `/me`, `/logout`, `/change-password` — מקומי לחלוטין. |
| `backend/app/routers/gmail.py::_check_enabled()` | חוסם את כל ה-`/gmail/*` mutations כש-`GMAIL_DISABLED=true`. |
| `backend/app/services/gmail_service.py` | **כל** הקריאות ל-Google כאן. שום מודול אחר לא מייבא googleapiclient. |
| `backend/app/services/email_sync_service.py::sync_now()` | Stub — לא קורא ל-Google. הוא הג'וב ההורי מ-APScheduler. |
| `backend/app/main.py::background_jobs()` | קורא ל-`scan_alerts` + `sync_now()` (stub). אין קשר ל-Google. |

---

## 8. Verification

לאחר כל שינוי בתלויות Google, הרץ:

```bash
cd backend && ./.venv/Scripts/python.exe -c "
import importlib, sys
# Confirm auth doesn't import any google.* module transitively
import app.services.auth_service
forbidden = [m for m in sys.modules if m.startswith('google')]
print('google modules loaded by auth_service:', forbidden or 'NONE ✓')
"
```

צריך להחזיר `NONE ✓`.
