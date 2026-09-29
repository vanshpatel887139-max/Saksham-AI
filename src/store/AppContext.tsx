import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { UserProfile, SkillGap, Course, Quiz, Notification, Activity, CompetencyScore, QuizQuestion, Lab, ChatMessage, ForecastData, ModuleCompleteResult, AssessmentQuestionRecord, DashboardSummary } from '../types';
import { mockNotifications, mockActivities, mockLabs } from '../services/appService';
import { courses as allCoursesData } from '../data/mockData';
import {
  apiLogin, apiUpdateProfile, apiUpdateCompetencies, apiAnalyzeGaps, apiEnrollCourse,
  apiSubmitQuiz, apiGetLabs, apiChatAssistant, apiCompleteModule, apiAdminForecast,
  apiGetCourses, apiGetUser, isBackendAvailable, apiLogout, UNAUTHORIZED_EVENT, apiDashboard, apiClearChatHistory,
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
  /**
   * Server-measured dashboard figures, or null when the summary has not been
   * fetched (or the backend is unreachable). Read this instead of inventing
   * values in a component — that is how "Learning Hours 24" happened.
   */
  dashboard: DashboardSummary | null;
  /**
   * True only while the post-sign-in fetches are still in flight. The
   * dashboard uses it to tell "not loaded yet" from "genuinely empty", so it
   * can show a skeleton instead of an empty-state message that would turn out
   * to be wrong a second later.
   */
  dataLoading: boolean;
  /** Re-read the summary; call after anything that changes the numbers. */
  refreshDashboard: () => Promise<void>;
  selectedRole: string;
  sidebarOpen: boolean;
  backendOnline: boolean;
  labs: Lab[];
  chatMessages: ChatMessage[];
  forecast: ForecastData | null;
  language: Language;
}

