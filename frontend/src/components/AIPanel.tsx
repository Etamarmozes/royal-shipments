import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { aiAsk, aiSuggestions } from "../api/endpoints";
import type { AIAnswer, AIContext } from "../types";
import clsx from "clsx";

/**
 * Reusable AI panel — used both in the floating widget and inside Receiving.
 *
 * `context` is forwarded to backend so the AI knows which shipment/container
 * the user is looking at and can answer warehouse questions properly.
 *
 * `compact=true` is for the in-page embed (no header, less padding).
 */
export default function AIPanel({
  context, compact = false, placeholder, autoFirstSuggestion,
}: {
  context?: AIContext;
  compact?: boolean;
  placeholder?: string;
  autoFirstSuggestion?: boolean;
}) {
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<{ q: string; a: AIAnswer }[]>([]);
  const sugg = useQuery({
    queryKey: ["ai-suggestions", context],
    queryFn: () => aiSuggestions(context),
  });
  const ask = useMutation({
    mutationFn: (question: string) => aiAsk(question, context),
    onSuccess: (a, question) => setHistory((h) => [{ q: question, a }, ...h]),
  });

  const submit = (text?: string) => {
    const question = (text ?? q).trim();
    if (!question) return;
    setQ("");
    ask.mutate(question);
  };

  return (
    <div className={clsx(
      "flex flex-col",
      compact ? "rounded-2xl bg-white border border-slate-200" : "h-full",
    )}>
      <div className={clsx("flex-1 overflow-y-auto", compact ? "p-3 max-h-72" : "p-4 space-y-3")}>
        {history.length === 0 && !ask.isPending && (
          <div className="space-y-2">
            <div className="text-xs text-slate-500">שאלות מהירות:</div>
            <div className="flex flex-wrap gap-1.5">
              {(sugg.data?.questions || []).map((sq) => (
                <button
                  key={sq}
                  className="text-xs px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700"
                  onClick={() => submit(sq)}
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        )}

        {ask.isPending && <div className="text-sm text-slate-500 mt-2">חושב…</div>}

        {history.map((row, i) => (
          <div key={i} className="space-y-2 mt-3">
            <div className="rounded-2xl rounded-bl-sm bg-slate-100 px-3 py-2 text-sm text-slate-800 max-w-[90%] mr-auto">
              {row.q}
            </div>
            <div className={clsx(
              "rounded-2xl rounded-br-sm px-3 py-2 text-sm max-w-[95%] ml-auto whitespace-pre-line",
              row.a.confidence === "low"
                ? "bg-amber-50 text-amber-900 border border-amber-200"
                : row.a.intent.startsWith("warehouse_")
                ? "bg-emerald-50 text-emerald-900 border border-emerald-200"
                : "bg-indigo-50 text-indigo-900 border border-indigo-200",
            )}>
              <div>{row.a.answer}</div>
              {row.a.actions && row.a.actions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {row.a.actions.map((act, ai) => (
                    <Link
                      key={ai}
                      to={act.link}
                      className="text-xs px-2 py-0.5 rounded-full bg-white border border-emerald-300 text-emerald-700 hover:bg-emerald-100"
                    >
                      {act.label} →
                    </Link>
                  ))}
                </div>
              )}
              {row.a.sources && row.a.sources.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <span className="text-[10px] text-slate-500 ml-1">מקורות:</span>
                  {row.a.sources.slice(0, 8).map((src, si) => (
                    src.link ? (
                      <Link
                        key={si}
                        to={src.link}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                      >
                        {src.kind === "container" ? "📦" :
                         src.kind === "shipment" ? "🚢" :
                         src.kind === "document" ? "📄" :
                         src.kind === "alert" ? "⚠" : "•"}{" "}
                        {src.label}
                      </Link>
                    ) : (
                      <span key={si} className="text-[10px] text-slate-500">{src.label}</span>
                    )
                  ))}
                </div>
              )}
              <div className="mt-1.5 text-[9px] text-slate-500">
                {row.a.intent} · ביטחון: {row.a.confidence}
              </div>
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        className={clsx(
          "flex items-center gap-2 border-t border-slate-100",
          compact ? "p-2" : "p-3",
        )}
      >
        <input
          className="input flex-1"
          placeholder={placeholder || "שאל שאלה…"}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          disabled={ask.isPending}
        />
        <button type="submit" className="btn-primary px-4" disabled={ask.isPending || !q.trim()}>
          שלח
        </button>
      </form>
    </div>
  );
}
