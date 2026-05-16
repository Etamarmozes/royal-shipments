import { useState, useMemo } from "react";
import { useLocation, useParams } from "react-router-dom";
import clsx from "clsx";
import AIPanel from "./AIPanel";
import type { AIContext } from "../types";

/**
 * Floating AI Assistant — bottom-left chat widget.
 *
 * Context-aware: reads the current route to figure out whether the user is
 * on a shipment, container, or receiving page, and forwards that as
 * `context` so the AI focuses on the right entity.
 */
export default function AIAssistant() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // Resolve context from URL
  const context: AIContext = useMemo(() => {
    const path = location.pathname;
    const ctx: AIContext = {};
    let m: RegExpMatchArray | null;
    if ((m = path.match(/^\/shipments\/(\d+)/))) {
      ctx.shipment_id = Number(m[1]);
      ctx.page = "shipment_profile";
    } else if ((m = path.match(/^\/containers\/(\d+)/))) {
      ctx.container_id = Number(m[1]);
      ctx.page = "container_profile";
    } else if (path.startsWith("/receiving")) {
      const params = new URLSearchParams(location.search);
      const cid = params.get("container");
      if (cid) ctx.container_id = Number(cid);
      ctx.page = "receiving";
    }
    return ctx;
  }, [location.pathname, location.search]);

  const inWarehouse = !!(context.container_id || context.page === "receiving");

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className={clsx(
          "fixed left-4 z-40 rounded-full shadow-lg w-14 h-14 flex items-center justify-center text-white",
          "hover:scale-105 transition",
          /* Lift above bottom-nav on mobile (bottom-nav ≈ 4.5rem) */
          "bottom-[5.5rem] lg:bottom-5",
          inWarehouse
            ? "bg-gradient-to-br from-emerald-500 to-teal-600"
            : "bg-gradient-to-br from-indigo-500 to-violet-600",
          open && "scale-95"
        )}
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}
        title={inWarehouse ? "עוזר מחסן" : "עוזר חכם"}
        aria-label={inWarehouse ? "עוזר מחסן" : "עוזר חכם"}
      >
        <span className="text-2xl">{inWarehouse ? "🧰" : "🤖"}</span>
      </button>

      {open && (
        <div className="fixed bottom-[10rem] lg:bottom-24 left-4 z-50 w-[min(440px,calc(100vw-2rem))] max-h-[70vh] flex flex-col rounded-2xl bg-white border border-slate-200 shadow-2xl">
          <header className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <div>
              <div className="font-semibold text-slate-900">
                {inWarehouse ? "עוזר מחסן" : "עוזר משלוחים"}
              </div>
              <div className="text-xs text-slate-500">
                {inWarehouse
                  ? "עונה על שאלות מחסן מתוך נתוני המכולה והמשלוח"
                  : "עונה רק מתוך נתוני המערכת"}
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-700">
              ✕
            </button>
          </header>
          <AIPanel context={context} placeholder={inWarehouse ? "שאל על המכולה הזאת…" : "שאל שאלה…"} />
        </div>
      )}
    </>
  );
}
