import { useApp } from '../store/AppContext';
import { useNavigate } from 'react-router-dom';
import { Shield, BarChart3, Lock } from 'lucide-react';
import { useState } from 'react';

export default function LoginPage() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleLogin = async (role: 'learner' | 'admin') => {
    setLoading(true);
    await login(role);
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-800 via-navy-900 to-navy-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-saffron-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl font-bold text-white">S</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">SakshamAI</h1>
          <p className="text-navy-300 text-sm">Skill Intelligence Platform for Official Statistics</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-navy-800 text-center mb-6">Sign In to Your Account</h2>

          <div className="space-y-4">
            <button
              onClick={() => handleLogin('learner')}
              disabled={loading}
              className="w-full flex items-center gap-4 p-4 border-2 border-navy-100 rounded-xl hover:border-saffron-400 hover:bg-saffron-50 transition-all duration-200 group cursor-pointer disabled:opacity-50 disabled:cursor-wait"
            >
              <div className="w-12 h-12 bg-navy-100 group-hover:bg-saffron-500 rounded-xl flex items-center justify-center transition-colors">
                {loading
                  ? <span className="w-5 h-5 border-2 border-saffron-400 border-t-white rounded-full animate-spin" />
                  : <BarChart3 className="text-navy-600 group-hover:text-white" size={24} />}
              </div>
              <div className="text-left">
                <p className="font-semibold text-navy-800">{loading ? 'Signing in…' : 'Login as Learner'}</p>
                <p className="text-xs text-navy-400">Access courses, assessments & learning paths</p>
              </div>
            </button>

            <button
              onClick={() => handleLogin('admin')}
              disabled={loading}
              className="w-full flex items-center gap-4 p-4 border-2 border-navy-100 rounded-xl hover:border-navy-600 hover:bg-navy-50 transition-all duration-200 group cursor-pointer disabled:opacity-50 disabled:cursor-wait"
            >
              <div className="w-12 h-12 bg-navy-100 group-hover:bg-navy-600 rounded-xl flex items-center justify-center transition-colors">
                {loading
                  ? <span className="w-5 h-5 border-2 border-navy-400 border-t-white rounded-full animate-spin" />
                  : <Shield className="text-navy-600 group-hover:text-white" size={24} />}
              </div>
              <div className="text-left">
                <p className="font-semibold text-navy-800">{loading ? 'Signing in…' : 'Login as Administrator'}</p>
                <p className="text-xs text-navy-400">View org analytics, manage learners & courses</p>
              </div>
            </button>
          </div>

          <div className="mt-6 pt-4 border-t border-navy-100">
            <div className="flex items-center gap-2 justify-center text-xs text-navy-400">
              <Lock size={12} />
              <span>Demo Mode – Authentication Simulated</span>
            </div>
          </div>
        </div>

        <div className="mt-6 space-y-2">
          <div className="flex items-center justify-center gap-2 text-xs text-navy-400">
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">MOCK iGOT API</span>
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">DEMO DATA</span>
            <span className="px-2 py-0.5 bg-navy-700 rounded text-navy-200 text-[10px]">SIH PROTOTYPE</span>
          </div>
        </div>
      </div>
    </div>
  );
}
