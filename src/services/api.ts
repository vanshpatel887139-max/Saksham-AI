/**
 * SakshamAI API client.
 *
 * Talks to the FastAPI backend at VITE_API_URL. See the API_URL definition below
 * for the four cases: `npm run dev` with it unset addresses a local backend
 * directly, and a production build defaults to same-origin relative requests,
 * which is the deployed shape (vercel.json rewrites /api/* to the API
 * server-side). All functions gracefully fall back to local in-memory mock
 * services when the backend is unreachable, so the app works in both demo modes.
 *
 * Authentication is not part of that automatic fallback. A failed sign-in used
 * to resolve to a mock user, which made a wrong password, a dead session and a
 * working demo indistinguishable. See apiLogin for how the fixed demo
 * credentials are handled instead.
 */

import { UserProfile, SkillGap, Course, Quiz, QuizQuestion, CompetencyScore, Lab, ModuleCompleteResult, ForecastData, ChatReply, QuizGenerationResult, IgotPlan, PythonRunResult, CompetencyTest, StatIndicator, StatSeries, CompareResult, DashboardSummary } from '../types';
import { competencies, roleRequirements, courses as mockCourses } from '../data/mockData';
import {
  defaultLearner, calculateSkillGaps, getRecommendedCourses,
  generateMCQs, mockLabs, deriveCompetencyTestLevels, buildRoleCompetencyTest,
  TEST_SUBSET_SIZE, QUESTIONS_PER_COMPETENCY,
  DEMO_LOGINS,
} from './appService';

/**
 * Base URL every request is built on.
 *
 *   `npm run dev`, unset        -> `http://localhost:8000`. VITE_API_URL was
 *                                  never set and a developer is running the
 *                                  backend locally, so address it directly.
 *   production build, unset     -> relative. See below.
 *   `''`                        -> relative, same-origin. The deployed shape.
 *   a URL                      -> used as-is, trailing slashes trimmed.
 *
 * Why an unset production build does NOT fall back to localhost: `VITE_*` values
 * are inlined at build time, so a production bundle with the var unset carries a
 * literal `http://localhost:8000`. On Vercel that means every request is aimed
 * at the visitor's own machine, `request()` sees a network failure, and the app
 * falls back to its in-memory mock data — a fully rendered demo backed by
 * nothing, with no error anywhere. Requiring an explicitly-empty
 * VITE_API_URL to avoid that is a trap, because "unset" and "set to empty" look
 * identical in most dashboards. So the default is same-origin in production,
 * which is what the /api rewrite in vercel.json provides.
 *
 * Note the `=== undefined` rather than `||`: `''` is falsy, so a `||` fallback
 * would turn the deliberate same-origin setting back into localhost.
 */
const RAW_API_URL = import.meta.env.VITE_API_URL as string | undefined;
const API_URL =
  RAW_API_URL === undefined
    ? import.meta.env.DEV
      ? 'http://localhost:8000'
      : ''
    : RAW_API_URL.replace(/\/+$/, '');

/**
 * The session cookie is `SameSite=strict`, and SameSite is evaluated per
 * *site* — a registrable domain — not per origin. The port is irrelevant, but
 * the hostname is not: `localhost` and `127.0.0.1` are different sites even
 * though they are the same machine. Point the app at one and the API at the
 * other and the browser silently withholds the cookie, so every request 401s
 * and the UI just bounces back to the login screen with no explanation.
 *
 * That is a miserable thing to debug from the symptom, so it is called out
 * here instead. Dev-only, and a warning rather than a hard failure, because in
 * production the API is normally a same-site subdomain where this is moot.
 */
if (import.meta.env.DEV && typeof window !== 'undefined') {
  try {
    const apiHost = new URL(API_URL).hostname;
    if (apiHost !== window.location.hostname) {
      console.warn(
        `[auth] VITE_API_URL points at "${apiHost}" but this page is served from ` +
          `"${window.location.hostname}". The session cookie is SameSite=strict and ` +
          `SameSite compares hostnames, so the browser will not send it and every ` +
          `request will 401. Use the same hostname on both sides, or serve /api ` +
          `through the Vite proxy so the app is same-origin.`,
      );
    }
  } catch {
    // A relative or unparseable API_URL is fine — the proxy case.
  }
}

