export type CompetencyCategory = 'Statistical' | 'Technical' | 'Digital Governance' | 'Behavioural';

export interface Competency {
  id: string;
  name: string;
  category: CompetencyCategory;
  description: string;
}

/** Where a competency's level came from. "default" = not covered by the role-based test. */
export type CompetencyScoreSource = 'tested' | 'default';

export interface CompetencyScore {
  competencyId: string;
  level: number; // 1-5
  source?: CompetencyScoreSource;
  accuracy?: number; // % correct, only when source === 'tested'
  selfRatedLevel?: number; // only if the self-rating step was completed
  testedAt?: string; // ISO timestamp
}

/** Provenance for the most recent automated role-based test. */
export interface TestMeta {
  testId: string;
  takenAt: string;
  // Optional: the backend persists the graded paper and its timestamp, but the
  // role context of the test is not stored alongside it.
  role?: string;
  roleLabel?: string;
  competencyIds?: string[];
  generatedBy?: string;
}

/** One graded question, persisted so the breakdown survives a refresh. */
export interface AssessmentQuestionRecord {
  position: number;
  questionId: string;
  competencyId: string;
  competencyName: string;
  prompt: string;
  options: string[];
  correctIndex: number;
  chosenIndex: number | null;
  difficulty: number;
  explanation: string;
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
  testMeta?: TestMeta;
  /** Per-question records for the most recent test, for the breakdown view. */
  assessmentQuestions?: AssessmentQuestionRecord[];
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

/**
 * Everything the dashboard draws, from one GET /api/dashboard.
 *
 * These were literals on the page before: learning hours was always 24, the
 * streak was always "7 days", and the pathway bars were 33/0/0. `null` here
 * means "the database has no row for this", which the UI renders as an
 * explicit dash — distinct from 0, which means a real measured zero.
 */
export interface DashboardSummary {
  learningHours: number;
  streak: number;
  /** ISO date of the learner's most recent activity, or null if never active. */
  streakAsOf: string | null;
  activeDayCount: number;
  activities: Activity[];
  notifications: Notification[];
  unreadCount: number;
  quizzes: {
    count: number;
    /** Percentage 0-100 across every scored quiz, or null if none scored. */
    average: number | null;
    last: {
      id: string;
      title: string;
      date: string;
      score: number;
      totalQuestions: number;
    } | null;
  };
  courses: {
    enrolled: number;
    completed: number;
    averageProgress: number;
  };
  pathway: {
    stage: string;
    /** Percentage 0-100 of that band meeting the target role's required level. */
    progress: number;
    met: number;
    total: number;
  }[];
  targetRole: string | null;
}

export interface AssessmentQuestion {
  id: string;
  competencyId: string;
  competencyName: string;
  category: CompetencyCategory;
  difficulty: 1 | 2 | 3 | 4 | 5;
  prompt: string;
  options: string[];
  correctIndex: number;
  explanation: string;
  stemSource?: 'llm' | 'bank' | 'stub';
}

export interface CompetencyTestResult {
  competencyId: string;
  competencyName: string;
  derivedLevel: number; // 1-5
  selfRatedLevel?: number; // manual self-rating if present
  perceptionGap?: number; // derived - selfRated (positive = underrated self)
  questionsAttempted: number;
  correctCount: number;
  accuracyPct: number;
  highestDifficultyCorrect: number;
}

export interface CompetencyTest {
  id: string;
  role: string;
  roleLabel: string;
  competencies: string[];
  questions: AssessmentQuestion[];
  results?: CompetencyTestResult[];
  takenAt?: string;
  locked: boolean;
  /**
   * Set when the test was graded locally because the backend was unreachable.
   * Distinguishes a genuine offline grade from a server response, so the caller
   * knows it must build the question breakdown itself — and must not trust
   * `takenAt`, which on this path is the generation time rather than submit time.
   */
  gradedOffline?: boolean;
}


// ---------------------------------------------------------------- official statistics
// World Bank Open Data for India, published under CC BY 4.0.
//
// The attribution fields (source, source_url, license, provenance) are not
// optional decoration. The licence requires attribution, so any UI that renders
// a StatIndicator is expected to display them. `provenance` is the field that
// keeps the app honest: it says which body actually produced the number
// ("National Statistical Offices", "UN World Population Prospects", "WHO"),
// which is not the same as saying "Indian government data" for all of them.

export interface StatIndicator {
  code: string;
  name: string;
  category: string;
  unit: string | null;
  provenance: string;
  source: string;
  source_url: string;
  license: string;
  first_year: number | null;
  last_year: number | null;
  observation_count: number | null;
}

export interface StatPoint {
  year: number;
  value: number | null;
}

export interface StatSeries {
  indicator: StatIndicator;
  count: number;
  points: StatPoint[];
}

export interface IndexedPoint {
  year: number;
  value: number | null;
  /** null when the series has no value at the shared base year. */
  indexed: number | null;
}

export interface CompareSeries {
  indicator: StatIndicator;
  base_year: number;
  base_value: number | null;
  points: IndexedPoint[];
}

export interface CompareResult {
  base_year: number;
  count: number;
  series: CompareSeries[];
}
