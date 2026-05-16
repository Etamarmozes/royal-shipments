import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listUsers, listRoles, createUserApi, updateUserApi, resetUserPassword,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, Section } from "../components/common";
import { fmtDateTime } from "../utils/format";
import clsx from "clsx";

const ROLE_LABELS: Record<string, string> = {
  admin: "מנהל",
  import_manager: "מנהל יבוא",
  warehouse: "מחסן",
  viewer: "צופה",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "badge-red",
  import_manager: "badge-blue",
  warehouse: "badge-green",
  viewer: "badge-gray",
};

export default function Users() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const roles = useQuery({ queryKey: ["roles"], queryFn: listRoles });
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [resetting, setResetting] = useState<any | null>(null);

  return (
    <div className="max-w-5xl mx-auto pb-12">
      <PageHeader
        title="משתמשים והרשאות"
        subtitle="ניהול גישה למערכת"
        actions={
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            + משתמש חדש
          </button>
        }
      />

      {users.isLoading ? <Loader /> :
       users.isError ? <ErrorState error={users.error} /> : (
         <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
           <table className="min-w-full text-sm">
             <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500">
               <tr>
                 <th className="text-right py-3 px-4 font-medium">שם משתמש</th>
                 <th className="text-right py-3 px-4 font-medium">שם מלא</th>
                 <th className="text-right py-3 px-4 font-medium">תפקיד</th>
                 <th className="text-right py-3 px-4 font-medium">סטטוס</th>
                 <th className="text-right py-3 px-4 font-medium">כניסה אחרונה</th>
                 <th className="text-right py-3 px-4 font-medium">פעולות</th>
               </tr>
             </thead>
             <tbody className="divide-y divide-slate-100">
               {(users.data || []).map((u) => (
                 <tr key={u.id} className="hover:bg-slate-50">
                   <td className="py-3 px-4 font-mono">{u.username}</td>
                   <td className="py-3 px-4">{u.full_name}</td>
                   <td className="py-3 px-4">
                     <span className={ROLE_COLORS[u.role] || "badge-gray"}>
                       {ROLE_LABELS[u.role] || u.role}
                     </span>
                   </td>
                   <td className="py-3 px-4">
                     {u.is_active ? (
                       <span className="badge-green">פעיל</span>
                     ) : (
                       <span className="badge-gray">מושבת</span>
                     )}
                     {u.must_change_password && (
                       <span className="badge-amber mr-1">חייב להחליף</span>
                     )}
                   </td>
                   <td className="py-3 px-4 text-xs text-slate-500">
                     {u.last_login_at ? fmtDateTime(u.last_login_at) : "—"}
                   </td>
                   <td className="py-3 px-4">
                     <div className="flex gap-1">
                       <button
                         className="btn-secondary text-xs px-2 py-1"
                         onClick={() => setEditing(u)}
                       >ערוך</button>
                       <button
                         className="btn-secondary text-xs px-2 py-1"
                         onClick={() => setResetting(u)}
                       >אפס סיסמה</button>
                     </div>
                   </td>
                 </tr>
               ))}
             </tbody>
           </table>
         </div>
       )}

      {showCreate && (
        <CreateUserModal
          roles={roles.data?.roles || []}
          onClose={() => setShowCreate(false)}
          onCreated={() => { qc.invalidateQueries({ queryKey: ["users"] }); setShowCreate(false); }}
        />
      )}
      {editing && (
        <EditUserModal
          user={editing}
          roles={roles.data?.roles || []}
          onClose={() => setEditing(null)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ["users"] }); setEditing(null); }}
        />
      )}
      {resetting && (
        <ResetPasswordModal
          user={resetting}
          onClose={() => setResetting(null)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ["users"] }); setResetting(null); }}
        />
      )}
    </div>
  );
}

function ModalShell({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg">{title}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function CreateUserModal({ roles, onClose, onCreated }: { roles: any[]; onClose: () => void; onCreated: () => void }) {
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("viewer");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => createUserApi({
      username: username.trim(), full_name: fullName.trim(), password,
      role, phone: phone || undefined, must_change_password: true,
    }),
    onSuccess: onCreated,
    onError: (e: any) => setError(e?.message || "שגיאה"),
  });

  return (
    <ModalShell title="משתמש חדש" onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-3">
        <div>
          <label className="label">שם משתמש</label>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} dir="ltr" autoFocus />
        </div>
        <div>
          <label className="label">שם מלא</label>
          <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div>
          <label className="label">סיסמה ראשונית</label>
          <input className="input" value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" />
          <div className="text-[10px] text-slate-400 mt-1">המשתמש יתבקש להחליף בכניסה הראשונה</div>
        </div>
        <div>
          <label className="label">תפקיד</label>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label">טלפון (אופציונלי)</label>
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} dir="ltr" />
        </div>
        {error && <div className="text-sm text-red-700 bg-red-50 p-2 rounded">{error}</div>}
        <div className="flex gap-2 justify-end">
          <button type="button" className="btn-secondary" onClick={onClose}>ביטול</button>
          <button type="submit" className="btn-primary" disabled={create.isPending}>
            {create.isPending ? "יוצר..." : "צור משתמש"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function EditUserModal({ user, roles, onClose, onSaved }: { user: any; roles: any[]; onClose: () => void; onSaved: () => void }) {
  const [fullName, setFullName] = useState(user.full_name || "");
  const [role, setRole] = useState(user.role);
  const [phone, setPhone] = useState(user.phone || "");
  const [isActive, setIsActive] = useState(user.is_active);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => updateUserApi(user.id, {
      full_name: fullName, role, phone, is_active: isActive,
    }),
    onSuccess: onSaved,
    onError: (e: any) => setError(e?.message || "שגיאה"),
  });

  return (
    <ModalShell title={`עריכת ${user.username}`} onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-3">
        <div>
          <label className="label">שם מלא</label>
          <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div>
          <label className="label">תפקיד</label>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label">טלפון</label>
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} dir="ltr" />
        </div>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          <span className="text-sm">משתמש פעיל</span>
        </label>
        {error && <div className="text-sm text-red-700 bg-red-50 p-2 rounded">{error}</div>}
        <div className="flex gap-2 justify-end">
          <button type="button" className="btn-secondary" onClick={onClose}>ביטול</button>
          <button type="submit" className="btn-primary" disabled={save.isPending}>שמור</button>
        </div>
      </form>
    </ModalShell>
  );
}

function ResetPasswordModal({ user, onClose, onSaved }: { user: any; onClose: () => void; onSaved: () => void }) {
  const [newPwd, setNewPwd] = useState("");
  const [mustChange, setMustChange] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reset = useMutation({
    mutationFn: () => resetUserPassword(user.id, newPwd, mustChange),
    onSuccess: onSaved,
    onError: (e: any) => setError(e?.message || "שגיאה"),
  });

  return (
    <ModalShell title={`איפוס סיסמה — ${user.username}`} onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); reset.mutate(); }} className="space-y-3">
        <div>
          <label className="label">סיסמה חדשה</label>
          <input className="input" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} dir="ltr" autoFocus />
        </div>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={mustChange} onChange={(e) => setMustChange(e.target.checked)} />
          <span className="text-sm">חייב להחליף בכניסה הבאה</span>
        </label>
        {error && <div className="text-sm text-red-700 bg-red-50 p-2 rounded">{error}</div>}
        <div className="flex gap-2 justify-end">
          <button type="button" className="btn-secondary" onClick={onClose}>ביטול</button>
          <button type="submit" className="btn-primary" disabled={reset.isPending}>אפס</button>
        </div>
      </form>
    </ModalShell>
  );
}
