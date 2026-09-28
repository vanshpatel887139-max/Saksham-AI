import { UserProfile, SkillGap, Competency, RoleRequirement, Course, QuizQuestion, Notification, Activity, Lab, CompetencyCategory, CompetencyTestResult, CompetencyTest, AssessmentQuestion, CompetencyScore, AssessmentQuestionRecord } from '../types';
import { competencies, roleRequirements, courses, assessmentQuestionBank, generateStubCompetencyQuestions, shuffleQuestionOptions } from '../data/mockData';

export const mockLabs: Lab[] = [
  {
    id: 'lab-python',
    title: 'Python Data Lab',
    category: 'Technical',
    description: 'Run Python snippets to explore data analysis fundamentals - variables, lists, loops, dictionaries and basic statistics.',
    icon: '🐍',
    exercises: [
      { title: 'Basics', code: "ages = [28, 34, 29, 41, 36]\nprint('Mean age:', sum(ages) / len(ages))" },
      { title: 'Statistics', code: "import statistics\nvalues = [3.1, 2.8, 3.6, 3.9, 2.4]\nprint('Mean:', statistics.mean(values))\nprint('Median:', statistics.median(values))\nprint('Variance:', round(statistics.variance(values), 3))" },
    ],
  },
  {
    id: 'lab-sql',
    title: 'SQL Query Lab',
    category: 'Technical',
    description: 'Write SQL against real World Bank India statistics - SELECT, WHERE, ORDER BY and aggregates, with errors reported instead of silent failure.',
    icon: '🗃️',
    exercises: [
      { table: 'districts', rows: [['id', 'name', 'state', 'population', 'literacy'], [1, 'Alwar', 'Rajasthan', 3674179, 70.7], [2, 'Mysuru', 'Karnataka', 3054822, 72.6], [3, 'Nashik', 'Maharashtra', 6109052, 80.9], [4, 'Ludhiana', 'Punjab', 3498739, 82.2], [5, 'Varanasi', 'Uttar Pradesh', 3676841, 70.3], [6, 'Thrissur', 'Kerala', 3121200, 95.1]] },
      { table: 'samples', rows: [['district_id', 'households_surveyed', 'dept'], [1, 420, 'NSSO'], [2, 515, 'Census'], [3, 310, 'NSSTA'], [4, 600, 'NSSO'], [5, 275, 'Census'], [6, 505, 'NSSTA']] },
    ],
  },
  {
    id: 'lab-viz',
    title: 'Data Visualization Lab',
    category: 'Technical',
    description: 'Build a chart with your own numbers. Try literacy rates by district or competitor skill levels.',
    icon: '📈',
    exercises: [
      { preset: 'Literacy by District', labels: ['Alwar', 'Mysuru', 'Nashik', 'Ludhiana', 'Varanasi', 'Thrissur'], values: [70.7, 72.6, 80.9, 82.2, 70.3, 95.1], type: 'bar' },
    ],
  },
  {
    id: 'lab-ml',
    title: 'AI/ML Playground',
    category: 'Technical',
    description: 'Fit a linear regression to data points and see predicted values - the same math behind forecasting.',
    icon: '🤖',
    exercises: [
      { title: 'Linear Regression', x: [1, 2, 3, 4, 5, 6], y: [12, 15, 17, 20, 22, 25], explain: 'hours studied -> score prediction' },
    ],
  },
  {
    id: 'lab-gis',
    title: 'GIS Mapping Sandbox',
    category: 'Technical',
    description: 'Visualize district data as a thematic map. Explore how GIS layers work for official statistics.',
    icon: '🗺️',
    exercises: [
      { preset: 'District Data', points: [['Alwar', 70.7], ['Mysuru', 72.6], ['Nashik', 80.9], ['Ludhiana', 82.2], ['Varanasi', 70.3], ['Thrissur', 95.1] as [string, number]] },
    ],
  },
];

