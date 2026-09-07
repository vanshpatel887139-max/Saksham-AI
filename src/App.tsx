import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './store/AppContext';
import Layout from './components/layout/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import CompetencyPage from './pages/CompetencyPage';
import SkillGapsPage from './pages/SkillGapsPage';
import LearningPathPage from './pages/LearningPathPage';
import CourseCataloguePage from './pages/CourseCataloguePage';
import CourseDetailPage from './pages/CourseDetailPage';
import VirtualLabsPage from './pages/VirtualLabsPage';
import QuizGeneratorPage from './pages/QuizGeneratorPage';
import AssessmentsPage from './pages/AssessmentsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useApp();
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useApp();
  if (!isAuthenticated) return <Navigate to="/" replace />;
  if (user?.role !== 'admin') return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { isAuthenticated } = useApp();

  return (
    <Routes>
      {/* Login */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />}
      />
      {/* Root: redirect based on auth state */}
      <Route
        path="/"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />}
      />

      {/* Protected app routes with shared layout */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/competency" element={<CompetencyPage />} />
        <Route path="/skill-gaps" element={<SkillGapsPage />} />
        <Route path="/learning-path" element={<LearningPathPage />} />
        <Route path="/courses" element={<CourseCataloguePage />} />
        <Route path="/courses/:id" element={<CourseDetailPage />} />
        <Route path="/labs" element={<VirtualLabsPage />} />
        <Route path="/quiz" element={<QuizGeneratorPage />} />
        <Route path="/assessments" element={<AssessmentsPage />} />
        <Route path="/analytics" element={<AdminRoute><AnalyticsPage /></AdminRoute>} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProvider>
  );
}