/** Fired when a request comes back 401 so the store can force a sign-out. */
export const UNAUTHORIZED_EVENT = 'sakshamai:unauthorized';

let backendAvailable = true;

export function isBackendAvailable(): boolean {
  return backendAvailable;
}

/**
 * The session lives in an httpOnly cookie set by the backend, so there is
 * nothing to keep here and nothing to persist.
 *
 * The token used to sit in sessionStorage. That survives a refresh, which was
 * the reason for it, but sessionStorage is readable by any script on the page,
 * so a single XSS anywhere in the bundle was enough to exfiltrate a live
 * session. An httpOnly cookie is attached by the browser itself and cannot be
 * read by script at all; the cost is that it becomes an ambient credential, so
 * the backend pairs it with `SameSite=strict` and an Origin check. Losing the
 * token from JS is the whole point — do not reintroduce a copy in localStorage
 * or sessionStorage "just so the UI can read it".
 */

/**
 * An error carrying the HTTP status.
 *
 * This exists because the old client treated *every* failure as "backend is
 * down" and silently served mock data instead. That is fine for a dropped
 * connection and actively harmful for a 401: an expired session would have
 * quietly become an offline demo with fabricated numbers rather than asking
 * the user to sign in again. Callers can now branch on `status`.
 */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  /** True when the request never reached the server. */
  get isOffline(): boolean {
    return this.status === 0;
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

/**
 * In-flight refresh, shared so that N simultaneous 401s cause one refresh.
 *
 * Without this, a dashboard fires six requests at once, all six come back 401
 * when the access token lapses, and all six try to refresh. Supabase *rotates*
 * the refresh token on every exchange, so the five losers would present an
 * already-consumed token and their replays would fail — turning a routine
 * one-hour expiry into a forced sign-out. The losers await the winner's
 * promise and then replay with the cookie the winner's response set.
 */
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      // Called through raw fetch, not request(): this is the retry path, and
      // routing it back through request() would re-enter the 401 handler.
      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      return res.ok;
    } catch {
      // Offline or the backend is down. Report failure so the caller signs
      // out rather than looping; the next successful load can try again.
      return false;
    } finally {
      // Cleared after settling, so a later expiry gets a fresh attempt.
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function request<T>(
  path: string,
  options?: RequestInit,
  isRetry = false,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };

  let res: Response;
  try {
    // credentials:'include' is what carries the session cookie. Without it the
    // browser drops the cookie on a cross-origin request and every call 401s.
    res = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: 'include' });
  } catch (e) {
    // Genuine network failure: the request never reached the server.
    backendAvailable = false;
    throw new ApiError(0, e instanceof Error ? e.message : 'network error');
  }

  if (res.status === 401 && !path.startsWith('/api/auth/') && !isRetry) {
    // The access token is an hour long and the refresh token a week. Try the
    // refresh before giving up, so an hour of idle time is not an involuntary
    // sign-out. On success the browser has already been given a new access
    // cookie, so simply replay the original call.
    if (await refreshSession()) {
      return request<T>(path, options, true);
    }
  }

  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    // The session is gone and could not be refreshed. The cookie is httpOnly,
    // so the client cannot clear it and does not need to: tell the app, so the
    // route guard sends the user back to the login screen instead of leaving
    // them on a dashboard whose every request is now failing.
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
  }

  if (!res.ok) {
    let detail = `API error ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch { /* non-JSON error body; keep the generic message */ }
    // A 5xx means the server is up but unhealthy, so the backend is still
    // "available" — do not flip the app into offline mock mode for it.
    if (res.status < 500) backendAvailable = true;
    throw new ApiError(res.status, detail);
  }

  backendAvailable = true;
  return await res.json() as T;
}

// ---------- Auth ----------

export interface DemoAccount {
  userId: string;
  email: string;
  name: string;
  department: string;
  designation: string;
  role: 'learner' | 'admin';
}

export async function apiGetDemoUsers(): Promise<{ users: DemoAccount[]; demoPassword: string | null }> {
  return request<{ users: DemoAccount[]; demoPassword: string | null }>('/api/auth/demo-users')
    .catch(() => ({ users: [], demoPassword: null }));
}

/**
 * Exchange credentials for a session.
 *
 * Normally this hits Supabase Auth through the backend. When the backend is
 * completely unreachable there is nothing left to verify a password against,
 * so the two fixed demo logins in DEMO_LOGINS are accepted locally and resolve
 * to the matching mock profile.
 *
 * That fallback is deliberately narrow. It requires an exact email *and* an
 * exact password match, and it only applies when the request never reached a
 * server (`isOffline`). If a backend is running and answers with 401/403/422,
 * the error is surfaced instead — a live backend is never bypassed, so this
 * cannot be used to escalate into an account whose credentials you don't know.
 */
export async function apiLogin(email: string, password: string): Promise<{ user: UserProfile }> {
  const key = email.trim().toLowerCase();
  try {
    const result = await request<{ user: UserProfile }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: key, password }),
    });
    return result;
  } catch (e) {
    const offline = e instanceof ApiError && e.isOffline;
    const demo = DEMO_LOGINS[key];
    if (!offline) throw e;

    if (demo && demo.password === password) {
      // No cookie was set, because no server answered. Nothing authorises
      // against this, so a refresh correctly returns to the login screen.
      return { user: demo.user };
    }

    // Offline, and these are not the demo logins. Surface that plainly instead
    // of leaking the underlying "Failed to fetch", which reads as a network
    // fault rather than a rejected sign-in.
    if (demo) throw new ApiError(0, 'That is not the demo password. Start the backend to sign in with your own account.');
    throw new ApiError(0, 'No server is reachable and that email is not a demo login. Start the backend, or pick a demo login below.');
  }
}

export async function apiGetUser(userId: string): Promise<UserProfile> {
  return request<UserProfile>(`/api/users/${userId}`).catch((e) => {
    if (e instanceof ApiError && e.isAuthError) throw e;
    throw new Error('offline');
  });
}

/**
 * Ask the backend to clear the session cookie.
 *
 * The cookie is httpOnly, so the client cannot delete it. If this call fails
 * because the server is unreachable, the cookie is still in the browser — the
 * user will appear signed out because local state is cleared, but the
 * credential is still there and will work again once the server is back. That
 * is why callers must not treat a failed logout as a guarantee, and why the
 * cookie's own `Max-Age` bounds the exposure.
 */
export async function apiLogout(): Promise<void> {
  try {
    await request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' });
  } catch {
    // Best effort by design — see above. Never block the UI on it.
  }
}

// ---------- Profile ----------

/** Receipt returned by account erasure. Contains no identifier, only counts. */
export interface EraseReceipt {
  deleted: boolean;
  userId: string;
  rowsRemoved: Record<string, number>;
  totalRowsRemoved: number;
  /** False if the Supabase Auth identity could not be removed. Check it. */
  authAccountRemoved: boolean;
  authAccountDetail: string;
  note: string;
}

/**
 * Erase the signed-in user's account and every row held about them.
 *
 * There is deliberately no offline fallback here, unlike the other profile
 * calls. A failed erasure must surface as a failure; silently pretending the
 * data was deleted would be the worst possible outcome for this operation.
 */
export async function apiDeleteMyAccount(): Promise<EraseReceipt> {
  return request<EraseReceipt>('/api/users/me', {
    method: 'DELETE',
    body: JSON.stringify({ confirmation: 'DELETE' }),
  });
}

export async function apiUpdateProfile(userId: string, updates: Partial<UserProfile>): Promise<UserProfile> {
  return request<UserProfile>(`/api/users/${userId}`, { method: 'PUT', body: JSON.stringify(updates) })
    .catch(() => {
      // fallback: patch locally (client state is patched by caller)
      throw new Error('offline');
    });
}

export async function apiUpdateCompetencies(userId: string, scores: CompetencyScore[]): Promise<UserProfile> {
  return request<UserProfile>(`/api/users/${userId}/competencies`, { method: 'PUT', body: JSON.stringify({ competencies: scores }) })
    .catch(() => {
      throw new Error('offline');
    });
}

// ---------- Competency framework ----------

export async function apiGetCompetencies() {
  return request<typeof competencies>('/api/competencies').catch(() => competencies);
}

export async function apiGetRoles(): Promise<string[]> {
  return request<{ role: string }[] | any[]>('/api/roles')
    .then(r => (r as any[]).map(x => x.role))
    .catch(() => roleRequirements.map(r => r.role));
}

// ---------- Skill gaps & recommendations ----------

export interface GapAnalysisResult {
  role: string;
  gaps: SkillGap[];
  topGaps: SkillGap[];
  recommendedCourses: Course[];
}

export async function apiAnalyzeGaps(role: string, scores: CompetencyScore[]): Promise<GapAnalysisResult> {
  return request<GapAnalysisResult>('/api/assessment/gaps', {
    method: 'POST',
    body: JSON.stringify({ role, competencies: scores }),
  }).catch(() => {
    const gaps = calculateSkillGaps(scores, role);
    return {
      role,
      gaps,
      topGaps: gaps.filter(g => g.priority === 'High' || g.priority === 'Medium').slice(0, 3),
      recommendedCourses: getRecommendedCourses(gaps),
    };
  });
}

// ---------- Courses ----------

export async function apiGetCourses(userId?: string): Promise<Course[]> {
  const q = userId ? `?user_id=${userId}` : '';
  return request<Course[]>(`/api/courses${q}`).catch(() => mockCourses);
}

export async function apiEnrollCourse(userId: string, courseId: string) {
  return request(`/api/courses/enroll`, { method: 'POST', body: JSON.stringify({ user_id: userId, course_id: courseId }) })
    .catch(() => ({ ok: false }));
}

export async function apiGetCourseDetail(courseId: string, userId?: string): Promise<Course> {
  const q = userId ? `?user_id=${userId}` : '';
  return request<Course>(`/api/courses/${courseId}${q}`)
    .catch(() => mockCourses.find(c => c.id === courseId)!);
}

export async function apiCompleteModule(userId: string, courseId: string, moduleTitle: string, assessmentScore = 0): Promise<ModuleCompleteResult> {
  return request<ModuleCompleteResult>(`/api/courses/module-complete`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, course_id: courseId, module_title: moduleTitle, assessment_score: assessmentScore }),
  }).catch(() => ({ ok: false, courseComplete: false, progress: 0, bumped: [] }));
}

  // ---------- VIRTUAL LABS ----------
  
  export async function apiGetLabs(): Promise<Lab[]> {
    return request<Lab[]>('/api/labs').catch(() => mockLabs);
  }
  
  /** Real CPython execution in the sandboxed backend runner. Throws when offline. */
  export async function apiRunPython(code: string): Promise<PythonRunResult> {
    return request<PythonRunResult>('/api/labs/run', { method: 'POST', body: JSON.stringify({ code }) });
  }
  
  // ---------- OFFICIAL STATISTICS ----------
  // World Bank Open Data for India (CC BY 4.0). The attribution fields travel
  // with every indicator on purpose: the licence requires credit, so a caller
  // cannot render a number without also having the means to say where it is
  // from. These throw on failure rather than falling back to invented rows —
  // a statistics product must never silently substitute made-up data.
  
  export async function apiGetIndicators(category?: string): Promise<StatIndicator[]> {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    const d = await request<{ indicators: StatIndicator[] }>(`/api/stats/indicators${q}`);
    return d.indicators;
  }
  
  export async function apiGetSeries(code: string): Promise<StatSeries> {
    return request<StatSeries>(`/api/stats/series/${encodeURIComponent(code)}`);
  }
  
  export async function apiCompareIndicators(codes: string[]): Promise<CompareResult> {
    const d = await request<CompareResult>(`/api/stats/compare?codes=${encodeURIComponent(codes.join(','))}`);
    return d;
  }
  
// ---------- ASSISTANT CHAT ----------

export async function apiChatAssistant(message: string, user_id: string, history?: { role: string; content: string }[]): Promise<ChatReply> {
  return request<ChatReply>(`/api/assistant/chat`, {
    method: 'POST',
    body: JSON.stringify({ user_id, message, history: history ?? [] }),
  })
    .catch(() => ({ reply: fallbackAssistant(message), exact: false, source: 'rule' }));
}

/**
 * Load the persisted advisor transcript.
 *
 * The server records every turn in `advisor_messages`, so a conversation
 * survives a refresh or a move to another browser instead of resetting to
 * empty. Returns [] offline.
 */
export async function apiChatHistory(): Promise<{ role: 'user' | 'assistant'; content: string; at: string | null }[]> {
  const res = await request<{ messages: { role: 'user' | 'assistant'; content: string; at: string | null }[] }>(
    '/api/assistant/history'
  ).catch(() => ({ messages: [] }));
  return res.messages;
}

export async function apiClearChatHistory(): Promise<void> {
  await request('/api/assistant/history', { method: 'DELETE' }).catch(() => undefined);
}

/**
 * Fetch every number the dashboard shows in one round trip.
 *
 * Batched deliberately: the page used to be assembled from a mix of literals
 * and one endpoint at a time, so the cards briefly disagreed with each other
 * while requests were in flight. One request also means the cards flip from
 * loading to loaded together.
 *
 * A 401 is rethrown rather than swallowed, because it means the session is
 * gone and the app must return to the login screen. Other failures resolve to
 * null so an offline backend leaves the rest of the dashboard usable.
 */
export async function apiDashboard(): Promise<DashboardSummary | null> {
  try {
    return await request<DashboardSummary>('/api/dashboard');
  } catch (e) {
    if (e instanceof ApiError && e.isAuthError) throw e;
    return null;
  }
}

function fallbackAssistant(message: string): string {
  const m = message.toLowerCase();
  if (m.includes('plan')) return "Here is a 2-week study plan for your priority skill gaps:\n- **Week 1**: focus on your top gaps — 45 minutes daily on the recommended iGOT Karmayogi / NSSTA modules\n- **Week 2**: micro-assessments and Virtual Lab practice to consolidate learning\n\nKindly confirm, and I can expand any week into a day-wise schedule.";
  if (m.includes('course') || m.includes('gap')) return "Based on your profile, priority areas include **Python**, **AI/ML** and **Data Visualization**. Please refer to the Course Catalogue for the matching iGOT Karmayogi and NSSTA recommendations (e.g. Python for Government Data Analysis — iGOT-MOD-301).";
  if (m.includes('interview')) return "To prepare for your assessments and interviews:\n- Review the competency requirements of your target role\n- Attempt 2–3 micro-assessments daily from the Quiz Generator\n- Revise the module content on your Learning Path\n\nWould you like a study plan to structure this preparation?";
  return "Welcome to SakshamAI. I assist with skill gaps, course recommendations, study plans, interview preparation and statistics concepts. You may try: 'Which courses do I need?' or 'Create a study plan for me'.";
}

// ---------- Quiz ----------

export async function apiGenerateQuiz(text: string, count: number, difficulty: string): Promise<QuizGenerationResult> {
  return request<QuizGenerationResult>(`/api/quiz/generate`, { method: 'POST', body: JSON.stringify({ text, count, difficulty }) })
    .catch(() => {
      return {
        quizId: `local-${Date.now()}`,
        title: `${difficulty} Quiz`,
        questions: generateMCQs(text, count, difficulty),
        generatedBy: 'mock',
      };
    });
}

export async function apiGenerateQuizFromFile(file: File, count: number, difficulty: string): Promise<QuizGenerationResult> {
  const form = new FormData();
  form.append('file', file);
  form.append('count', String(count));
  form.append('difficulty', difficulty);
  try {
    // Raw fetch because the body is FormData, which must not carry the JSON
    // content-type. The session cookie rides along via credentials:'include'.
    const res = await fetch(`${API_URL}/api/quiz/generate/file`, {
      method: 'POST',
      body: form,
      credentials: 'include',
    });
    if (!res.ok) throw new ApiError(res.status, `API error ${res.status}`);
    backendAvailable = true;
    return await res.json();
  } catch (e) {
    backendAvailable = false;
    throw e;
  }
}

export async function apiSubmitQuiz(payload: { user_id: string; title: string; questions: QuizQuestion[]; answers: (number | null)[] }): Promise<{ quizId: string; score: number; total: number }> {
  return request<{ quizId: string; score: number; total: number }>(`/api/quiz/submit`, { method: 'POST', body: JSON.stringify(payload) })
    .catch(() => {
      const score = payload.questions.reduce((acc, q, i) => acc + (payload.answers[i] === q.correctAnswer ? 1 : 0), 0);
      return { quizId: `local-${Date.now()}`, score, total: payload.questions.length };
    });
}

export async function apiGetQuizHistory(userId: string): Promise<Quiz[]> {
  return request<Quiz[]>(`/api/quiz/history/${userId}`).catch(() => []);
}

// ---------- Admin ----------

export async function apiAdminOverview() {
  return request(`/api/admin/overview`).catch(() => null);
}

export async function apiAdminLearners() {
  return request(`/api/admin/learners`).catch(() => []);
}

export async function apiAdminCharts() {
  return request(`/api/admin/charts`).catch(() => null);
}

export async function apiAdminForecast(): Promise<ForecastData | null> {
  return request<ForecastData>(`/api/admin/forecast`).catch(() => null);
}

// ---------- iGOT Karmayogi Learning Plan ----------

export async function apiGeneratePlan(userId: string, targetRole: string, weeks: number, language: string): Promise<IgotPlan> {
  return request<IgotPlan>(`/api/igot/plan`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, target_role: targetRole, weeks, language }),
  }).catch(() => fallbackPlan(weeks));
}

function fallbackPlan(weeks: number): IgotPlan {
  const gaps = calculateSkillGaps(defaultLearner.competencies, defaultLearner.currentRole).filter(g => g.gap > 0).slice(0, weeks);
  const top = gaps.length ? gaps : [{ competencyName: 'Statistical Analysis', gap: 1 } as SkillGap];
  const weeksOut: IgotPlan['weeks'] = top.map((g, i) => {
    const matches = mockCourses.filter(c => c.skillsCovered.includes(g.competencyName));
    return {
      week: i + 1,
      theme: `Master ${g.competencyName}`,
      courses: matches.slice(0, 2).map(c => ({
        courseId: c.id, title: c.title, courseCode: c.courseCode, provider: c.provider, action: 'Enroll and complete all modules',
      })) as IgotPlan['weeks'][number]['courses'],
      practice: `45 min/day on ${g.competencyName} modules; use Virtual Labs sandboxes.`,
      assessment: 'Complete 2 micro-assessments from the Quiz Generator.',
      outcome: `Close the ${g.gap}-level gap on ${g.competencyName}.`,
    };
  });
  return {
    title: 'iGOT Karmayogi Learning Plan',
    summary: 'Offline plan built from your current skill gaps.',
    focusAreas: top.map(g => ({ competency: g.competencyName, gap: g.gap, recommendation: 'Prioritize iGOT/NSSTA modules covering this competency' })),
    weeks: weeksOut,
    certPath: top.map(g => `iGOT module completion - ${g.competencyName}`),
    source: 'rule',
    model: '',
  };
}
/**
 * Question generation can take a while when the LLM is reachable, so it gets a
 * longer budget than the default. On timeout `request` throws and the caller
 * falls back to the local bank rather than leaving the UI spinning forever.
 */
const GENERATE_TIMEOUT_MS = 30_000;

export async function apiGenerateCompetencyTest(
  role: string,
  roleLabel: string,
  competencyIds: string[],
  maxQuestions: number = TEST_SUBSET_SIZE * QUESTIONS_PER_COMPETENCY,
  questionsPerCompetency: number = QUESTIONS_PER_COMPETENCY
): Promise<CompetencyTest> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), GENERATE_TIMEOUT_MS);
  const opts = { maxQuestions, questionsPerCompetency };
  try {
    return await request<CompetencyTest>('/api/assessment/generate', {
      method: 'POST',
      body: JSON.stringify({ role, roleLabel, competencyIds, ...opts }),
      signal: controller.signal,
    });
  } catch {
    return buildRoleCompetencyTest(role, roleLabel, competencyIds, opts);
  } finally {
    clearTimeout(timer);
  }
}

export async function apiSubmitCompetencyTest(
  test: CompetencyTest,
  answers: (number | null)[],
  userId?: string,
  selfRatings: Record<string, number> = {}
): Promise<CompetencyTest> {
  return request<CompetencyTest>('/api/assessment/submit', {
      method: 'POST',
      body: JSON.stringify({
        testId: test.id,
        role: test.role,
        roleLabel: test.roleLabel,
        questions: test.questions,
        answers,
        userId,
        selfRatings,
      }),
    })
    .catch(() => ({
      ...test,
      results: deriveCompetencyTestLevels(test.questions, answers),
      locked: true,
      // Explicit marker: `isBackendAvailable()` is also false for a 4xx/5xx, so
      // it cannot distinguish a real offline grade from a rejected request.
      gradedOffline: true,
    }));
}
