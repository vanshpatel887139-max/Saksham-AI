import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import AssistantWidget from '../AssistantWidget';
import { useApp } from '../../store/AppContext';

export default function Layout() {
  const { sidebarOpen } = useApp();

  return (
    <div className="min-h-screen bg-navy-50">
      <Sidebar />
      <main className={`transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-16'}`}>
        <Outlet />
      </main>
      <AssistantWidget />
    </div>
  );
}