/**
 * ShipmentTimeline — first version (Phase 1).
 *
 * Maps `current_stage` (1..9) to the lifecycle:
 *   1 PO        → 2 confirmed → 3 production → 4 ready → 5 booked
 *   → 6 in transit → 7 updates → 8 customs → 9 warehouse
 *
 * Visual only. Does NOT mutate state, does NOT call APIs, does NOT
 * make assumptions when current_stage is null/0 (renders all stages
 * as pending without crashing).
 *
 * The component uses `flex-row-reverse` so in RTL the user reads it as
 * a left-to-right *progress* (oldest stage on the right, latest on
 * the left), matching how Hebrew text flows on a page.
 */
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";

interface StageDef {
  n: number;
  key: string;
  label: string;
  shortLabel: string;
  icon: IconName;
}

const STAGES: StageDef[] = [
  { n: 1, key: "po",         label: "הזמנה",            shortLabel: "PO",          icon: "clipboard" },
  { n: 2, key: "confirmed",  label: "אישור הזמנה",      shortLabel: "אישור",       icon: "check" },
  { n: 3, key: "production", label: "ייצור",            shortLabel: "ייצור",       icon: "factory" },
  { n: 4, key: "ready",      label: "מוכן ליציאה",       shortLabel: "מוכן",        icon: "carton" },
  { n: 5, key: "booked",     label: "בוקינג",           shortLabel: "בוקינג",      icon: "container" },
  { n: 6, key: "in_transit", label: "בים / בדרך",       shortLabel: "בדרך",        icon: "ship" },
  { n: 7, key: "updates",    label: "עדכונים שוטפים",   shortLabel: "עדכונים",     icon: "refresh" },
  { n: 8, key: "customs",    label: "שחרור מכס",        shortLabel: "מכס",         icon: "customs" },
  { n: 9, key: "warehouse",  label: "הגעה למחסן",       shortLabel: "מחסן",        icon: "warehouse" },
];

type StageState = "done" | "current" | "pending";

function stateOf(stageN: number, current: number): StageState {
  if (current <= 0) return "pending";
  if (stageN < current) return "done";
  if (stageN === current) return "current";
  return "pending";
}

const STATE_CLS: Record<StageState, string> = {
  done:    "bg-emerald-50 text-emerald-800 border-emerald-200",
  current: "bg-blue-50 text-blue-800 border-blue-300 ring-2 ring-blue-200/60",
  pending: "bg-slate-50 text-slate-500 border-slate-200",
};

const CONNECTOR_CLS: Record<StageState, string> = {
  done:    "bg-emerald-200",
  current: "bg-blue-200",
  pending: "bg-slate-200",
};

interface ShipmentTimelineProps {
  /** 1..9 — or null/undefined when no stage is set. */
  currentStage?: number | null;
  /** Compact mode — smaller pills, no labels on hover-targets >= md. */
  compact?: boolean;
  /** Click handler when a stage is clicked. Stage number passed. */
  onStageClick?: (stage: number) => void;
  className?: string;
}

export default function ShipmentTimeline({
  currentStage,
  compact = false,
  onStageClick,
  className,
}: ShipmentTimelineProps) {
  const cur = Number(currentStage ?? 0) | 0;

  return (
    <div
      role="region"
      aria-label="ציר חיי משלוח"
      className={clsx(
        "card overflow-x-auto py-3 px-2",
        compact && "py-2",
        className,
      )}
    >
      {/* Caption row — gives non-tech users an obvious heading */}
      <div className="flex items-center justify-between mb-2 px-1">
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
          מחזור חיי משלוח
        </h3>
        <span className="text-[11px] text-slate-500">
          {cur > 0
            ? <>שלב נוכחי: <span className="font-semibold text-slate-700">{cur}/9</span></>
            : <>שלב לא נקבע</>}
        </span>
      </div>

      <ol
        role="list"
        className={clsx(
          // flex-row-reverse: in RTL pages, this places stage 1 on the right
          // and stage 9 on the left — matching Hebrew reading flow.
          "flex flex-row-reverse items-stretch gap-0",
          "min-w-max",
        )}
      >
        {STAGES.map((s, idx) => {
          const st = stateOf(s.n, cur);
          const isLast = idx === STAGES.length - 1;
          const Tag = onStageClick ? "button" : "div";
          return (
            <li key={s.key} className="flex items-center shrink-0">
              <Tag
                type={onStageClick ? "button" : undefined}
                onClick={onStageClick ? () => onStageClick(s.n) : undefined}
                aria-current={st === "current" ? "step" : undefined}
                title={`${s.n}. ${s.label}`}
                className={clsx(
                  "inline-flex items-center gap-1.5 rounded-md border",
                  compact ? "px-1.5 py-1 text-[11px]" : "px-2 py-1.5 text-xs",
                  "transition-colors duration-150",
                  STATE_CLS[st],
                  onStageClick && "hover:opacity-90 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brand-500/40",
                )}
              >
                <Icon name={s.icon} size={compact ? 12 : 14} aria-hidden />
                <span className="font-semibold">{s.n}</span>
                <span className="hidden md:inline">{compact ? s.shortLabel : s.label}</span>
              </Tag>
              {!isLast && (
                <span
                  aria-hidden
                  className={clsx(
                    "h-0.5 w-3 sm:w-4 lg:w-6 mx-0.5 rounded-full",
                    CONNECTOR_CLS[st],
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
