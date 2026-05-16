# Shipment Data Import — Excel Workflow

## TL;DR
1. הורד תבנית: `Sidebar → ייבוא מאקסל → הורד shipment_import_template.xlsx`
2. מלא את הקובץ (מחק את שורות הדוגמה הכתומות).
3. העלה אותו → תקבל **תצוגה מקדימה**.
4. סמן לכל שורה: צור חדש / עדכן קיים / דלג.
5. לחץ "אשר וייבא".

**אף שורה לא נכתבת ל-DB עד שאתה מאשר. אף משלוח קיים לא נדרס.**

---

## למה עכשיו?

יש כרגע 7 רשומות במערכת. כולן demo/test (SHP-006…SHP-011 מ-seed,
SHP-012 ממייל בדיקה). הנתונים האמיתיים של Royal Linen נמצאים במייל של Jacob.
לפני שמחברים את ה-email sync, רוצים יבוא חד-פעמי מסודר מאקסל.

---

## איפה זה במערכת

| תפריט | URL | מי רואה |
|---|---|---|
| ייבוא מאקסל | `/import-excel` | admin / import_manager |
| בדיקת נתונים קיימים | `/data-review` | admin / import_manager |

שתי השורות החדשות בסיידבר — אייקון 📊 ו-🧪.

---

## עמודות התבנית

| מפתח | תווית עברית | חובה? | סוג | הערות |
|---|---|---|---|---|
| `shipment_reference` | מס' משלוח (SHP-XXX) | לא | str | ריק → הקצאה אוטומטית |
| `supplier_name` | ספק | **כן** | str | השדה היחיד החובה |
| `brand` | מותג | לא | str | |
| `category` | קטגוריה | לא | str | מתוך הרשימה המבוקרת |
| `purchase_order_number` | PO | לא | str | dedup key |
| `invoice_number` | Invoice | לא | str | dedup key |
| `packing_list_number` | Packing List No. | לא | str | |
| `bill_of_lading_number` | BL / BOL | לא | str | dedup key |
| `forwarder_name` | עמיל | לא | str | מאוחסן ב-`customs_broker` |
| `shipping_company` | חברת שילוח | לא | str | מאוחסן ב-`shipping_channel` |
| `vessel_name` | אוניה | לא | str | |
| `container_number` | מספר מכולה | לא | str | dedup key |
| `container_type` | סוג מכולה | לא | str | 40HC / 20GP / 40HQ … |
| `origin_country` | מדינת מקור | לא | str | |
| `origin_port` | נמל יציאה | לא | str | |
| `destination_port` | נמל יעד | לא | str | |
| `destination_warehouse` | מחסן יעד | לא | str | |
| `incoterm` | Incoterm | לא | str | FOB/CIF/EXW/DAP/DDP |
| `shipment_status` | סטטוס | לא | str | ordered/in_transit/arrived/received/delayed/cancelled |
| `etd` | ETD | לא | date | YYYY-MM-DD |
| `eta_port` | ETA נמל | לא | date | |
| `eta_warehouse` | ETA מחסן | לא | date | |
| `actual_arrival_port` | הגעה בפועל לנמל | לא | date | |
| `actual_arrival_warehouse` | הגעה בפועל למחסן | לא | date | |
| `number_of_cartons` | כמות קרטונים | לא | int | |
| `number_of_pallets` | כמות משטחים | לא | int | אם ריק — חישוב אוטומטי |
| `gross_weight` | משקל ברוטו (ק״ג) | לא | float | |
| `cbm` | CBM | לא | float | |
| `shipment_value` | ערך משלוח | לא | float | |
| `currency` | מטבע | לא | str | USD/EUR/ILS/CNY/INR |
| `payment_status` | סטטוס תשלום | לא | str | paid/partial/unpaid/pending |
| `customs_status` | סטטוס מכס | לא | str | pending/released/held |
| `documents_status` | סטטוס מסמכים | לא | str | complete/partial/missing |
| `invoice_received` | Invoice התקבל? | לא | bool | yes/no |
| `packing_list_received` | Packing List התקבל? | לא | bool | yes/no |
| `bl_received` | BL התקבל? | לא | bool | yes/no |
| `certificate_received` | תעודה התקבלה? | לא | bool | yes/no |
| `other_documents_missing` | מסמכים חסרים אחרים | לא | str | טקסט חופשי |
| `notes` | הערות | לא | str | |
| `internal_owner` | אחראי פנים-ארגוני | לא | str | |
| `priority` | עדיפות | לא | str | low/normal/high/urgent |

### מבנה הקובץ
- **שורה 1**: הוראות (טקסט)
- **שורה 2**: תוויות עברית
- **שורה 3**: מפתחות טכניים (אנגלית — חובה!)
- **שורה 4**: שורה ריקה
- **שורות 5-7**: שורות לדוגמה (כתום בהיר, יסוננו אוטומטית — מכילות `SAMPLE-`)
- **שורות 8+**: הנתונים שלך

הקובץ כולל **גליון "README"** עם הוראות + **Data Validation** במדיניות הסטטוסים.

---

## כפילויות

המערכת בודקת התאמה לפי **4 מפתחות** (לפי סדר עדיפות):

