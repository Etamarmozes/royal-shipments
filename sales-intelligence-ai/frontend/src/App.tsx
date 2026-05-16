import { Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { DataFreshness } from './components/DataFreshness';
import { Dashboard } from './pages/Dashboard';
import { Imports } from './pages/Imports';
import { AIChat } from './pages/AIChat';
import { Reports } from './pages/Reports';

export default function App() {
  return (
    <div className="flex h-full" dir="rtl">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <header className="h-14 border-b border-slate-200 bg-white px-6 flex items-center justify-between">
          <div className="text-sm text-muted">Royal Linen — Sales Intelligence</div>
          <DataFreshness />
        </header>
        <div className="p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/imports" element={<Imports />} />
            <Route path="/chat" element={<AIChat />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
