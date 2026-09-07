/**
 * SakshamAI API client.
 *
 * Talks to the FastAPI backend at VITE_API_URL (default http://localhost:8000).
 * All functions gracefully fall back to local in-memory mock services when the
 * backend is unreachable, so the app works in both demo modes.
 */

import { UserProfile, SkillGap, Course, Quiz, QuizQuestion, CompetencyScore, Lab, ModuleCompleteResult, ForecastData, ChatReply, QuizGenerationResult, IgotPlan, PythonRunResult } from '../types';
import { competencies, roleRequirements, courses as mockCourses } from '../data/mockData';
import {
  defaultLearner, adminUser, calculateSkillGaps, getRecommendedCourses,
  generateMCQs, mockLabs,
} from './appService';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000';

let backendAvailable = true;

export function isBackendAvailable(): boolean {
  return backendAvailable;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`API error ${res.status}`);
    backendAvailable = true;
    return await res.json() as T;
  } catch (e) {
    backendAvailable = false;
    throw e;
  }
}

// ---------- Auth ----------

export async function apiLogin(role: 'learner' | 'admin'): Promise<{ token: string; user: UserProfile }> {
  return request<{ token: string; user: UserProfile }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ role }) })
    .catch(() => {
      const user = role === 'admin' ? adminUser : defaultLearner;
      return { token: `local-token-${user.id}`, user };
    });
}

// ---------- Profile ----------

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

// ---------- ASSISTANT CHAT ----------

export async function apiChatAssistant(message: string, user_id: string, history?: { role: string; content: string }[]): Promise<ChatReply> {
  return request<ChatReply>(`/api/assistant/chat`, {
    method: 'POST',
    body: JSON.stringify({ user_id, message, history: history ?? [] }),
  })
    .catch(() => ({ reply: fallbackAssistant(message), exact: false, source: 'rule' }));
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
    const res = await fetch(`${API_URL}/api/quiz/generate/file`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`API error ${res.status}`);
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