/**
 * Royal Tracker — single-source icon library.
 *
 * Design rules:
 *   • Outline-style monochrome SVG using `currentColor`.
 *   • viewBox 0 0 24 24, default render 18×18 (overridable via `size`).
 *   • All semantic icons are NON-DIRECTIONAL — they do NOT mirror in RTL.
 *     Only directional icons (arrow_back, arrow_next) flip via the consumer.
 *   • Icon names map roughly to logistics meaning (carton, container, ship,
 *     pallet, warehouse, document, alert, …) so the UI reads literally.
 *
 * Adding a new icon: add an entry to PATHS with a 24×24 line drawing.
 * Use stroke-only paths; fill="none" is set at the wrapper level.
 */
import { SVGAttributes } from "react";
import clsx from "clsx";

export type IconName =
  // logistics — entities
  | "pallet" | "carton" | "container" | "warehouse"
  | "ship" | "truck" | "plane"
  // logistics — documents
  | "document" | "invoice" | "packing_list" | "bl" | "purchase_order"
  | "customs" | "certificate" | "image"
  // navigation
  | "dashboard" | "home" | "tag" | "email" | "star" | "alert" | "history"
  | "users" | "excel" | "import" | "rollback" | "test_tube" | "search"
  | "info" | "receiving" | "settings"
  // status / actions
  | "check" | "clock" | "clock_alert" | "anchor" | "eye" | "pencil"
  | "comment" | "factory" | "clipboard" | "refresh" | "lock" | "dot"
  // arrows (directional — flip in RTL via class="rtl-flip")
  | "arrow_left" | "arrow_right";

interface IconProps extends Omit<SVGAttributes<SVGSVGElement>, "children"> {
  name: IconName;
  size?: number;
  /** stroke width override (default 1.75) */
  weight?: number;
}