export const defaultLearner: UserProfile = {
  id: 'learner-1',
  name: 'Ananya Sharma',
  employeeId: 'GOV-2021-0847',
  designation: 'Statistical Investigator',
  department: 'National Sample Survey Office',
  currentRole: 'Data Analyst',
  education: 'M.Sc. Statistics, University of Delhi',
  experience: 3,
  careerGoal: 'Senior Statistical Officer',
  previousTraining: 'Basic Data Entry, Census Operations Training',
  preferredLanguage: 'English',
  competencies: [
    { competencyId: 'survey-design', level: 3 },
    { competencyId: 'sampling', level: 2 },
    { competencyId: 'data-quality', level: 3 },
    { competencyId: 'python', level: 1 },
    { competencyId: 'sql', level: 2 },
    { competencyId: 'data-visualization', level: 2 },
    { competencyId: 'ai-ml', level: 1 },
    { competencyId: 'cybersecurity', level: 2 },
    { competencyId: 'data-privacy', level: 3 },
    { competencyId: 'communication', level: 4 },
    { competencyId: 'leadership', level: 2 },
    { competencyId: 'project-management', level: 2 },
    { competencyId: 'national-accounts', level: 2 },
    { competencyId: 'price-statistics', level: 2 },
    { competencyId: 'labour-statistics', level: 2 },
    { competencyId: 'agricultural-statistics', level: 2 },
    { competencyId: 'industrial-statistics', level: 2 },
    { competencyId: 'sdg-indicators', level: 3 },
    { competencyId: 'metadata-standards', level: 2 },
    { competencyId: 'r', level: 1 },
    { competencyId: 'stata', level: 2 },
    { competencyId: 'spss', level: 2 },
    { competencyId: 'sas', level: 1 },
    { competencyId: 'gis', level: 1 },
    { competencyId: 'cloud-computing', level: 1 },
    { competencyId: 'api-open-data', level: 1 },
    { competencyId: 'digital-signatures', level: 2 },
    { competencyId: 'government-cloud', level: 1 },
    { competencyId: 'digital-public-infra', level: 1 },
    { competencyId: 'ethics', level: 4 },
    { competencyId: 'decision-making', level: 3 },
    { competencyId: 'change-management', level: 2 },
  ],
  profileCompleted: true,
  role: 'learner',
};

export const adminUser: UserProfile = {
  id: 'admin-1',
  name: 'Dr. Rajesh Kumar',
  employeeId: 'GOV-2015-0123',
  designation: 'Director',
  department: 'National Sample Survey Office',
  currentRole: 'Administrator',
  education: 'Ph.D. Statistics, IIT Kanpur',
  experience: 15,
  careerGoal: 'Additional Secretary',
  previousTraining: 'Leadership Development Program, Advanced Statistical Methods',
  preferredLanguage: 'English',
  competencies: [
    { competencyId: 'survey-design', level: 5 },
    { competencyId: 'sampling', level: 5 },
    { competencyId: 'data-quality', level: 5 },
    { competencyId: 'national-accounts', level: 5 },
    { competencyId: 'price-statistics', level: 5 },
    { competencyId: 'labour-statistics', level: 5 },
    { competencyId: 'agricultural-statistics', level: 5 },
    { competencyId: 'industrial-statistics', level: 5 },
    { competencyId: 'sdg-indicators', level: 5 },
    { competencyId: 'metadata-standards', level: 5 },
    { competencyId: 'python', level: 3 },
    { competencyId: 'r', level: 3 },
    { competencyId: 'sql', level: 4 },
    { competencyId: 'stata', level: 4 },
    { competencyId: 'spss', level: 3 },
    { competencyId: 'sas', level: 3 },
    { competencyId: 'gis', level: 3 },
    { competencyId: 'data-visualization', level: 5 },
    { competencyId: 'ai-ml', level: 3 },
    { competencyId: 'cloud-computing', level: 3 },
    { competencyId: 'api-open-data', level: 3 },
    { competencyId: 'cybersecurity', level: 5 },
    { competencyId: 'data-privacy', level: 5 },
    { competencyId: 'digital-signatures', level: 3 },
    { competencyId: 'government-cloud', level: 3 },
    { competencyId: 'digital-public-infra', level: 3 },
    { competencyId: 'communication', level: 5 },
    { competencyId: 'leadership', level: 5 },
    { competencyId: 'project-management', level: 5 },
    { competencyId: 'ethics', level: 5 },
    { competencyId: 'decision-making', level: 5 },
    { competencyId: 'change-management', level: 5 },
  ],
  profileCompleted: true,
  role: 'admin',
};

