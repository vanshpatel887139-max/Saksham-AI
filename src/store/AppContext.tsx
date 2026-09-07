import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { UserProfile, SkillGap, Course, Quiz, Notification, Activity, CompetencyScore, QuizQuestion, Lab, ChatMessage, ForecastData, ModuleCompleteResult } from '../types';
import { mockNotifications, mockActivities, mockLabs } from '../services/appService';
import { courses as allCoursesData } from '../data/mockData';
import {
  apiLogin, apiUpdateProfile, apiUpdateCompetencies, apiAnalyzeGaps, apiEnrollCourse,
  apiSubmitQuiz, apiGetLabs, apiChatAssistant, apiCompleteModule, apiAdminForecast,
  apiGetCourses, isBackendAvailable,
} from '../services/api';
import { determineEnrollment } from '../services/appService';

type Language = 'en' | 'hi';

interface AppState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  skillGaps: SkillGap[];
  recommendedCourses: Course[];
  enrolledCourses: Course[];
  quizzes: Quiz[];
  notifications: Notification[];
  activities: Activity[];
  selectedRole: string;
  sidebarOpen: boolean;
  backendOnline: boolean;
  labs: Lab[];
  chatMessages: ChatMessage[];
  forecast: ForecastData | null;
  language: Language;
}

