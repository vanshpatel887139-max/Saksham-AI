import Header from '../components/layout/Header';
import { Card, Button } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { Shield, Globe, Database, FileText, Key, Server, Trash2, AlertTriangle } from 'lucide-react';
import { useState } from 'react';
import { apiDeleteMyAccount, type EraseReceipt } from '../services/api';

export default function SettingsPage() {
  const { user, logout } = useApp();
  const { t } = useI18n();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<EraseReceipt | null>(null);

  const placeholders = [
    { icon: Key, title: t('Government SSO Integration', 'सरकारी SSO एकीकरण'), description: t('Single Sign-On with Aadhaar-based or e-HRMS authentication for seamless login.', 'सहज लॉगिन हेतु आधार-आधारित अथवा e-HRMS प्रमाणीकरण के साथ सिंगल साइन-ऑन।'), status: t('Planned', 'नियोजित') },
    { icon: Globe, title: t('iGOT Karmayogi API', 'iGOT Karmayogi API'), description: t('Live course catalogue and enrollment through the iGOT Karmayogi platform.', 'iGOT Karmayogi मंच के माध्यम से लाइव कोर्स सूची और पंजीकरण।'), status: t('Planned', 'नियोजित') },
    { icon: Shield, title: t('DPDP Compliance', 'DPDP अनुपालन'), description: t('Digital Personal Data Protection Act compliance for handling citizen data.', 'नागरिक डेटा के प्रबंधन हेतु डिजिटल व्यक्तिगत डेटा संरक्षण अधिनियम का अनुपालन।'), status: t('Planned', 'नियोजित') },
    { icon: Database, title: t('Encrypted Data Exchange', 'एन्क्रिप्टेड डेटा आदान-प्रदान'), description: t('End-to-end encrypted communication with government data servers.', 'सरकारी डेटा सर्वरों के साथ एंड-टू-एंड एन्क्रिप्टेड संचार।'), status: t('Planned', 'नियोजित') },
    { icon: FileText, title: t('Audit Logs', 'ऑडिट लॉग'), description: t('Comprehensive activity logging for accountability and compliance.', 'जवाबदेहिता और अनुपालन हेतु व्यापक गतिविधि लॉगिंग।'), status: t('Planned', 'नियोजित') },
    { icon: Server, title: t('Role-Based Access Control', 'भूमिका-आधारित पहुँच नियंत्रण'), description: t('Fine-grained permissions for different government roles and departments.', 'विभिन्न सरकारी भूमिकाओं और विभागों हेतु सूक्ष्म-स्तरीय अनुमतियाँ।'), status: t('Planned', 'नियोजित') },
  ];

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
          ? t('Your session expired. Sign in again to delete your account.', 'आपका सत्र समाप्त हो गया है। अपना खाता हटाने हेतु पुनः साइन इन करें।')
          : t('Could not reach the server, so nothing was deleted. Your data is untouched — try again when the server is running.', 'सर्वर से संपर्क नहीं हो सका, अतः कुछ भी हटाया नहीं गया। आपका डेटा सुरक्षित है — सर्वर चल रहा हो तब पुनः प्रयास करें।')
      );
      setBusy(false);
    }
  };

  return (
    <div>
      <Header title={t('Settings', 'सेटिंग्स')} />
      <div className="p-6 space-y-6">
        <Card>
          <h2 className="text-base font-semibold text-navy-800 mb-4">{t('Account Settings', 'खाता सेटिंग्स')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('User ID', 'उपयोगकर्ता ID')}</p>
              <p className="text-sm font-medium text-navy-800">{user?.id}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('Role', 'भूमिका')}</p>
              <p className="text-sm font-medium text-navy-800 capitalize">{user?.role}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('Language Preference', 'भाषा वरीयता')}</p>
              <p className="text-sm font-medium text-navy-800">{user?.preferredLanguage}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('Authentication', 'प्रमाणीकरण')}</p>
              <p className="text-sm font-medium text-navy-800">{t('Demo Mode (Simulated)', 'डेमो मोड (अनुकरणित)')}</p>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="text-base font-semibold text-navy-800 mb-2">{t('Future Integration Placeholders', 'भविष्य के एकीकरण हेतु स्थान')}</h2>
          <p className="text-xs text-navy-400 mb-4">{t('These features are planned for production deployment', 'इन सुविधाओं का उत्पादन परिनियोजन हेतु नियोजन किया गया है')}</p>
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
          <h2 className="text-base font-semibold text-navy-800 mb-2">{t('Multilingual Support', 'बहुभाषी समर्थन')}</h2>
          <p className="text-xs text-navy-400 mb-4">{t('Planned languages for the platform', 'मंच हेतु नियोजित भाषाएँ')}</p>
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
              <h2 className="text-base font-semibold text-navy-800">{t('Demo Prototype', 'डेमो प्रोटोटाइप')}</h2>
              <p className="text-xs text-navy-400">{t('SakshamAI v0.1 — SIH 2025 Demonstration', 'SakshamAI v0.1 — SIH 2025 प्रदर्शन')}</p>
            </div>
            <Button variant="danger" size="sm">{t('Reset All Data', 'सारा डेटा रीसेट करें')}</Button>
          </div>
        </Card>

        <Card className="border-red-200">
          <div className="flex items-start gap-3">
            <Trash2 size={18} className="text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <h2 className="text-base font-semibold text-navy-800">{t('Delete my data', 'मेरा डेटा हटाएँ')}</h2>
              <p className="text-xs text-navy-400 mt-1 max-w-2xl">
                {t('Permanently erases your account and everything held about you: your profile, competency levels, assessment answers, quiz attempts, course progress, notifications and advisor chat history. This cannot be undone and no anonymised copy is kept.', 'आपका खाता और आपके बारे में संग्रहीत सभी जानकारी स्थायी रूप से मिटा देता है: आपकी प्रोफ़ाइल, दक्षता स्तर, आकलन उत्तर, क्विज़ प्रयास, कोर्स प्रगति, सूचनाएँ और सलाहकार चैट इतिहास। इसे पूर्ववत नहीं किया जा सकता और कोई अनामित प्रति भी नहीं रखी जाती।')}
              </p>

              {receipt ? (
                <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                  <p className="text-xs font-semibold text-emerald-800">
                    {receipt.totalRowsRemoved} {t('records deleted.', 'रिकॉर्ड हटा दिए गए।')}
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
                      {t('Your records are gone, but the sign-in account could not be removed automatically', 'आपके रिकॉर्ड मिट गए हैं, परंतु साइन-इन खाता स्वतः नहीं हटाया जा सका')} ({receipt.authAccountDetail}). {t('An administrator needs to finish this in the Supabase dashboard.', 'इसे पूरा करने हेतु किसी प्रशासक को Supabase डैशबोर्ड में कार्रवाई करनी होगी।')}
                    </p>
                  )}
                </div>
              ) : confirming ? (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-xs font-semibold text-red-800 flex items-center gap-1.5">
                    <AlertTriangle size={14} />
                    {t('This cannot be undone', 'इसे पूर्ववत नहीं किया जा सकता')}
                  </p>
                  <p className="text-xs text-red-700 mt-1.5">
                    {t('You will be signed out. Any account not linked to Supabase Auth, including the only remaining administrator, cannot be deleted this way.', 'आपको साइन आउट कर दिया जाएगा। Supabase Auth से न जुड़ा कोई भी खाता, जिसमें केवल शेष प्रशासक भी शामिल है, इस प्रकार से हटाया नहीं जा सकता।')}
                  </p>
                  <div className="flex gap-2 mt-3">
                    <Button variant="danger" size="sm" disabled={busy} onClick={runErase}>
                      {busy ? t('Deleting…', 'हटाया जा रहा है…') : t('Yes, delete everything', 'हाँ, सब कुछ हटाएँ')}
                    </Button>
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
                      {t('Cancel', 'रद्द करें')}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="danger" size="sm" className="mt-4" onClick={() => setConfirming(true)}>
                  {t('Delete my data', 'मेरा डेटा हटाएँ')}
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
