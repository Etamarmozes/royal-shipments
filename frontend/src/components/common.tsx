import { ReactNode } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";

export function PageHeader({
  title, subtitle, actions,
}: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Loader({ text = "טוען..." }: { text?: string }) {
  return (
    <div className="flex items-center justify-center py-10 text-slate-500">
      <div className="animate-pulse">{text}</div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  iconName,
  action,
  tone = "default",
}: {
  title: string;
  description?: string;
  /** Legacy prop — emoji or short string. Kept for backward-compat. */
  icon?: string;
  /** Preferred — name of an icon from the new SVG library. */
  iconName?: IconName;
  /** Optional CTA — supports either a router link (`to`) or a click handler. */
  action?: { label: string; to?: string; onClick?: () => void };
  /** Visual tone — default | info | success | warning. */
  tone?: "default" | "info" | "success" | "warning";
}) {
  const toneCls = {
    default: "border-slate-200 text-slate-400",
    info:    "border-blue-200 text-blue-500",
    success: "border-emerald-200 text-emerald-500",
    warning: "border-amber-200 text-amber-500",
  }[tone];
  return (
    <div className={clsx("card text-center py-10", toneCls)}>
      {iconName ? (
        <div className="flex items-center justify-center mb-3">
          <Icon name={iconName} size={40} className="opacity-70" />
        </div>
      ) : icon ? (
        <div className="text-4xl mb-2" aria-hidden>{icon}</div>
      ) : (
        <div className="flex items-center justify-center mb-3">
          <Icon name="dot" size={40} className="opacity-50" />
        </div>
      )}
      <div className="font-semibold text-slate-700">{title}</div>
      {description && (
        <div className="text-sm text-slate-500 mt-1 max-w-md mx-auto">{description}</div>
      )}
      {action && (
        <div className="mt-4">
          {action.to ? (
            <Link to={action.to} className="btn-primary inline-flex">{action.label}</Link>
          ) : (
            <button onClick={action.onClick} className="btn-primary">{action.label}</button>
          )}
        </div>
      )}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "שגיאה לא ידועה";
  return (
    <div className="card border-red-200 bg-red-50">
      <div className="font-semibold text-red-800">שגיאה</div>
      <div className="text-sm text-red-700 mt-1">{message}</div>
    </div>
  );
}

export function KpiCard({
  label, value, hint, tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "warning" | "danger" | "success" | "info";
}) {
  const toneClass = {
    default: "border-slate-200",
    warning: "border-amber-300 bg-amber-50",
    danger: "border-red-300 bg-red-50",
    success: "border-emerald-300 bg-emerald-50",
    info: "border-blue-300 bg-blue-50",
  }[tone];
  return (
    <div className={clsx("card", toneClass)}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
      {hint && <div className="text-xs text-slate-400 mt-1">{hint}</div>}
    </div>
  );
}

export function Section({
  title, action, children,
}: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="card mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}
