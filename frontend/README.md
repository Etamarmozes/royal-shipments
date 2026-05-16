# Royal Linen Shipments — Frontend

React + TypeScript + Tailwind, RTL מלא בעברית.

## דרישות
- Node.js 18+

## התקנה והרצה

```bash
cd frontend
npm install
npm run dev
```

האפליקציה תרוץ ב-http://localhost:5173 ותתחבר אוטומטית ל-Backend ב-http://localhost:8000 דרך Vite proxy.

לבנייה לפרודקשן:
```bash
npm run build
npm run preview
```

## מסכים

| מסך | נתיב |
|------|------|
| דשבורד | `/` |
| משלוחים פעילים | `/shipments` |
| פרופיל משלוח | `/shipments/:id` |
| מכולות | `/containers` |
| תחזית 8 שבועות | `/forecast` |
| מרכז עדכונים ממייל | `/email-updates` |
| משלוחים חדשים לאישור | `/pending-shipments` |
| תוספות עבודה | `/extra-work` |
| התראות | `/alerts` |
| היסטוריה | `/history` |

## Stack
- Vite + React 18 + TypeScript
- Tailwind CSS (RTL)
- TanStack Query לניהול בקשות
- React Router
- Axios
- date-fns בעברית