/**
 * The two fixed demo logins, usable only when no backend is reachable.
 *
 * ############################################################################
 * # THIS PASSWORD IS PUBLIC IN A DEV BUILD. IT IS COMPILED INTO THE         #
 * # SHIPPED JS BUNDLE.                                                      #
 * #                                                                          #
 * # `Demo@1234` below is a literal in client source, so anyone can read it   #
 * # with curl, view-source, or the network tab. Moving it to a              #
 * # `VITE_*` variable would NOT help: Vite inlines those into the same       #
 * # bundle. This is a deliberate demo affordance, NOT a secret and NOT        #
 * # authentication — it exists only so the UI can be explored before a       #
 * # backend is wired up.                                                     #
 * #                                                                          #
 * # A production build must not contain it, so the table is behind            #
 * # `import.meta.env.DEV` and is empty when `npm run build` runs. That is    #
 * # now automatic — verified by scripts/check_deploy.py, which greps the     #
 * # built bundle for this string and fails the deploy if it finds it.        #
 * #                                                                          #
 * # The gitleaks allowlist entry that keeps this from failing a commit is   #
 * # scoped to this file and is still required, because the *source* still   #
 * # contains the literal.                                                    #
 * ############################################################################
 *
 * The addresses match the rows seeded by supabase/migrations/003_seed.sql
 * and the password matches DEMO_USER_PASSWORD in .env.example, so the same two
 * logins work unchanged once a real backend is connected — at which point they
 * are verified by Supabase Auth and this table stops being consulted.
 *
 * apiLogin only ever consults it when the backend is unreachable, so a running
 * backend always takes precedence and cannot be bypassed this way.
 *
 * The passwords live in the JavaScript bundle, which means anyone who can
 * download the bundle can read them. That is acceptable for a demo and not
 * acceptable for a deployment, so the table is empty in a production build and
 * the offline fallback can never authenticate anyone. Vite replaces
 * `import.meta.env.DEV` with a literal at build time, so the strings below are
 * dropped from the output entirely rather than merely unreachable — check the
 * built bundle for "Demo@1234" to confirm.
 */
const DEMO_PASSWORDS: Record<string, { password: string; user: UserProfile }> =
  import.meta.env.DEV
    ? {
        'learner-1@sakshamai.demo': { password: 'Demo@1234', user: defaultLearner },
        'admin-1@sakshamai.demo': { password: 'Demo@1234', user: adminUser },
      }
    : {};

export const DEMO_LOGINS: Record<string, { password: string; user: UserProfile }> = DEMO_PASSWORDS;


export const mockNotifications: Notification[] = [
  { id: 'n1', message: 'Your Data Visualization competency improved from Level 2 to Level 3 after completing the recommended course and assessment.', type: 'success', date: '2025-09-01', read: false },
  { id: 'n2', message: 'New course available: Advanced Machine Learning for Statistics', type: 'info', date: '2025-08-28', read: false },
  { id: 'n3', message: 'You have 3 high-priority skill gaps to address for your target role.', type: 'warning', date: '2025-08-25', read: true },
  { id: 'n4', message: 'Monthly learning streak: 7 days! Keep it up.', type: 'success', date: '2025-08-20', read: true },
];

export const mockActivities: Activity[] = [
  { id: 'a1', action: 'Completed Quiz', detail: 'Python for Government Data Analysis - Score: 80%', date: '2025-09-01', icon: '📝' },
  { id: 'a2', action: 'Enrolled in Course', detail: 'Data Visualization with Power BI', date: '2025-08-28', icon: '📚' },
  { id: 'a3', action: 'Skill Improved', detail: 'Data Visualization: Level 2 → Level 3', date: '2025-08-25', icon: '🎯' },
  { id: 'a4', action: 'Completed Course', detail: 'Introduction to Artificial Intelligence', date: '2025-08-20', icon: '✅' },
  { id: 'a5', action: 'Profile Updated', detail: 'Added career goal: Senior Statistical Officer', date: '2025-08-15', icon: '👤' },
];

