import { NavLink } from 'react-router-dom';

const items = [
  { to: '/', label: 'Dashboard', emoji: '◉' },
  { to: '/imports', label: 'Imports', emoji: '↥' },
  { to: '/chat', label: 'AI Chat', emoji: '✦' },
  { to: '/reports', label: 'Reports', emoji: '▤' },
];

export function Sidebar() {
  return (
    <aside className="w-56 bg-white border-l border-slate-200 h-full flex flex-col">
      <div className="px-5 py-5 border-b border-slate-200">
        <div className="text-lg font-bold text-ink leading-tight">Sales Intelligence</div>
        <div className="text-xs text-muted">Command Center</div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-accent/10 text-accent font-semibold'
                  : 'text-ink hover:bg-slate-100'
              }`
            }
          >
            <span className="text-lg leading-none">{it.emoji}</span>
            <span>{it.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-xs text-muted border-t border-slate-200">
        v0.1 · MVP
      </div>
    </aside>
  );
}
