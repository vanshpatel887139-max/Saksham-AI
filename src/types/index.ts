export type CompetencyCategory = 'Statistical' | 'Technical' | 'Digital Governance' | 'Behavioural';

export interface Competency {
  id: string;
  name: string;
  category: CompetencyCategory;
  description: string;
}

export interface CompetencyScore {
  competencyId: string;
  level: number; // 1-5
}

export interface RoleRequirement {
  role: string;
  requirements: CompetencyScore[];
}

export interface SkillGap {
  competencyId: string;
  competencyName: string;
  category: CompetencyCategory;
  currentLevel: number;
  requiredLevel: number;
  gap: number;
  priority: 'High' | 'Medium' | 'Low' | 'No Gap';
}

export interface UserProfile {
  id: string;
  name: string;
  employeeId: string;
  designation: string;
  department: string;
  currentRole: string;
  education: string;
  experience: number;
  careerGoal: string;
  previousTraining: string;
  preferredLanguage: string;
  competencies: CompetencyScore[];
  profileCompleted: boolean;
  role: 'learner' | 'admin';
}

export interface CourseModule {
  title: string;
  duration: string;
  type: 'lesson' | 'lab' | 'quiz';
  summary: string;
  completed?: boolean;
  code?: string;
  sandbox?: 'python' | 'sql';
}

export interface Course {
  id: string;
  courseCode: string;
  title: string;
  provider: 'iGOT Karmayogi' | 'NSSTA';
  description: string;
  skillsCovered: string[];
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  duration: string;
  language: string;
  rating: number;
  thumbnail: string;
  category: CompetencyCategory;
  modules: CourseModule[];
  enrolled: boolean;
  progress: number;
}

export interface LabExercise {
  title?: string;
  code?: string;
  table?: string;
  rows?: (string | number)[][];
  preset?: string;
  labels?: string[];
  values?: number[];
  type?: string;
  x?: number[];
  y?: number[];
  explain?: string;
  points?: [string, number][];
}

export interface Lab {
  id: string;
  title: string;
  category: string;
  description: string;
  icon: string;
  exercises: LabExercise[];
}

export interface PythonRunResult {
  ok: boolean;
  output: string;
  error?: string;
  durationMs?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  source?: 'llm' | 'rule';
}

export interface ChatReply {
  reply: string;
  exact?: boolean;
  source?: 'llm' | 'rule';
  model?: string;
}

export interface QuizGenerationResult {
  quizId: string;
  title: string;
  questions: QuizQuestion[];
  generatedBy?: string;
}

export interface IgotPlanFocusArea {
  competency: string;
  gap: number;
  recommendation: string;
}

export interface IgotPlanCourse {
  courseId: string;
  title: string;
  courseCode: string;
  provider: string;
  action: string;
}

export interface IgotPlanWeek {
  week: number;
  theme: string;
  courses: IgotPlanCourse[];
  practice: string;
  assessment: string;
  outcome: string;
}

export interface IgotPlan {
  title: string;
  summary: string;
  focusAreas: IgotPlanFocusArea[];
  weeks: IgotPlanWeek[];
  certPath: string[];
  source?: 'llm' | 'rule';
  model?: string;
}

export interface ForecastPoint {
  label: string;
  value: number;
}

export interface ForecastFuturePoint {
  label: string;
  hours: number;
  completions: number;
}

export interface ForecastData {
  method: string;
  future: ForecastFuturePoint[];
  readinessTrend: ForecastPoint[];
  insights: string[];
}

export interface ModuleCompleteResult {
  ok: boolean;
  courseComplete: boolean;
  progress: number;
  bumped: { id: string; name: string; before: number; after: number }[];
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctAnswer: number;
  explanation: string;
  difficulty: 'Easy' | 'Medium' | 'Hard';
  sourceExcerpt: string;
}

export interface Quiz {
  id: string;
  title: string;
  questions: QuizQuestion[];
  score?: number;
  totalQuestions: number;
  completed: boolean;
  date: string;
  answers?: (number | null)[];
}

export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning';
  date: string;
  read: boolean;
}

export interface Activity {
  id: string;
  action: string;
  detail: string;
  date: string;
  icon: string;
}
