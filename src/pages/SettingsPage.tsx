import Header from '../components/layout/Header';
import { Card, Button } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { Shield, Globe, Database, FileText, Key, Server, Trash2, AlertTriangle } from 'lucide-react';
import { useState } from 'react';
import { apiDeleteMyAccount, type EraseReceipt } from '../services/api';

const placeholders = [
  { icon: Key, title: 'Government SSO Integration', description: 'Single Sign-On with Aadhaar-based or e-HRMS authentication for seamless login.', status: 'Planned' },
  { icon: Globe, title: 'iGOT Karmayogi API', description: 'Live course catalogue and enrollment through the iGOT Karmayogi platform.', status: 'Planned' },
  { icon: Shield, title: 'DPDP Compliance', description: 'Digital Personal Data Protection Act compliance for handling citizen data.', status: 'Planned' },
  { icon: Database, title: 'Encrypted Data Exchange', description: 'End-to-end encrypted communication with government data servers.', status: 'Planned' },
  { icon: FileText, title: 'Audit Logs', description: 'Comprehensive activity logging for accountability and compliance.', status: 'Planned' },
  { icon: Server, title: 'Role-Based Access Control', description: 'Fine-grained permissions for different government roles and departments.', status: 'Planned' },
];

export default function SettingsPage() {
  const { user, logout } = useApp();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<EraseReceipt | null>(null);

  const runErase = async () => {
    setBusy(true);
    setError('');
    try {
      const r = await apiDeleteMyAccount();
      setReceipt(r);
      // The backend has already dropped the row and invalidated the session
      // cache, so the local session is meaningless now. Clear it either way:
      // a partially-completed erase must not leave a usable-looking screen.
      logout();
    } catch (e: any) {
      setError(
        e?.isAuthError
          ? 'Your session expired. Sign in again to delete your account.'
          : 'Could not reach the server, so nothing was deleted. Your data is untouched — try again when the server is running.'
      );
      setBusy(false);
    }
  };

  return (
    <div>
      <Header title="Settings" />
      <div className="p-6 space-y-6">
        <Card>
          <h2 className="text-base font-semibold text-navy-800 mb-4">Account Settings</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">User ID</p>
              <p className="text-sm font-medium text-navy-800">{user?.id}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">Role</p>
              <p className="text-sm font-medium text-navy-800 capitalize">{user?.role}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">Language Preference</p>
              <p className="text-sm font-medium text-navy-800">{user?.preferredLanguage}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">Authentication</p>
              <p className="text-sm font-medium text-navy-800">Demo Mode (Simulated)</p>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="text-base font-semibold text-navy-800 mb-2">Future Integration Placeholders</h2>
          <p className="text-xs text-navy-400 mb-4">These features are planned for production deployment</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {placeholders.map(p => (
              <div key={p.title} className="p-4 border border-dashed border-navy-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <p.icon size={18} className="text-navy-400" />
                  <h3 className="text-sm font-medium text-navy-700">{p.title}</h3>
                </div>
                <p className="text-xs text-navy-400 mb-2">{p.description}</p>
                <span className="px-2 py-0.5 bg-navy-100 text-navy-500 text-[10px] rounded font-medium">{p.status}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-base font-semibold text-navy-800 mb-2">Multilingual Support</h2>
          <p className="text-xs text-navy-400 mb-4">Planned languages for the platform</p>
          <div className="flex flex-wrap gap-2">
            {['English'].map(lang => (
              <span key={lang} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${lang === user?.preferredLanguage ? 'bg-saffron-100 text-saffron-700 border border-saffron-200' : 'bg-navy-50 text-navy-500 border border-navy-100'}`}>
                {lang} {lang === user?.preferredLanguage && '✓'}
              </span>
            ))}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-navy-800">Demo Prototype</h2>
              <p className="text-xs text-navy-400">SakshamAI v0.1 — SIH 2025 Demonstration</p>
            </div>
            <Button variant="danger" size="sm">Reset All Data</Button>
          </div>
        </Card>

        <Card className="border-red-200">
          <div className="flex items-start gap-3">
            <Trash2 size={18} className="text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <h2 className="text-base font-semibold text-navy-800">Delete my data</h2>
              <p className="text-xs text-navy-400 mt-1 max-w-2xl">
                Permanently erases your account and everything held about you: your
                profile, competency levels, assessment answers, quiz attempts, course
                progress, notifications and advisor chat history. This cannot be undone
                and no anonymised copy is kept.
              </p>

              {receipt ? (
                <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                  <p className="text-xs font-semibold text-emerald-800">
                    {receipt.totalRowsRemoved} records deleted.
                  </p>
                  <ul className="mt-2 text-xs text-emerald-700 space-y-0.5">
                    {Object.entries(receipt.rowsRemoved)
                      .filter(([, n]) => n > 0)
                      .map(([table, n]) => (
                        <li key={table}>{table.replace(/_/g, ' ')}: {n}</li>
                      ))}
                  </ul>
                  {!receipt.authAccountRemoved && (
                    <p className="mt-2 text-xs text-amber-700">
                      Your records are gone, but the sign-in account could not be removed
                      automatically ({receipt.authAccountDetail}). An administrator needs
                      to finish this in the Supabase dashboard.
                    </p>
                  )}
                </div>
              ) : confirming ? (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-xs font-semibold text-red-800 flex items-center gap-1.5">
                    <AlertTriangle size={14} />
                    This cannot be undone
                  </p>
                  <p className="text-xs text-red-700 mt-1.5">
                    You will be signed out. Any account not linked to Supabase Auth,
                    including the only remaining administrator, cannot be deleted this way.
                  </p>
                  <div className="flex gap-2 mt-3">
                    <Button variant="danger" size="sm" disabled={busy} onClick={runErase}>
                      {busy ? 'Deleting…' : 'Yes, delete everything'}
                    </Button>
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="danger" size="sm" className="mt-4" onClick={() => setConfirming(true)}>
                  Delete my data
                </Button>
              )}

              {error && <p className="text-xs text-red-600 mt-3">{error}</p>}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
