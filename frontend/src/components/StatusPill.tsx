/**
 * StatusPill — icon + color + label.  Never color-only.
 *
 * Two ways to use:
 *
 *   1. With a semantic `kind` (preferred — gives consistent icon+color+label):
 *        <StatusPill kind="in_transit"/>
 *
 *   2. Custom (for one-off cases where the kinds don't fit):
 *        <StatusPill icon="alert" tone="danger" label="ניירת חסרה"/>
 *
 * Sizes:
 *   <StatusPill size="sm" .../>   (default — table rows)
 *   <StatusPill size="md" .../>   (cards / panels)
 */
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";

export type StatusKind =
  | "in_transit"      // משלוח בדרך
  | "arrived"         // הגיע
  | "delayed"         // מתעכב
  | "customs"         // במכס
  | "port"            // בנמל
  | "warehouse"       // במחסן
  | "missing_docs"    // ניירת חסרה
  | "needs_review"    // לבדיקה
  | "approved"        // אושר
  | "rolled_back"     // בוטל / חזר אחורה
  | "neutral";        // ניטרלי / ללא סטטוס

type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "muted";

const TONE_CLS: Record<Tone, string> = {
  neutral: "bg-slate-50 text-slate-700 border-slate-200",
  info:    "bg-blue-50 text-blue-800 border-blue-200",
  success: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger:  "bg-rose-50 text-rose-800 border-rose-200",
  muted:   "bg-slate-50 text-slate-500 border-slate-200",
};

interface KindPreset {
  tone: Tone;
  icon: IconName;
  label: string;
}

const KIND_PRESET: Record<StatusKind, KindPreset> = {
  in_transit:   { tone: "info",    icon: "ship",        label: "בדרך" },
  arrived:      { tone: "success", icon: "check",       label: "הגיע" },
  delayed:      { tone: "warning", icon: "clock_alert", label: "מתעכב" },
  customs:      { tone: "warning", icon: "customs",     label: "במכס" },
  port:         { tone: "info",    icon: "anchor",      label: "בנמל" },
  warehouse:    { tone: "neutral", icon: "warehouse",   label: "במחסן" },
  missing_docs: { tone: "danger",  icon: "alert",       label: "ניירת חסרה" },
  needs_review: { tone: "warning", icon: "eye",         label: "לבדיקה" },
  approved:     { tone: "success", icon: "check",       label: "אושר" },
  rolled_back:  { tone: "muted",   icon: "rollback",    label: "בוטל" },
  neutral:      { tone: "neutral", icon: "dot",         label: "—" },
};

interface BaseProps {
  size?: "sm" | "md";
  className?: string;
}

interface KindProps extends BaseProps {
  kind: StatusKind;
  /** Optional override of the preset label (icon + tone stay from the kind). */
  label?: string;
  /** Optional override of the preset icon. */
  icon?: IconName;
  /** Optional override of the preset tone. */
  tone?: Tone;
}

interface CustomProps extends BaseProps {
  kind?: undefined;
  icon: IconName;
  tone?: Tone;
  label: string;
}

type Props = KindProps | CustomProps;

const SIZE_CLS = {
  sm: "px-1.5 py-0.5 text-[11px] leading-tight gap-1",
  md: "px-2.5 py-1 text-xs leading-snug gap-1.5",
} as const;

const ICON_SIZE = { sm: 12, md: 14 } as const;

export function StatusPill(props: Props) {
  const size = props.size ?? "sm";
  const cls = props.className;

  const preset = props.kind ? KIND_PRESET[props.kind] : null;
  const icon: IconName = props.icon ?? preset?.icon ?? "dot";
  const tone: Tone = props.tone ?? preset?.tone ?? "neutral";
  const label: string = props.label ?? preset?.label ?? "";

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border font-medium whitespace-nowrap",
        SIZE_CLS[size],
        TONE_CLS[tone],
        cls,
      )}
      // Color-blind safety: title surfaces the same info as the icon+label
      title={label}
    >
      <Icon name={icon} size={ICON_SIZE[size]} aria-hidden />
      {label && <span>{label}</span>}
    </span>
  );
}

/**
 * Helper — derive a StatusKind from a Shipment row.
 * Centralised so the badge is consistent across pages.
 */
export function shipmentStatusKind(s: {
  delay_status?: boolean | null;
  paperwork_complete?: boolean | null;
  current_stage?: number | null;
  archived?: boolean | null;
  actual_arrival_warehouse?: string | null;
  actual_arrival_israel?: string | null;
}): StatusKind {
  if (s.archived) return "rolled_back";
  if (s.actual_arrival_warehouse) return "warehouse";
  if (s.actual_arrival_israel) return "arrived";
  if (s.delay_status) return "delayed";
  if (s.paperwork_complete === false && (s.current_stage ?? 0) >= 7) return "missing_docs";
  const stage = s.current_stage ?? 0;
  if (stage >= 8) return "customs";
  if (stage >= 6) return "in_transit";
  return "neutral";
}
