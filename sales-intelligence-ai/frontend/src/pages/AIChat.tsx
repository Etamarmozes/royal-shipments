import { useState } from 'react';
import { api } from '../services/api';

type Msg = { role: 'user' | 'assistant'; text: string; tool_calls?: any[]; mode?: string };

const SUGGESTIONS = [
  'תראה לי קדס מול אדידס החודש לפי סניפים',
  'איזה פריטים בסיכון מלאי?',
  'תכין לי סיכום למנכ״ל',
  'Compare Keds vs Adidas this month',
  'What should I reorder?',
];

export function AIChat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const send = async (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setInput('');
    setLoading(true);
    try {
      const r = await api.chat(q);
      setMessages((m) => [...m, {
        role: 'assistant', text: r.answer, tool_calls: r.tool_calls, mode: r.mode,
      }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-9rem)]">
      <h1 className="text-xl font-bold text-ink mb-4">AI Chat</h1>

      {messages.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 mb-4">
          <div className="text-sm text-muted mb-3">Try one of these:</div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)}
                      className="text-sm bg-slate-100 hover:bg-slate-200 text-ink px-3 py-1.5 rounded-md">
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto space-y-3 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`max-w-3xl ${m.role === 'user' ? 'ms-auto' : ''}`}>
            <div className={`rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
              m.role === 'user'
                ? 'bg-accent text-white'
                : 'bg-white border border-slate-200 text-ink'
            }`}>
              {m.text}
            </div>
            {m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0 && (
              <details className="mt-1 text-xs text-muted">
                <summary className="cursor-pointer">
                  {m.tool_calls.length} tool call{m.tool_calls.length === 1 ? '' : 's'} · {m.mode}
                </summary>
                <ul className="ms-4 mt-1 space-y-1">
                  {m.tool_calls.map((t, j) => (
                    <li key={j}>
                      <code>{t.tool}</code> · {JSON.stringify(t.args)}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
        {loading && (
          <div className="text-sm text-muted">Thinking…</div>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask in Hebrew or English…"
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-accent text-white px-4 py-2 rounded-md text-sm disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