export const mockOrgLearners = [
  { name: 'Ananya Sharma', department: 'National Sample Survey Office', role: 'Data Analyst', competency: 2.4, gaps: 4, completed: 3, status: 'Active' },
  { name: 'Vikram Singh', department: 'Census Division', role: 'Statistical Investigator', competency: 3.1, gaps: 2, completed: 5, status: 'Active' },
  { name: 'Priya Patel', department: 'National Sample Survey Office', role: 'Data Analyst', competency: 2.8, gaps: 3, completed: 4, status: 'Active' },
  { name: 'Amit Verma', department: 'DGCIS', role: 'Senior Statistical Officer', competency: 3.9, gaps: 1, completed: 7, status: 'Active' },
  { name: 'Sneha Reddy', department: 'Census Division', role: 'Statistical Investigator', competency: 2.2, gaps: 5, completed: 2, status: 'Inactive' },
  { name: 'Rahul Gupta', department: 'National Sample Survey Office', role: 'Data Analyst', competency: 3.5, gaps: 2, completed: 6, status: 'Active' },
  { name: 'Deepa Nair', department: 'NSSTA', role: 'Senior Statistical Officer', competency: 4.1, gaps: 1, completed: 8, status: 'Active' },
  { name: 'Karthik Menon', department: 'DGCIS', role: 'Statistical Investigator', competency: 2.6, gaps: 3, completed: 3, status: 'Active' },
  { name: 'Meera Joshi', department: 'National Sample Survey Office', role: 'Data Analyst', competency: 3.0, gaps: 3, completed: 4, status: 'Active' },
  { name: 'Suresh Kumar', department: 'NSSTA', role: 'Senior Statistical Officer', competency: 3.7, gaps: 2, completed: 5, status: 'Active' },
];

export function calculateSkillGaps(currentScores: { competencyId: string; level: number }[], targetRole: string): SkillGap[] {
  const roleReq = roleRequirements.find(r => r.role === targetRole);
  if (!roleReq) return [];

  return roleReq.requirements.map(req => {
    const current = currentScores.find(c => c.competencyId === req.competencyId);
    const currentLevel = current ? current.level : 0;
    const gap = Math.max(0, req.level - currentLevel);
    let priority: SkillGap['priority'] = 'No Gap';
    if (gap >= 3) priority = 'High';
    else if (gap === 2) priority = 'Medium';
    else if (gap === 1) priority = 'Low';

    const comp = competencies.find(c => c.id === req.competencyId)!;
    return {
      competencyId: req.competencyId,
      competencyName: comp.name,
      category: comp.category,
      currentLevel,
      requiredLevel: req.level,
      gap,
      priority,
    };
  });
}

export function getRecommendedCourses(gaps: SkillGap[]): Course[] {
  const highGaps = gaps.filter(g => g.priority === 'High' || g.priority === 'Medium');
  const gapSkillNames = highGaps.map(g => g.competencyName);

  return courses.filter(course =>
    course.skillsCovered.some(skill => gapSkillNames.includes(skill))
  );
}

export function determineEnrollment(allCourses: Course[], gaps: SkillGap[], enrolled: Course[]): Course[] {
  const matched = getRecommendedCourses(gaps);
  return matched.map(c => {
    const enrol = enrolled.find(e => e.id === c.id);
    return enrol ? enrol : c;
  });
}

export function generateMCQs(text: string, count: number, difficulty: string): QuizQuestion[] {
  const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 20);
  const words = text.split(/\s+/).filter(w => w.length > 5);
  const questions: QuizQuestion[] = [];

  const templates = [
    (topic: string, detail: string) => ({
      question: `What is the primary purpose of ${topic} in official statistics?`,
      correctAnswer: 0,
      options: [
        `To ensure systematic and accurate ${detail}`,
        'To reduce operational costs only',
        'To automate all manual processes',
        'To replace human judgment entirely',
      ],
    }),
    (topic: string, detail: string) => ({
      question: `Which of the following best describes ${topic}?`,
      correctAnswer: 1,
      options: [
        'A technique used only in private sector',
        `A methodology for ${detail}`,
        'An outdated practice in statistics',
        'A type of hardware component',
      ],
    }),
    (topic: string, detail: string) => ({
      question: `In the context of government data, ${topic} is important because:`,
      correctAnswer: 2,
      options: [
        'It reduces the need for data collection',
        'It only applies to financial data',
        `It ensures ${detail} in official records`,
        'It eliminates all data errors',
      ],
    }),
    (topic: string, detail: string) => ({
      question: `What is a key challenge when implementing ${topic}?`,
      correctAnswer: 0,
      options: [
        `Ensuring data quality and ${detail}`,
        'Lack of government interest',
        'Too much available funding',
        'Excess of qualified personnel',
      ],
    }),
    (topic: string, _detail: string) => ({
      question: `Which skill is most related to ${topic}?`,
      correctAnswer: 3,
      options: [
        'Cooking and food preparation',
        'Mechanical engineering',
        'Agricultural science',
        `Analytical thinking and ${_detail}`,
      ],
    }),
  ];

  const usedSentences = new Set<string>();

  for (let i = 0; i < count; i++) {
    const sentence = sentences[i % sentences.length] || words.slice(i * 3, i * 3 + 10).join(' ');
    const topic = words[i % words.length] || 'statistical methods';
    const template = templates[i % templates.length];

    if (usedSentences.has(sentence) && sentences.length > count) {
      continue;
    }
    usedSentences.add(sentence);

    const generated = template(topic, sentence.trim().substring(0, 60));
    const shuffled = [...generated.options];
    const correctText = shuffled[generated.correctAnswer];

    for (let j = shuffled.length - 1; j > 0; j--) {
      const k = Math.floor(Math.random() * (j + 1));
      [shuffled[j], shuffled[k]] = [shuffled[k], shuffled[j]];
    }
    const newCorrectIndex = shuffled.indexOf(correctText);

    questions.push({
      id: `q-${Date.now()}-${i}`,
      question: generated.question,
      options: shuffled,
      correctAnswer: newCorrectIndex,
      explanation: `Based on the provided content: "${sentence.trim().substring(0, 100)}..."`,
      difficulty: difficulty as QuizQuestion['difficulty'],
      sourceExcerpt: sentence.trim().substring(0, 120),
    });
  }

  return questions;
}