interface AppContextType extends AppState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUserProfile: (updates: Partial<UserProfile>) => Promise<void>;
  updateCompetencies: (scores: CompetencyScore[]) => Promise<void>;
  /**
   * Seeds the latest-test paper into local profile state without a server call.
   * Used only on the offline grading path, where `apiUpdateCompetencies` throws
   * and the enriched response that normally carries the breakdown is absent.
   */
  setLocalAssessmentRecords: (records: AssessmentQuestionRecord[], testId: string, takenAt: string) => void;
  setSelectedRole: (role: string) => void;
  calculateGaps: (role?: string) => Promise<void>;
  enrollInCourse: (courseId: string) => Promise<void>;
  saveQuiz: (title: string, questions: QuizQuestion[], answers: (number | null)[]) => Promise<Quiz>;
  toggleSidebar: () => void;
  markNotificationRead: (id: string) => void;
  refreshData: () => Promise<void>;
  sendAssistantMessage: (message: string) => Promise<void>;
  /** Wipe the advisor transcript locally and on the server. */
  clearChat: () => Promise<void>;
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
  // Start empty rather than seeded with the mocks, so an offline sign-in shows
  // an honest empty feed instead of records that look like the user's own.
  // `appService` seeds them again if the summary call fails.
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  // null means "not loaded yet", which is distinct from a loaded summary whose
  // numbers happen to be zero. The dashboard uses it to avoid rendering a
  // spurious 0 hours for the moment before the request lands.
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  // False whenever data has settled; true only during the burst of fetches a
  // fresh sign-in starts. See the property's doc comment for why the
  // dashboard needs this distinct from `dashboard === null`.
  const [dataLoading, setDataLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [backendOnline, setBackendOnline] = useState(isBackendAvailable());
  const [labs, setLabs] = useState<Lab[]>(mockLabs);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [language, setLanguage] = useState<Language>('en');

  /**
   * Pull the dashboard's numbers, feed and notifications in one request.
   *
   * Callers that mutate the underlying tables (submitting a quiz, completing a
   * module) call this again afterwards, so a value shown on the dashboard
   * always reflects the last thing the user did rather than the state at
   * sign-in. Failures are swallowed to null deliberately: the rest of the app
   * must keep working when this one endpoint is unavailable.
   */
  const refreshDashboard = useCallback(async () => {
    try {
      const summary = await apiDashboard();
      setDashboard(summary);
      if (summary) {
        setActivities(summary.activities);
        setNotifications(summary.notifications);
        setBackendOnline(true);
      } else {
        // Offline: fall back to the bundled sample feed so the page is not
        // blank, but keep `dashboard` null so no card shows invented numbers.
        setActivities(mockActivities);
        setNotifications(mockNotifications);
      }
    } catch { /* 401 propagates to the session-expiry listener */ }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    // Throws on bad credentials — deliberately no catch, so a failed sign-in
    // leaves the user on the login screen instead of quietly continuing as a
    // mock learner.
    const result = await apiLogin(email, password);
    setUser(result.user);
    setIsAuthenticated(true);
    setBackendOnline(isBackendAvailable());
    setDataLoading(true);

    try {
      // The post-sign-in fetches are independent, so run them concurrently.
      // Serialised, the labs, transcript, dashboard summary and enrolment rows
      // were awaited one after another and the dashboard stayed empty — or
      // worse, showed its "no data yet" messages — for the whole chain's
      // latency. In parallel they resolve in roughly one round-trip.
      await Promise.all([
        apiGetLabs()
          .then(setLabs)
          .catch(() => { /* offline: keep mock labs */ }),
        // One request for hours, streak, feed, notifications, quiz stats and the
        // pathway. Previously the page rendered literals for all of these.
        refreshDashboard(),
        result.user.role === 'learner'
          ? (async () => {
              const [analysis, coursesRaw] = await Promise.all([
                apiAnalyzeGaps(result.user.currentRole || 'Data Analyst', result.user.competencies),
                apiGetCourses(result.user.id).catch(() => null),
              ]);
              setSkillGaps(analysis.gaps);
              const enrolled = coursesRaw && coursesRaw.length > 0
                ? coursesRaw
                : analysis.recommendedCourses.slice(0, 2);
              if (enrolled && enrolled.length > 0) {
                setEnrolledCourses(enrolled.filter(c => c.enrolled).length > 0
                  ? enrolled.filter(c => c.enrolled)
                  : analysis.recommendedCourses.slice(0, 2).map(c => ({ ...c, enrolled: true, progress: 10 })));
              } else {
                setEnrolledCourses(analysis.recommendedCourses.slice(0, 2).map(c => ({
                  ...c, enrolled: true, progress: Math.floor(Math.random() * 60) + 10,
                })));
              }
            })().catch(() => { /* per-profile data is best-effort */ })
          : Promise.resolve(),
      ]);
    } finally {
      // Even if one fetch fails the page keeps working; this flag is what the
      // dashboard uses to tell "still loading" from "genuinely empty".
      setDataLoading(false);
    }
  }, [refreshDashboard]);

  // An expired or revoked session produces a 401 on the next request, which
  // the api client reports here. Clearing the user is what makes the route
  // guards in App.tsx bounce back to the login screen; without it the user
  // would sit on a dashboard where every call fails.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setIsAuthenticated(false);
      setSkillGaps([]);
      setEnrolledCourses([]);
      setQuizzes([]);
      setChatMessages([]);
      setForecast(null);
      // Clear the feed too. Leaving the previous learner's activities and
      // notifications in state is the one leak this app cannot afford: they
      // are personal data, and a stale array would render on the next login
      // for up to the moment the new summary lands.
      setActivities([]);
      setNotifications([]);
      setDashboard(null);
      setDataLoading(false);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const logout = useCallback(() => {
    // Clear the server-side session too. Fire-and-forget: local state is
    // dropped immediately so the UI is never waiting on the network to sign
    // someone out, and apiLogout() swallows its own errors.
    void apiLogout();
    setUser(null);
    setIsAuthenticated(false);
    setSkillGaps([]);
    setEnrolledCourses([]);
    setQuizzes([]);
    setChatMessages([]);
    setForecast(null);
    setActivities([]);
    setNotifications([]);
    setDashboard(null);
    setDataLoading(false);
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
        // The response is the full enriched profile. Merge it in so that
        // testMeta / assessmentQuestions (only ever populated by this endpoint)
        // reach client state — otherwise the results page has no data to show.
        const fresh = await apiUpdateCompetencies(user.id, scores);
        setUser(prev => prev ? {
          ...prev,
          ...fresh,
          competencies: scores,
        } : fresh);
        setBackendOnline(isBackendAvailable());
      } catch { /* offline: local state kept */ }
      targetRole = user.currentRole || selectedRole;
      const analysis = await apiAnalyzeGaps(targetRole, scores);
      setSkillGaps(analysis.gaps);
    }
  }, [user, selectedRole]);

  const setLocalAssessmentRecords = useCallback((
    records: AssessmentQuestionRecord[],
    testId: string,
    takenAt: string,
  ) => {
    setUser(prev => prev ? {
      ...prev,
      testMeta: { ...prev.testMeta, testId, takenAt },
      assessmentQuestions: records,
    } : prev);
  }, []);

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
      // Refresh the profile so auto-updated competencies show up. This used to
      // call apiLogin() with a role to get a fresh copy, which meant every
      // module completion performed a second credential exchange just to read
      // data it was already authorised for.
      const fresh = await apiGetUser(user.id);
      setUser(fresh);
      if (user.role === 'learner') {
        const analysis = await apiAnalyzeGaps(fresh.currentRole || 'Data Analyst', fresh.competencies);
        setSkillGaps(analysis.gaps);
      }
      setEnrolledCourses(prev => prev.map(c => c.id === courseId ? { ...c, progress: result.progress } : c));
      // Module completion moves the hours, the pathway and the activity feed,
      // so re-read rather than patching them locally: progress is a
      // server-computed percentage and guessing it here would drift.
      void refreshDashboard();
    }
    return result;
  }, [user, refreshDashboard]);

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
    // The attempt is now a row in `quizzes`, so the dashboard's quiz average
    // and the activity feed are both out of date. Re-read them.
    void refreshDashboard();
    return quiz;
  }, [user, refreshDashboard]);

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

  const clearChat = useCallback(async () => {
    // Drop local state immediately so the UI never waits on the network, then
    // clear the server-side transcript best-effort (apiClearChatHistory swallows
    // its own failures).
    setChatMessages([]);
    await apiClearChatHistory();
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
      quizzes, notifications, activities, dashboard, dataLoading, refreshDashboard, selectedRole, sidebarOpen, backendOnline,
      labs, chatMessages, forecast, language,
      login, logout, updateUserProfile, updateCompetencies, setLocalAssessmentRecords, setSelectedRole,
      calculateGaps, enrollInCourse, saveQuiz, toggleSidebar, markNotificationRead, refreshData,
      sendAssistantMessage, completeModule, loadForecast, clearChat, toggleLanguage,
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