/* eslint-disable max-len */
const PATHS: Record<IconName, JSX.Element> = {
  // ----- entities -----
  pallet: (
    <>
      <rect x="2.5" y="13" width="19" height="3" rx="0.5"/>
      <line x1="5" y1="16" x2="5" y2="20"/>
      <line x1="12" y1="16" x2="12" y2="20"/>
      <line x1="19" y1="16" x2="19" y2="20"/>
      <line x1="3" y1="20" x2="21" y2="20"/>
      <line x1="6" y1="9" x2="18" y2="9"/>
      <line x1="6" y1="11" x2="18" y2="11"/>
    </>
  ),
  carton: (
    <>
      <path d="M3.5 7.5 L12 4 L20.5 7.5 L20.5 17 L12 20 L3.5 17 Z"/>
      <line x1="3.5" y1="7.5" x2="12" y2="11"/>
      <line x1="20.5" y1="7.5" x2="12" y2="11"/>
      <line x1="12" y1="11" x2="12" y2="20"/>
      <line x1="8" y1="6" x2="16" y2="6"/>
    </>
  ),
  container: (
    <>
      <rect x="2" y="7" width="20" height="11" rx="1"/>
      <line x1="6" y1="7" x2="6" y2="18"/>
      <line x1="10" y1="7" x2="10" y2="18"/>
      <line x1="14" y1="7" x2="14" y2="18"/>
      <line x1="18" y1="7" x2="18" y2="18"/>
    </>
  ),
  warehouse: (
    <>
      <path d="M3 11 L12 5 L21 11 L21 20 L3 20 Z"/>
      <rect x="9" y="13" width="6" height="7"/>
      <line x1="9" y1="16" x2="15" y2="16"/>
    </>
  ),
  ship: (
    <>
      <path d="M3 14 L12 14 L12 8 L7 8 Z"/>
      <path d="M12 14 L12 9 L17 9 L20 14"/>
      <path d="M2 17 Q5 19 8 17 T14 17 T20 17 L21 14 L3 14 Z"/>
      <line x1="9.5" y1="11" x2="9.5" y2="14"/>
    </>
  ),
  truck: (
    <>
      <rect x="2" y="9" width="11" height="8" rx="0.5"/>
      <path d="M13 11 L17 11 L20 14 L20 17 L13 17 Z"/>
      <circle cx="6.5" cy="18" r="1.6"/>
      <circle cx="16" cy="18" r="1.6"/>
    </>
  ),
  plane: (
    <>
      <path d="M3 13 L21 13 L18 9 L13 9 L11 5 L9 5 L10 9 L6 9 L4 7 L3 7 L4 11 L3 13 Z"/>
      <path d="M9 16 L15 16"/>
    </>
  ),
  // ----- documents -----
  document: (
    <>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z"/>
      <path d="M15 3 L15 7 L19 7"/>
      <line x1="9" y1="12" x2="16" y2="12"/>
      <line x1="9" y1="15" x2="16" y2="15"/>
      <line x1="9" y1="18" x2="13" y2="18"/>
    </>
  ),
  invoice: (
    <>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z"/>
      <path d="M15 3 L15 7 L19 7"/>
      <text x="12" y="17" fontSize="8" textAnchor="middle" stroke="none" fill="currentColor" fontWeight="700">$</text>
      <line x1="9" y1="11" x2="16" y2="11"/>
    </>
  ),
  packing_list: (
    <>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z"/>
      <path d="M15 3 L15 7 L19 7"/>
      <polyline points="8.5,12 10,13.5 12,11"/>
      <line x1="13" y1="12.5" x2="16.5" y2="12.5"/>
      <polyline points="8.5,16 10,17.5 12,15"/>
      <line x1="13" y1="16.5" x2="16.5" y2="16.5"/>
    </>
  ),
  bl: (
    <>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z"/>
      <path d="M15 3 L15 7 L19 7"/>
      <circle cx="12" cy="14" r="3"/>
      <text x="12" y="16" fontSize="3.4" textAnchor="middle" stroke="none" fill="currentColor" fontWeight="700">BL</text>
    </>
  ),
  purchase_order: (
    <>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z"/>
      <path d="M15 3 L15 7 L19 7"/>
      <text x="12" y="16" fontSize="6" textAnchor="middle" stroke="none" fill="currentColor" fontWeight="700">PO</text>
    </>
  ),
  customs: (
    <>
      <circle cx="12" cy="12" r="8"/>
      <circle cx="12" cy="12" r="5" strokeDasharray="2 1.4"/>
      <polyline points="9.5,12.5 11.2,14.2 14.5,10.5"/>
    </>
  ),
  certificate: (
    <>
      <rect x="3" y="4" width="18" height="13" rx="1"/>
      <circle cx="12" cy="11" r="2"/>
      <path d="M11 13 L9.5 17 L12 15.5 L14.5 17 L13 13"/>
    </>
  ),
  image: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="1"/>
      <circle cx="9" cy="10" r="1.5"/>
      <path d="M3 17 L9 12 L13 16 L16 13 L21 18"/>
    </>
  ),
  // ----- navigation -----
  dashboard: (
    <>
      <rect x="3" y="3" width="8" height="8" rx="1"/>
      <rect x="13" y="3" width="8" height="5" rx="1"/>
      <rect x="13" y="10" width="8" height="11" rx="1"/>
      <rect x="3" y="13" width="8" height="8" rx="1"/>
    </>
  ),
  home: (
    <>
      <path d="M3 11 L12 4 L21 11 V20 H14 V14 H10 V20 H3 Z"/>
    </>
  ),
  tag: (
    <>
      <path d="M3 12 L11 4 L21 4 L21 14 L13 22 Z"/>
      <circle cx="17" cy="8" r="1.4"/>
    </>
  ),
  email: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="1"/>
      <polyline points="3,7 12,13 21,7"/>
    </>
  ),
  star: (
    <>
      <path d="M12 3.5 L14.4 9.4 L20.7 9.9 L15.9 14 L17.4 20 L12 16.7 L6.6 20 L8.1 14 L3.3 9.9 L9.6 9.4 Z"/>
    </>
  ),
  alert: (
    <>
      <path d="M12 3.5 L21.5 19.5 L2.5 19.5 Z"/>
      <line x1="12" y1="10" x2="12" y2="14.5"/>
      <circle cx="12" cy="17" r="0.7" fill="currentColor"/>
    </>
  ),
  history: (
    <>
      <path d="M4 12 a8 8 0 1 0 3 -6.3"/>
      <polyline points="3,3 3,7 7,7"/>
      <polyline points="12,8 12,12 15,14"/>
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="9" r="3.5"/>
      <path d="M3 19 a6 6 0 0 1 12 0"/>
      <circle cx="17" cy="10" r="2.5"/>
      <path d="M14.5 19 a4 4 0 0 1 7.5 0"/>
    </>
  ),
  excel: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="1"/>
      <line x1="3" y1="9" x2="21" y2="9"/>
      <line x1="3" y1="14" x2="21" y2="14"/>
      <line x1="9" y1="4" x2="9" y2="20"/>
      <line x1="15" y1="4" x2="15" y2="20"/>
    </>
  ),
  import: (
    <>
      <path d="M12 3 L12 14"/>
      <polyline points="8,11 12,15 16,11"/>
      <path d="M4 18 H20 V21 H4 Z"/>
    </>
  ),
  rollback: (
    <>
      <polyline points="6,7 3,10 6,13"/>
      <path d="M3 10 H14 a6 6 0 0 1 0 12 H8"/>
    </>
  ),
  test_tube: (
    <>
      <path d="M9 3 H15 V14 a3 3 0 0 1 -6 0 Z"/>
      <line x1="8" y1="3" x2="16" y2="3"/>
      <path d="M9 11 a3 3 0 0 0 6 0"/>
    </>
  ),
  search: (
    <>
      <circle cx="10" cy="10" r="6"/>
      <line x1="14.5" y1="14.5" x2="20" y2="20"/>
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9"/>
      <line x1="12" y1="11" x2="12" y2="16"/>
      <circle cx="12" cy="8" r="0.7" fill="currentColor"/>
    </>
  ),
  receiving: (
    <>
      <path d="M3 11 L12 5 L21 11 L21 20 L3 20 Z"/>
      <path d="M9 13 L12 16 L15 13"/>
      <line x1="12" y1="11" x2="12" y2="16"/>
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3"/>
      <path d="M12 2 v3 M12 19 v3 M2 12 h3 M19 12 h3 M5 5 l2 2 M17 17 l2 2 M5 19 l2 -2 M17 7 l2 -2"/>
    </>
  ),
  // ----- status / actions -----
  check: (
    <>
      <polyline points="4,12 10,18 20,6"/>
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9"/>
      <polyline points="12,7 12,12 16,14"/>
    </>
  ),
  clock_alert: (
    <>
      <circle cx="12" cy="12" r="9"/>
      <polyline points="12,7 12,12 16,14"/>
      <line x1="20" y1="3" x2="20" y2="6"/>
      <circle cx="20" cy="8" r="0.7" fill="currentColor"/>
    </>
  ),
  anchor: (
    <>
      <circle cx="12" cy="5" r="2"/>
      <line x1="12" y1="7" x2="12" y2="20"/>
      <path d="M5 14 a7 7 0 0 0 14 0"/>
      <line x1="9" y1="10" x2="15" y2="10"/>
    </>
  ),
  eye: (
    <>
      <path d="M2 12 Q12 4 22 12 Q12 20 2 12 Z"/>
      <circle cx="12" cy="12" r="2.6"/>
    </>
  ),
  pencil: (
    <>
      <path d="M4 20 L4 16 L16 4 L20 8 L8 20 Z"/>
      <line x1="13" y1="7" x2="17" y2="11"/>
    </>
  ),
  comment: (
    <>
      <path d="M3 5 H21 V17 H13 L8 21 L8 17 H3 Z"/>
      <circle cx="9" cy="11" r="0.7" fill="currentColor"/>
      <circle cx="12" cy="11" r="0.7" fill="currentColor"/>
      <circle cx="15" cy="11" r="0.7" fill="currentColor"/>
    </>
  ),
  factory: (
    <>
      <path d="M3 20 V11 L9 13 V11 L15 13 V11 L21 13 V20 Z"/>
      <line x1="3" y1="20" x2="21" y2="20"/>
      <line x1="6" y1="20" x2="6" y2="16"/>
      <line x1="12" y1="20" x2="12" y2="16"/>
      <line x1="18" y1="20" x2="18" y2="16"/>
      <line x1="6" y1="11" x2="6" y2="4"/>
      <polyline points="3,7 6,4 9,7"/>
    </>
  ),
  clipboard: (
    <>
      <rect x="6" y="4" width="12" height="17" rx="1"/>
      <rect x="9" y="2.5" width="6" height="3" rx="0.6"/>
      <line x1="9" y1="11" x2="15" y2="11"/>
      <line x1="9" y1="14" x2="15" y2="14"/>
      <line x1="9" y1="17" x2="13" y2="17"/>
    </>
  ),
  refresh: (
    <>
      <polyline points="20,6 20,11 15,11"/>
      <path d="M20 11 a8 8 0 1 0 -2 6"/>
    </>
  ),
  lock: (
    <>
      <rect x="5" y="11" width="14" height="10" rx="1"/>
      <path d="M8 11 V8 a4 4 0 0 1 8 0 V11"/>
    </>
  ),
  dot: (
    <>
      <circle cx="12" cy="12" r="3" fill="currentColor"/>
    </>
  ),
  // ----- directional -----
  arrow_left: (
    <>
      <line x1="20" y1="12" x2="4" y2="12"/>
      <polyline points="10,6 4,12 10,18"/>
    </>
  ),
  arrow_right: (
    <>
      <line x1="4" y1="12" x2="20" y2="12"/>
      <polyline points="14,6 20,12 14,18"/>
    </>
  ),
};
/* eslint-enable max-len */

export function Icon({ name, size = 18, weight = 1.75, className, ...rest }: IconProps) {
  const path = PATHS[name];
  if (!path) {
    // Fallback: render a small dotted circle (better than crash) — log so devs catch it.
    if (typeof console !== "undefined") {
      console.warn(`<Icon name="${name as string}"/> not found in PATHS`);
    }
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden
           className={clsx("inline-block align-middle", className)}>
        <circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" strokeDasharray="2 2"/>
      </svg>
    );
  }
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={weight}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={clsx("inline-block align-middle shrink-0", className)}
      {...rest}
    >
      {path}
    </svg>
  );
}