export function getOverallCompetencyScore(competencies: { level: number }[]): number {
  if (competencies.length === 0) return 0;
  const sum = competencies.reduce((acc, c) => acc + c.level, 0);
  return Math.round((sum / competencies.length) * 10) / 10;
}

export function getRoleRequirements(): RoleRequirement[] {
  return roleRequirements;
}

export function getAllCompetencies(): Competency[] {
  return competencies;
}

export function getAllCourses(): Course[] {
  return courses;
}
export interface AssessmentQuestionSpec {
  competencyId: string;
  competencyName: string;
  category: CompetencyCategory;
  description: string;
}

export function deriveCompetencyTestLevels(
  questions: AssessmentQuestion[],
  answers: (number | null)[]
): CompetencyTestResult[] {
  const byCompetency = new Map<string, { q: AssessmentQuestion; index: number }[]>();
  questions.forEach((q, index) => {
    const list = byCompetency.get(q.competencyId) || [];
    list.push({ q, index });
    byCompetency.set(q.competencyId, list);
  });
  const results: CompetencyTestResult[] = [];
  for (const [competencyId, entries] of byCompetency) {
    let correct = 0;
    let maxDifficultyCorrect = 0;
    for (const { q, index } of entries) {
      const answer = answers[index];
      if (answer !== null && answer !== undefined && answer === q.correctIndex) {
        correct += 1;
        if (q.difficulty > maxDifficultyCorrect) maxDifficultyCorrect = q.difficulty;
      }
    }
    const accuracyPct = Math.round((correct / entries.length) * 100);
    let derived = accuracyPct >= 90 ? 5 : accuracyPct >= 75 ? 4 : accuracyPct >= 55 ? 3 : accuracyPct >= 35 ? 2 : 1;
    derived = Math.min(derived, Math.max(1, maxDifficultyCorrect));
    results.push({
      competencyId,
      competencyName: entries[0].q.competencyName,
      derivedLevel: derived,
      questionsAttempted: entries.length,
      correctCount: correct,
      accuracyPct,
      highestDifficultyCorrect: maxDifficultyCorrect,
    });
  }
  return results;
}

/**
 * The role-based test deliberately covers only a focused subset of the 32 role
 * competencies. A role has 32 requirements, so spreading a small question budget
 * across all of them yields one question each — far too thin to derive a 1-5
 * level from. Anything outside the subset is surfaced as "Not covered by test".
 */
export const TEST_SUBSET_SIZE = 6;
export const QUESTIONS_PER_COMPETENCY = 3;

/**
 * Picks the competencies most worth testing: highest required level first, ties
 * broken by the largest current gap. Returns at most `limit` entries.
 */
