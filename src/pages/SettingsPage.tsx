import Header from '../components/layout/Header';
import { Card, Button } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { Shield, Globe, Database, FileText, Key, Server } from 'lucide-react';

const placeholders = [
  { icon: Key, title: 'Government SSO Integration', description: 'Single Sign-On with Aadhaar-based or e-HRMS authentication for seamless login.', status: 'Planned' },
  { icon: Globe, title: 'iGOT Karmayogi API', description: 'Live course catalogue and enrollment through the iGOT Karmayogi platform.', status: 'Planned' },
  { icon: Shield, title: 'DPDP Compliance', description: 'Digital Personal Data Protection Act compliance for handling citizen data.', status: 'Planned' },
  { icon: Database, title: 'Encrypted Data Exchange', description: 'End-to-end encrypted communication with government data servers.', status: 'Planned' },
  { icon: FileText, title: 'Audit Logs', description: 'Comprehensive activity logging for accountability and compliance.', status: 'Planned' },
  { icon: Server, title: 'Role-Based Access Control', description: 'Fine-grained permissions for different government roles and departments.', status: 'Planned' },
];

export default function SettingsPage() {
  const { user } = useApp();

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
      </div>
    </div>
  );
}
