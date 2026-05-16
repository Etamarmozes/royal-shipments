import { format, parseISO, differenceInDays } from "date-fns";
import { he } from "date-fns/locale";

export function fmtDate(s?: string | null): string {
  if (!s) return "—";
  try {
    return format(parseISO(s), "dd/MM/yyyy", { locale: he });
  } catch {
    return s;
  }
}

export function fmtDateTime(s?: string | null): string {
  if (!s) return "—";
  try {
    return format(parseISO(s), "dd/MM/yyyy HH:mm", { locale: he });
  } catch {
    return s;
  }
}

export function daysFromNow(s?: string | null): number | null {
  if (!s) return null;
  try {
    return differenceInDays(parseISO(s), new Date());
  } catch {
    return null;
  }
}

export function fmtNumber(n?: number | null, digits = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("he-IL", { maximumFractionDigits: digits });
}

export function loadStatusColor(s: string): string {
  switch (s) {
    case "פנוי":
      return "badge-green";
    case "רגיל":
      return "badge-blue";
    case "עמוס":
      return "badge-amber";
    case "חריג":
      return "badge-red";
    default:
      return "badge-gray";
  }
}

export function severityColor(s: string): string {
  switch (s) {
    case "critical":
    case "high":
      return "badge-red";
    case "medium":
      return "badge-amber";
    case "low":
      return "badge-blue";
    default:
      return "badge-gray";
  }
}

export function stageLabel(stage?: number | null): string {
  if (!stage) return "—";
  const stages: Record<number, string> = {
    1: "1 — הזמנה",
    2: "2 — אישור הזמנה",
    3: "3 — ייצור",
    4: "4 — מוכן ליציאה",
    5: "5 — בוקינג",
    6: "6 — בים/בדרך",
    7: "7 — עדכונים שוטפים",
    8: "8 — שחרור מכס",
    9: "9 — הגעה למחסן",
  };
  return stages[stage] || `${stage}`;
}
