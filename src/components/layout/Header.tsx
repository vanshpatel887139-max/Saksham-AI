import { useApp } from '../../store/AppContext';
import { Bell, Menu } from 'lucide-react';
import { useState } from 'react';

export default function Header({ title }: { title: string }) {
  const { user, notifications, toggleSidebar, toggleLanguage, language } = useApp();
  const [showNotifs, setShowNotifs] = useState(false);
  const unread = notifications.filter(n => !n.read).length;

  return (
    <header className="bg-white border-b border-navy-100 px-6 py-3 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <button onClick={toggleSidebar} className="lg:hidden p-2 rounded-lg hover:bg-navy-50 cursor-pointer">
          <Menu size={20} className="text-navy-600" />
        </button>
        <h1 className="text-lg font-semibold text-navy-800">{language === 'hi' ? `🇮🇳 ${title}` : title}</h1>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-navy-200 text-xs font-medium text-navy-600 hover:bg-navy-50 cursor-pointer"
          title="Toggle language / भाषा बदलें"
        >
          <span>{language === 'en' ? '🌐 English' : '🌐 हिन्दी'}</span>
        </button>
        <div className="relative">
          <button
            onClick={() => setShowNotifs(!showNotifs)}
            className="relative p-2 rounded-lg hover:bg-navy-50 cursor-pointer"
          >
            <Bell size={20} className="text-navy-500" />
            {unread > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold">
                {unread}
              </span>
            )}
          </button>
          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-lg border border-navy-100 py-2 z-50">
              <div className="px-4 py-2 border-b border-navy-100">
                <h3 className="text-sm font-semibold text-navy-800">Notifications</h3>
              </div>
              {notifications.map(n => (
                <div key={n.id} className={`px-4 py-3 border-b border-navy-50 last:border-0 ${!n.read ? 'bg-saffron-50' : ''}`}>
                  <p className="text-xs text-navy-700">{n.message}</p>
                  <p className="text-[10px] text-navy-400 mt-1">{n.date}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {user && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-navy-600 flex items-center justify-center text-xs font-bold text-white">
              {user.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-medium text-navy-800">{user.name}</p>
              <p className="text-xs text-navy-400">{user.department}</p>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