export function selectTestCompetencies(
  targetRole: string,
  currentScores: { competencyId: string; level: number }[],
  limit = TEST_SUBSET_SIZE
): CompetencyScore[] {
  const req = getRoleRequirements().find(r => r.role === targetRole);
  if (!req) return [];
  const currentOf = new Map(currentScores.map(c => [c.competencyId, c.level]));
  return [...req.requirements]
    .map(r => ({
      competencyId: r.competencyId,
      level: r.level,
      gap: Math.max(0, r.level - (currentOf.get(r.competencyId) ?? 0)),
    }))
    .sort((a, b) => b.level - a.level || b.gap - a.gap || a.competencyId.localeCompare(b.competencyId))
    .slice(0, Math.max(0, limit))
    .map(({ competencyId, level }) => ({ competencyId, level }));
}

export function buildRoleCompetencyTest(
  targetRole: string,
  roleLabel: string,
  competencyIds: string[],
  opts: { maxQuestions?: number; questionsPerCompetency?: number } = {}
): CompetencyTest {
  const maxQuestions = opts.maxQuestions ?? TEST_SUBSET_SIZE * QUESTIONS_PER_COMPETENCY;
  const perCompetency = opts.questionsPerCompetency ?? QUESTIONS_PER_COMPETENCY;
  const byCompetency = new Map<string, AssessmentQuestion[]>();
  for (const q of assessmentQuestionBank) {
    const list = byCompetency.get(q.competencyId) || [];
    list.push(q);
    byCompetency.set(q.competencyId, list);
  }
  const questions: AssessmentQuestion[] = [];
  for (const competencyId of competencyIds) {
    if (questions.length >= maxQuestions) break;
    const comp = competencies.find(c => c.id === competencyId);
    const bank = byCompetency.get(competencyId);
    let qs: AssessmentQuestion[];
    if (bank && bank.length >= 3) {
      qs = bank;
    } else if (comp) {
      qs = generateStubCompetencyQuestions({
        competencyId: comp.id,
        competencyName: comp.name,
        category: comp.category,
        description: comp.description,
      });
    } else {
      qs = [];
    }
    for (const q of qs) {
      if (questions.length >= maxQuestions) break;
      if (questions.filter(x => x.competencyId === competencyId).length >= perCompetency) break;
      questions.push(shuffleQuestionOptions(q));
    }
  }
  return {
    id: `ct-${Date.now()}`,
    role: targetRole,
    roleLabel,
    competencies: competencyIds.map(id => competencies.find(c => c.id === id)?.name || id),
    questions,
    takenAt: new Date().toISOString(),
    locked: false,
  };
}

/**
 * Writes test-derived levels into the profile, keeping everything the test did
 * not cover untouched — that is what makes a retake non-destructive.
 *
 * Provenance travels with each score so the results view can distinguish a
 * tested level from a default without re-running anything.
 */
export function applyCompetencyTestToProfile(
  profile: { competencies: CompetencyScore[] },
  test: CompetencyTest,
  selfRatings: Record<string, number> = {}
): { competencies: CompetencyScore[] } {
  if (!test.results || test.results.length === 0) return { competencies: profile.competencies };
  const testedAt = test.takenAt || new Date().toISOString();
  const byId = new Map(test.results.map(r => [r.competencyId, r]));

  const merged = profile.competencies.map(c => {
    const r = byId.get(c.competencyId);
    if (!r) {
      // Not covered by this test: keep the existing level and its provenance.
      return c.source ? c : { ...c, source: 'default' as const };
    }
    return {
      ...c,
      level: r.derivedLevel,
      source: 'tested' as const,
      accuracy: r.accuracyPct,
      selfRatedLevel: selfRatings[c.competencyId] ?? r.selfRatedLevel,
      testedAt,
    };
  });

  for (const r of test.results) {
    if (!merged.some(c => c.competencyId === r.competencyId)) {
      merged.push({
        competencyId: r.competencyId,
        level: r.derivedLevel,
        source: 'tested',
        accuracy: r.accuracyPct,
        selfRatedLevel: selfRatings[r.competencyId] ?? r.selfRatedLevel,
        testedAt,
      });
    }
  }
  return { competencies: merged };
}

/** Flattens a test + answers into the per-question records the breakdown view renders. */
export function buildQuestionRecords(
  test: CompetencyTest,
  answers: (number | null)[]
): AssessmentQuestionRecord[] {
  return test.questions.map((q, position) => ({
    position,
    questionId: q.id,
    competencyId: q.competencyId,
    competencyName: q.competencyName,
    prompt: q.prompt,
    options: q.options,
    correctIndex: q.correctIndex,
    chosenIndex: answers[position] ?? null,
    difficulty: q.difficulty,
    explanation: q.explanation,
  }));
}
