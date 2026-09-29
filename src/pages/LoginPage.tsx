import { useApp, useI18n } from '../store/AppContext';
import { useNavigate } from 'react-router-dom';
import { Shield, BarChart3, Lock, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import Logo from '../components/Logo';
import { apiGetDemoUsers, DemoAccount } from '../services/api';

const DEMO_EMAIL = 'learner-1@sakshamai.demo';

export default function LoginPage() {
  const { login } = useApp();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const [demoPassword, setDemoPassword] = useState<string | null>(null);
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState('');

  useEffect(() => {
    apiGetDemoUsers().then(({ users, demoPassword: pw }) => {
      setAccounts(users);
      setDemoPassword(pw);
      if (users.length) setEmail(users[0].email);
    }).catch(() => { /* offline: fall back to manual entry */ });
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!email || !password) {
      setError(t('Enter your email and password.', 'अपना ईमेल और पासवर्ड दर्ज करें।'));
      return;
    }
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      // Never fall back to a mock user here — a failed sign-in must not look
      // like a successful one.
      setError(err instanceof Error ? err.message : t('Sign-in failed', 'साइन-इन विफल रहा'));
      setLoading(false);
    }
  };

  const pick = (a: DemoAccount) => {
    setEmail(a.email);
    if (demoPassword) setPassword(demoPassword);
    setError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-800 via-navy-900 to-navy-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          {/* The only placement that asks for the full lockup. mb-4 is block
              rhythm to the h1 below, not alignment -- the mark is centred by
              justify-center, and there is no sibling text to align to. */}
          <div className="flex justify-center mb-4">
            <Logo variant="full" height={72} />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">SakshamAI</h1>
          <p className="text-navy-300 text-sm">{t('Skill Intelligence Platform for Official Statistics', 'आधिकारिक सांख्यिकी हेतु कौशल बुद्धिमत्ता मंच')}</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-navy-800 text-center mb-6">{t('Sign In to Your Account', 'अपने खाते में साइन इन करें')}</h2>

          {accounts.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-2 text-xs font-medium text-navy-500 uppercase tracking-wide mb-3">
                <Users size={14} />
                <span>{t('Demo accounts', 'डेमो खाते')}</span>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {accounts.map(a => {
                  const active = email === a.email;
                  const Icon = a.role === 'admin' ? Shield : BarChart3;
                  return (
                    <button
                      key={a.userId}
                      type="button"
                      onClick={() => pick(a)}
                      disabled={loading}
                      className={`w-full flex items-center gap-3 p-3 border-2 rounded-xl text-left transition-all duration-200 disabled:opacity-50 disabled:cursor-wait ${
                        active
                          ? 'border-saffron-400 bg-saffron-50'
                          : 'border-navy-100 hover:border-saffron-400 hover:bg-saffron-50'
                      }`}
                    >
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${active ? 'bg-saffron-500' : 'bg-navy-100'}`}>
                        <Icon className={active ? 'text-white' : 'text-navy-600'} size={18} />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-navy-800 text-sm truncate">{a.name}</p>
                        <p className="text-xs text-navy-400 truncate">{a.designation || a.department}</p>
                      </div>
                      {a.role === 'admin' && (
                        <span className="ml-auto text-[10px] font-semibold px-2 py-0.5 bg-navy-100 text-navy-600 rounded shrink-0">
                          {t('ADMIN', 'व्यवस्थापक')}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
              {demoPassword && (
                <p className="mt-3 text-xs text-navy-400">
                  {t('Demo password:', 'डेमो पासवर्ड:')} <code className="font-mono text-navy-600">{demoPassword}</code>
                </p>
              )}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-navy-700 mb-1.5">
                {t('Email', 'ईमेल')}
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 border-2 border-navy-100 rounded-xl focus:border-saffron-400 focus:outline-none transition-colors text-navy-800"
                placeholder="you@sakshamai.demo"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-navy-700 mb-1.5">
                {t('Password', 'पासवर्ड')}
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 border-2 border-navy-100 rounded-xl focus:border-saffron-400 focus:outline-none transition-colors text-navy-800"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 p-3.5 bg-saffron-500 hover:bg-saffron-600 rounded-xl text-white font-semibold transition-colors duration-200 disabled:opacity-50 disabled:cursor-wait"
            >
              {loading
                ? <span className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                : <Lock size={18} />}
              {loading ? t('Signing in…', 'साइन इन किया जा रहा है…') : t('Sign In', 'साइन इन')}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-navy-100">
            <div className="flex items-center gap-2 justify-center text-xs text-navy-400">
              <Lock size={12} />
              <span>{t('Credentials verified by Supabase Auth when a server is connected', 'सर्वर जुड़ा होने पर क्रेडेंशियल की जाँच Supabase Auth द्वारा की जाती है')}</span>
            </div>
          </div>
        </div>

        <div className="mt-6 space-y-2">
          <div className="flex items-center justify-center gap-2 text-xs text-navy-400">
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">{t('MOCK iGOT API', 'मॉक iGOT एपीआई')}</span>
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">{t('DEMO DATA', 'डेमो डेटा')}</span>
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">{t('SIH PROTOTYPE', 'एसआईएच प्रोटोटाइप')}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
