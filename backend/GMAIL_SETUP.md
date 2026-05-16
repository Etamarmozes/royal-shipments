# Gmail Integration — Setup & Usage

חיבור ה-MVP ל-Gmail API דרך OAuth2. שלב זה רק **מושך** מיילים ושומר אותם ב-`EmailUpdate` עם `status='fetched'`. הפרסור / זיהוי SHP-IDs / יצירת PendingShipment **לא רצים בשלב הזה** — זה ייעשה בנפרד בשלב הבא.

---

## שלב חד-פעמי: יצירת credentials.json ב-Google Cloud

1. היכנס ל-https://console.cloud.google.com/
2. צור פרויקט חדש (או בחר קיים), למשל "Royal Linen Shipments".
3. **הפעל את Gmail API:**
   - APIs & Services → Library
   - חפש "Gmail API" → Enable
4. **הגדר OAuth consent screen:**
   - APIs & Services → OAuth consent screen
   - User type: **External**
   - App name: Royal Linen Shipments
   - User support email + Developer email: הכתובת שלך
   - Scopes: הוסף `https://www.googleapis.com/auth/gmail.readonly`
   - Test users: הוסף את `royallinenshipments@gmail.com`
5. **צור OAuth Client ID:**
   - APIs & Services → Credentials → Create credentials → OAuth client ID
   - Application type: **Web application**
   - Name: Royal Linen Backend
   - Authorized redirect URIs: הוסף **בדיוק** את הכתובת:
     ```
     http://localhost:8000/gmail/callback
     ```
   - Create
6. **הורד את ה-credentials JSON**:
   - בעמוד Credentials → לחץ על שם ה-Client ID שיצרת → "Download JSON"
   - שמור בשם `credentials.json` בתיקייה: `backend/credentials.json`

> **חשוב:** הקובץ `credentials.json` מכיל סוד. הוא כבר ב-`.gitignore`. אל תעלה אותו ל-Git.

---

## שימוש

### 1. אישור חד-פעמי (הסכמת המשתמש)

פתח בדפדפן (כשהשרת רץ):
```
http://localhost:8000/gmail/connect
```

המערכת תפנה אותך למסך הסכמה של Google. בחר את החשבון `royallinenshipments@gmail.com` → אשר את הגישה לקריאת מיילים → תוחזר אוטומטית ל-frontend (`http://localhost:5173/email-updates?gmail=connected`).

הטוקן יישמר ב-`backend/data/gmail_token.json` (גם הוא ב-`.gitignore`).

### 2. בדיקת סטטוס

```bash
curl http://localhost:8000/gmail/status
```
תוצאה אופיינית אחרי חיבור:
```json
{
  "connected": true,
  "token_file_exists": true,
  "credentials_file_exists": true,
  "expiry": "2026-05-02T23:00:00",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
}
```

### 3. סנכרון מיילים

```bash
curl -X POST http://localhost:8000/gmail/sync
```

תוצאה:
```json
{
  "query": "newer_than:7d is:unread -in:spam -in:trash",
  "matched": 23,
  "inserted": 18,
  "skipped_existing": 5,
  "errors": [],
  "synced_at": "2026-05-02T22:15:00"
}
```

- `matched` — כמה מיילים תאמו ל-query
- `inserted` — כמה חדשים נוספו ל-DB
- `skipped_existing` — נמשכו אבל כבר קיימים (לפי `email_message_id`) — נדלגים
- `errors` — שגיאות פר-מייל (אם היו)

### 4. ניתוק

```bash
curl -X POST http://localhost:8000/gmail/disconnect
```
מוחק את `gmail_token.json`. בפעם הבאה צריך להריץ שוב `/gmail/connect`.

---

## מה נשמר ב-EmailUpdate

לכל מייל שנמשך נוצרת רשומה עם:
- `email_message_id` — Gmail message ID (משמש ל-dedup)
- `email_thread_id` — Gmail thread ID
- `sender` — From header
- `subject` — Subject header
- `received_at` — מועד קבלה (מ-Date header, fallback ל-internalDate)
- `body_excerpt` — 500 תווים ראשונים של גוף הטקסט
- `full_body_text` — גוף מלא כטקסט (אם המייל ב-HTML — מנקה תגיות)
- `attachment_names` — רשימת שמות קבצים מצורפים (ללא הורדה כרגע)
- `status` — תמיד `"fetched"` בשלב הזה
- `detection_type`, `detected_fields_json`, `confidence_score` — **כולם NULL** (אין parsing עדיין)

מצב ה-`status` כשלב המשך:
- `fetched` ← אחרי `/gmail/sync` (החדש)
- `pending` / `needs_review` / `approved` / `rejected` ← לאחר parsing (שלב הבא)

---

## הגדרות ב-config.py

```python
GMAIL_SYNC_DAYS = 7              # חלון סריקה (ימים אחורה)
GMAIL_SYNC_MAX_MESSAGES = 100    # תקרת מיילים לפר-קריאה
GMAIL_PREFER_UNREAD = True       # רק unread (אפשר לשנות ל-False)
GMAIL_REDIRECT_URI = "http://localhost:8000/gmail/callback"
GMAIL_FRONTEND_RETURN_URL = "http://localhost:5173/email-updates"
```

---

## לוגים

ה-service רושם לוגים ברורים תחת logger בשם `"gmail"`:
- `Gmail OAuth: building authorization URL`
- `Gmail OAuth: state=<short>`
- `Gmail OAuth: token stored — has_refresh=True, expiry=...`
- `Gmail OAuth: token expired, refreshing`
- `Gmail SYNC start`
- `Gmail SYNC: query=...`
- `Gmail SYNC: N messages match query`
- `Gmail SYNC: fetching message k/N id=...`
- `Gmail SYNC done — inserted=X, skipped_existing=Y, errors=Z`

הם מודפסים ל-stdout של uvicorn ב-format:
```
2026-05-02 22:15:00 [INFO] gmail: Gmail SYNC: 23 messages match query
```

---

## מה עוד לא נבנה (במכוון, לפי הבריף הנוכחי)

- **Parsing המיילים** (זיהוי SHP-IDs, ETA, container numbers) — בקובץ `email_parser_service.py` יש את ה-regex parser, אבל הוא לא מופעל אוטומטית על מיילים שנמשכים מ-Gmail.
- **הורדת קבצים מצורפים** — שמורים רק שמות, לא תוכן. בשלב הבא נוסיף `download_attachment(message_id, attachment_id)`.
- **Polling אוטומטי כל שעה** — APScheduler קיים אבל קורא רק ל-`alert_service.scan_alerts` ול-stub של `email_sync_service.sync_now`. צריך להוסיף `gmail_service.sync_inbox(db)` ל-`background_jobs()`.

כל אלה מתוכננים לשלב הבא, אחרי שאישרת שהחיבור הראשוני עובד.