interface AppContextType extends AppState {
  login: (role: 'learner' | 'admin') => Promise<void>;
  logout: () => void;
  updateUserProfile: (updates: Partial<UserProfile>) => Promise<void>;
  updateCompetencies: (scores: CompetencyScore[]) => Promise<void>;
  setSelectedRole: (role: string) => void;
  calculateGaps: (role?: string) => Promise<void>;
  enrollInCourse: (courseId: string) => Promise<void>;
  saveQuiz: (title: string, questions: QuizQuestion[], answers: (number | null)[]) => Promise<Quiz>;
  toggleSidebar: () => void;
  markNotificationRead: (id: string) => void;
  refreshData: () => Promise<void>;
  sendAssistantMessage: (message: string) => Promise<void>;
  completeModule: (courseId: string, moduleTitle: string, assessmentScore: number) => Promise<ModuleCompleteResult>;
  loadForecast: () => Promise<void>;
  toggleLanguage: () => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [skillGaps, setSkillGaps] = useState<SkillGap[]>([]);
  const [selectedRole, setSelectedRole] = useState('Data Analyst');
  const [enrolledCourses, setEnrolledCourses] = useState<Course[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [notifications] = useState<Notification[]>(mockNotifications);
  const [activities] = useState<Activity[]>(mockActivities);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [backendOnline, setBackendOnline] = useState(isBackendAvailable());
  const [labs, setLabs] = useState<Lab[]>(mockLabs);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [language, setLanguage] = useState<Language>('en');

  const login = useCallback(async (role: 'learner' | 'admin') => {
    const result = await apiLogin(role);
    setUser(result.user);
    setIsAuthenticated(true);
    setBackendOnline(isBackendAvailable());
    try {
      const labsData = await apiGetLabs();
      setLabs(labsData);
    } catch { /* offline: keep mock labs */ }
    if (role === 'learner') {
      const analysis = await apiAnalyzeGaps(result.user.currentRole || 'Data Analyst', result.user.competencies);
      setSkillGaps(analysis.gaps);
      const enrolled = await apiGetCourses(result.user.id).catch(() => analysis.recommendedCourses.slice(0, 2));
      if (enrolled && enrolled.length > 0) {
        setEnrolledCourses(enrolled.filter(c => c.enrolled).length > 0
          ? enrolled.filter(c => c.enrolled)
          : analysis.recommendedCourses.slice(0, 2).map(c => ({ ...c, enrolled: true, progress: 10 })));
      } else {
        setEnrolledCourses(analysis.recommendedCourses.slice(0, 2).map(c => ({
          ...c, enrolled: true, progress: Math.floor(Math.random() * 60) + 10,
        })));
      }
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setSkillGaps([]);
    setEnrolledCourses([]);
    setQuizzes([]);
    setChatMessages([]);
    setForecast(null);
  }, []);

  const updateUserProfile = useCallback(async (updates: Partial<UserProfile>) => {
    setUser(prev => prev ? { ...prev, ...updates } : null);
    if (user) {
      try { await apiUpdateProfile(user.id, updates); }
      catch { /* offline: local state kept */ }
    }
  }, [user]);

  const updateCompetencies = useCallback(async (scores: CompetencyScore[]) => {
    setUser(prev => prev ? { ...prev, competencies: scores } : null);
    let targetRole = selectedRole;
    if (user) {
      try {
        await apiUpdateCompetencies(user.id, scores);
        setBackendOnline(isBackendAvailable());
      } catch { /* offline */ }
      targetRole = user.currentRole || selectedRole;
      const analysis = await apiAnalyzeGaps(targetRole, scores);
      setSkillGaps(analysis.gaps);
    }
  }, [user, selectedRole]);

  const calculateGaps = useCallback(async (role?: string) => {
    if (!user) return;
    const targetRole = role || user.currentRole || selectedRole;
    const analysis = await apiAnalyzeGaps(targetRole, user.competencies);
    setSkillGaps(analysis.gaps);
    setSelectedRole(targetRole);
    setEnrolledCourses(analysis.recommendedCourses.slice(0, 2).map(c => ({
      ...c, enrolled: true, progress: 0,
    })));
  }, [user, selectedRole]);

  const enrollInCourse = useCallback(async (courseId: string) => {
    setEnrolledCourses(prev => {
      const exists = prev.find(c => c.id === courseId);
      if (exists) return prev;
      const course = allCoursesData.find(c => c.id === courseId);
      if (course) return [...prev, { ...course, enrolled: true, progress: 0 }];
      return prev;
    });
    if (user) {
      try { await apiEnrollCourse(user.id, courseId); }
      catch { /* offline */ }
    }
  }, [user]);

  const completeModule = useCallback(async (courseId: string, moduleTitle: string, assessmentScore: number) => {
    if (!user) return { ok: false, courseComplete: false, progress: 0, bumped: [] };
    const result = await apiCompleteModule(user.id, courseId, moduleTitle, assessmentScore);
    if (result.ok) {
      // refresh profile + recompute gaps so auto-updated competencies reflect
      const fresh = await apiLogin(user.role === 'admin' ? 'admin' : 'learner');
      setUser(fresh.user);
      if (user.role === 'learner') {
        const analysis = await apiAnalyzeGaps(fresh.user.currentRole || 'Data Analyst', fresh.user.competencies);
        setSkillGaps(analysis.gaps);
      }
      setEnrolledCourses(prev => prev.map(c => c.id === courseId ? { ...c, progress: result.progress } : c));
    }
    return result;
  }, [user]);

  const saveQuiz = useCallback(async (title: string, questions: QuizQuestion[], answers: (number | null)[]) => {
    let score = 0;
    if (user) {
      try {
        const result = await apiSubmitQuiz({
          user_id: user.id, title, questions, answers,
        });
        score = result.score;
      } catch {
        score = questions.reduce((acc, q, i) => acc + (answers[i] === q.correctAnswer ? 1 : 0), 0);
      }
    } else {
      score = questions.reduce((acc, q, i) => acc + (answers[i] === q.correctAnswer ? 1 : 0), 0);
    }
    const quiz: Quiz = {
      id: `quiz-${Date.now()}`,
      title,
      questions,
      score,
      totalQuestions: questions.length,
      completed: true,
      date: new Date().toISOString().split('T')[0],
      answers,
    };
    setQuizzes(prev => [quiz, ...prev]);
    return quiz;
  }, [user]);

  const sendAssistantMessage = useCallback(async (message: string) => {
    const userMsg: ChatMessage = { id: `m-${Date.now()}`, role: 'user', content: message, timestamp: new Date().toISOString() };
    const history = chatMessages.slice(-8).map(m => ({ role: m.role, content: m.content }));
    setChatMessages(prev => [...prev, userMsg]);
    let res: { reply: string; source?: 'llm' | 'rule' };
    try {
      res = await apiChatAssistant(message, user?.id ?? 'learner-1', history);
    } catch {
      res = { reply: "I am unable to reach the service at the moment. Kindly try again shortly.", source: 'rule' };
    }
    const replyMsg: ChatMessage = {
      id: `m-${Date.now()}-r`,
      role: 'assistant',
      content: res.reply,
      timestamp: new Date().toISOString(),
      source: res.source ?? 'rule',
    };
    setChatMessages(prev => [...prev, replyMsg]);
  }, [user, chatMessages]);

  const loadForecast = useCallback(async () => {
    const data = await apiAdminForecast();
    if (data) setForecast(data);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prev => !prev);
  }, []);

  const markNotificationRead = useCallback((_id: string) => {
    // noop for mock
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage(prev => {
      const nxt = prev === 'en' ? 'hi' : 'en';
      if (user) {
        const patch = { preferredLanguage: nxt === 'hi' ? 'Hindi' : 'English' };
        setUser(u => u ? { ...u, ...patch } : u);
      }
      return nxt;
    });
  }, [user]);

  const refreshData = useCallback(async () => {
    setBackendOnline(isBackendAvailable());
  }, []);

  const recommendedCourses = skillGaps.length > 0
    ? determineEnrollment(allCoursesData.filter(c => skillGaps.some(g => c.skillsCovered.includes(g.competencyName))), skillGaps, enrolledCourses)
    : [];

  return (
    <AppContext.Provider value={{
      user, isAuthenticated, skillGaps, recommendedCourses, enrolledCourses,
      quizzes, notifications, activities, selectedRole, sidebarOpen, backendOnline,
      labs, chatMessages, forecast, language,
      login, logout, updateUserProfile, updateCompetencies, setSelectedRole,
      calculateGaps, enrollInCourse, saveQuiz, toggleSidebar, markNotificationRead, refreshData,
      sendAssistantMessage, completeModule, loadForecast, toggleLanguage,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

export function useI18n() {
  const { language } = useApp();
  return { language, t: (en: string, hi?: string) => (language === 'hi' && hi ? hi : en) };
}