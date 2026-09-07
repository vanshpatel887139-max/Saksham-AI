import { NavLink, useNavigate } from 'react-router-dom';
import { useApp, useI18n } from '../../store/AppContext';
import {
  LayoutDashboard, User, BarChart3, Target, Route, BookOpen, Brain,
  ClipboardList, PieChart, Settings, ChevronLeft, ChevronRight, LogOut, FlaskConical,
} from 'lucide-react';

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar, user, logout, language } = useApp();
  const { t } = useI18n();
  const navigate = useNavigate();

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: t('Dashboard', 'डैशबोर्ड') },
    { to: '/profile', icon: User, label: t('My Profile', 'मेरी प्रोफ़ाइल') },
    { to: '/competency', icon: BarChart3, label: t('Competency Assessment', 'दक्षता मूल्यांकन') },
    { to: '/skill-gaps', icon: Target, label: t('Skill Gaps', 'स्किल गैप') },
    { to: '/learning-path', icon: Route, label: t('Learning Path', 'सीखने का मार्ग') },
    { to: '/courses', icon: BookOpen, label: t('Course Catalogue', 'कोर्स सूची') },
    { to: '/labs', icon: FlaskConical, label: t('Virtual Labs', 'वर्चुअल लैब') },
    { to: '/quiz', icon: Brain, label: t('AI Quiz Generator', 'एआई क्विज़ जनरेटर') },
    { to: '/assessments', icon: ClipboardList, label: t('My Assessments', 'मेरे आकलन') },
  ];

  if (user?.role === 'admin') {
    navItems.push({ to: '/analytics', icon: PieChart, label: t('Analytics', 'एनालिटिक्स') });
  }
  navItems.push({ to: '/settings', icon: Settings, label: t('Settings', 'सेटिंग्स') });

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <aside className={`fixed left-0 top-0 h-full bg-navy-800 text-white transition-all duration-300 z-30 flex flex-col ${sidebarOpen ? 'w-64' : 'w-16'}`}>
      <div className="flex items-center justify-between p-4 border-b border-navy-700">
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-saffron-500 rounded-lg flex items-center justify-center font-bold text-sm">S</div>
            <div>
              <h1 className="text-sm font-bold leading-tight">SakshamAI</h1>
              <p className="text-[10px] text-navy-300 leading-tight">{language === 'hi' ? 'स्किल इंटेलिजेंस' : 'Skill Intelligence'}</p>
            </div>
          </div>
        )}
        <button onClick={toggleSidebar} className="p-1 rounded hover:bg-navy-700 cursor-pointer">
          {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${isActive ? 'bg-saffron-500 text-white' : 'text-navy-200 hover:bg-navy-700 hover:text-white'}`
            }
          >
            <item.icon size={18} />
            {sidebarOpen && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="p-3 border-t border-navy-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-saffron-600 flex items-center justify-center text-xs font-bold">
              {user.name.split(' ').map(n => n[0]).join('')}
            </div>
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{user.name}</p>
                <p className="text-[10px] text-navy-300 truncate">{user.designation}</p>
              </div>
            )}
            {sidebarOpen && (
              <button onClick={handleLogout} className="p-1.5 rounded hover:bg-navy-700 text-navy-300 hover:text-white cursor-pointer" title="Logout">
                <LogOut size={14} />
              </button>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}