1. `shipment_reference` (SHP-XXX) — ההתאמה החזקה ביותר
2. `bill_of_lading_number` — שטר מטען
3. `invoice_number` — חשבונית
4. `container_number` — מספר מכולה

אם אחד מהם תואם לרשומה קיימת, השורה מסומנת **"עדכון קיים"** והפעולה
המוצעת היא `update`. אחרת — `create`.

### מספר מכולות באותו משלוח
שורה אחת לכל מכולה. כל השורות עם אותו `shipment_reference` נחשבות לאותו
משלוח. השורה הראשונה קובעת את שדות המשלוח (ספק, ETA, וכו'); כל שורה
מוסיפה מכולה משלה.

---

## תצוגה מקדימה

לכל שורה תראה:
- **חיווי כפילות** — אם נמצאה התאמה, איזה שדה התאים (`matched_by`)
- **שגיאות** — אם supplier ריק או תאריך לא תקני
- **דרופ-דאון פעולה** — `create` / `update` / `skip` (ברירת המחדל לפי המצב)

הסיכום למעלה מראה: סה״כ שורות / חדשים / עדכון / שגיאות / ספקים שונים.

לאחר אישור, ה-backend דורש body של `{"rows": [...], "confirm": "APPLY"}`.
ללא מחרוזת `APPLY` מוחזר 400 — מגן מפני קליק בטעות.

---

## Audit log

כל שורה מיובאת יוצרת event ב-`shipment_events`:
- `action_type`: `excel_import_create` או `excel_import_update`
- `source`: `excel_import`
- `changed_by`: שם המשתמש המאומת
- `note`: רשימת השדות שעודכנו

ניתן לראות את הלוג ב-`/history` או ב-tab "היסטוריית שינויים" בפרופיל המשלוח.

---

## Manual override interaction

אם משלוח **קיים** עם שדה שמסומן `manual_overrides` (נערך ידנית במערכת),
היבוא **לא ידרוס** את השדה הזה — גם אם בקובץ Excel יש ערך אחר. השדה
מוצג ב-UI עם תג 🔒 ידני. זה מבטיח שלא תאבד עריכות ידניות אם תייבא שוב.

---

## הרשאות

| תפקיד | הרשאות יבוא |
|---|---|
| `admin` | הורד תבנית, preview, apply, flag, purge |
| `import_manager` | הורד תבנית, preview, apply, flag (ללא purge) |
| `warehouse` | אין |
| `viewer` | אין |

`purge-test-data` דורש `shipment.delete` (admin בלבד) **וגם** מחרוזת אישור
`"DELETE"` ב-body.

---

## בדיקה (13/13 ✓)

| # | בדיקה | תוצאה |
|---|---|---|
| 1 | הורדת תבנית | 11489 bytes, signature PK ✓ |
| 2 | תצוגה מקדימה של תבנית ריקה | 0 שורות נטו (sample-rows סוננו) |
| 3 | שורה עם supplier חסר | מסומנת `error`: "שדה חובה ריק: supplier_name" |
| 4 | יבוא 2 מכולות באותו משלוח | created=1 shipment, containers=2 |
| 5 | זיהוי כפילות בהעלאה חוזרת | פעולה מוצעת = `update` ל-2 השורות |
| 6 | apply ללא `confirm: APPLY` | HTTP 400 |
| 7 | קובץ פגום | `file_errors` עם הודעה ברורה |
| 8 | Data Review מסווג נכון | excel-imported = `data_source: excel`, לא חשוד |
| 9 | סימון test + purge | מחק 1 רשומה |
| 10 | רשומות קיימות לא נגעו | 7/7 SHP-006…SHP-012 שלמים |
| 11 | Audit | excel/flag/purge events נרשמו |
| 12 | Viewer חסום | 4×403 (preview/apply/flag/purge) |

---

## פתרון בעיות

| בעיה | פתרון |
|---|---|
| "לא זוהתה כותרת תקנית" | ודא ששורה 3 מכילה את המפתחות הטכניים באנגלית (`supplier_name`, וכו'). השתמש בתבנית הרשמית. |
| "שדה חובה ריק: supplier_name" | מלא את עמודת הספק. אם השורה ריקה לחלוטין, היא תסונן אוטומטית. |
| כל השורות `error` | בדוק את שורת המפתחות הטכניים (3) — אולי נמחקה |
| תאריכים לא נקלטים | פורמט: YYYY-MM-DD (גם DD/MM/YYYY ו-DD-MM-YYYY מתקבלים) |
| מכולה כבר משויכת למשלוח אחר | ה-import מדלג ומציג זאת ב-`details`. שנה ידנית במערכת. |

---

## מה הלאה

אחרי שהיבוא מהאקסל עובד, השלבים הבאים (לא בנויים עדיין):

1. **חיבור Gmail של Jacob** — phase 3
2. **AI extraction מהמיילים** — phase 4
3. **Pending Email Updates screen** — phase 4
4. **Smart matching** — phase 5

ראה [`EMAIL_SYNC_APPROVAL_WORKFLOW.md`](./EMAIL_SYNC_APPROVAL_WORKFLOW.md).
