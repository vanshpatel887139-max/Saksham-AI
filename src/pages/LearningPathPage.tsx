import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/layout/Header';
import { Card, Badge, Button, ProgressBar } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { apiGeneratePlan } from '../services/api';
import { IgotPlan } from '../types';
import { Route, CheckCircle, Circle, ArrowRight, Lock, Sparkles, Target, Award, BookOpen, CalendarDays } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';

const pathwayStages = [
  {
    title: 'Foundation',
    description: 'Build core statistical and technical knowledge',
    color: 'from-green-500 to-green-600',
    courses: [
      { name: 'Fundamentals of Official Statistics', provider: 'NSSTA', duration: '8 weeks', status: 'completed' as const },
      { name: 'Python for Government Data Analysis', provider: 'iGOT Karmayogi', duration: '10 weeks', status: 'in-progress' as const },
      { name: 'SQL for Statistical Databases', provider: 'iGOT Karmayogi', duration: '6 weeks', status: 'locked' as const },
    ],
  },
  {
    title: 'Role-Specific Skills',
    description: 'Develop competencies required for your target role',
    color: 'from-saffron-500 to-saffron-600',
    courses: [
      { name: 'Survey Design and Sampling', provider: 'NSSTA', duration: '6 weeks', status: 'locked' as const },
      { name: 'Data Visualization with Power BI', provider: 'iGOT Karmayogi', duration: '5 weeks', status: 'locked' as const },
      { name: 'Data Privacy and Cybersecurity', provider: 'NSSTA', duration: '4 weeks', status: 'locked' as const },
    ],
  },
  {
    title: 'Advanced & Future Skills',
    description: 'Prepare for leadership and emerging technologies',
    color: 'from-navy-600 to-navy-800',
    courses: [
      { name: 'Introduction to Artificial Intelligence', provider: 'iGOT Karmayogi', duration: '8 weeks', status: 'locked' as const },
      { name: 'Advanced Machine Learning for Statistics', provider: 'iGOT Karmayogi', duration: '12 weeks', status: 'locked' as const },
      { name: 'Leadership in Digital Governance', provider: 'iGOT Karmayogi', duration: '6 weeks', status: 'locked' as const },
    ],
  },
];

const statusIcons = {
  completed: <CheckCircle size={16} className="text-green-500" />,
  'in-progress': <ArrowRight size={16} className="text-saffron-500" />,
  locked: <Lock size={16} className="text-navy-300" />,
};

const statusLabels = {
  completed: 'Completed',
  'in-progress': 'In Progress',
  locked: 'Locked',
};

export default function LearningPathPage() {
  const { user, language } = useApp();
  const { t } = useI18n();
  const navigate = useNavigate();
  const { animate, staggerStyle } = useStagger();
  const [generating, setGenerating] = useState(false);
  const [planWeeks, setPlanWeeks] = useState(2);
  const [plan, setPlan] = useState<IgotPlan | null>(null);

  const generatePlan = async () => {
    const targetRole = user?.currentRole || user?.careerGoal || '';
    setGenerating(true);
    try {
      const result = await apiGeneratePlan(user?.id || 'learner-1', targetRole, planWeeks, language === 'hi' ? 'Hindi' : 'English');
      setPlan(result);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <Header title="Learning Path" />
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-2 stagger-fade-up" style={staggerStyle(0, animate)}>
          <Route size={20} className="text-saffron-500" />
          <div>
            <h2 className="text-lg font-semibold text-navy-800">Your Personalized Learning Pathway</h2>
            <p className="text-sm text-navy-400">Three-stage pathway tailored to your career goal: Senior Statistical Officer</p>
          </div>
        </div>

        <div className="relative">
          <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-navy-100 hidden md:block" />

          {pathwayStages.map((stage, si) => (
            <div key={stage.title} className="relative mb-8 last:mb-0">
              <div className="hidden md:flex absolute left-5 w-7 h-7 rounded-full bg-white border-2 border-navy-200 items-center justify-center z-10">
                <span className="text-xs font-bold text-navy-600">{si + 1}</span>
              </div>

              <div className="md:ml-16">
                <Card className="stagger-fade-up" style={staggerStyle(1 + si, animate)}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stage.color} flex items-center justify-center text-white font-bold`}>
                      {si + 1}
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-navy-800">{stage.title}</h3>
                      <p className="text-xs text-navy-400">{stage.description}</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {stage.courses.map(course => (
                      <div key={course.name} className={`flex items-center justify-between p-3 rounded-lg border ${course.status === 'completed' ? 'bg-green-50 border-green-200' : course.status === 'in-progress' ? 'bg-saffron-50 border-saffron-200' : 'bg-navy-50 border-navy-100'}`}>
                        <div className="flex items-center gap-3">
                          {statusIcons[course.status]}
                          <div>
                            <p className="text-sm font-medium text-navy-800">{course.name}</p>
                            <p className="text-xs text-navy-400">{course.provider} • {course.duration}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={course.status === 'completed' ? 'success' : course.status === 'in-progress' ? 'warning' : 'default'}>
                            {statusLabels[course.status]}
                          </Badge>
                          {course.status !== 'locked' && (
                            <Button size="sm" variant={course.status === 'completed' ? 'ghost' : 'primary'}>
                              {course.status === 'completed' ? 'Review' : 'Continue'}
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {si === 0 && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-navy-500">Stage Progress</span>
                        <span className="font-medium text-navy-700">33%</span>
                      </div>
                      <ProgressBar value={1} max={3} size="sm" />
                    </div>
                  )}
                </Card>
              </div>
            </div>
          ))}
        </div>

        {/* iGOT Karmayogi AI Learning Plan */}
        <Card className="border-saffron-200 bg-gradient-to-br from-saffron-50/70 to-white stagger-fade-up" style={staggerStyle(4, animate)}>
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Sparkles size={18} className="text-saffron-500" />
                <h3 className="text-base font-semibold text-navy-800">iGOT Karmayogi AI Learning Plan</h3>
              </div>
              <p className="text-sm text-navy-400">Generate a week-by-week career plan from your real skill gaps, mapped to the iGOT Karmayogi & NSSTA course catalogue.</p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={planWeeks}
                onChange={e => setPlanWeeks(Number(e.target.value))}
                className="px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white"
              >
                <option value={2}>2 weeks</option>
                <option value={4}>4 weeks</option>
                <option value={8}>8 weeks</option>
              </select>
              <Button onClick={generatePlan} disabled={generating}>
                {generating ? <><span className="animate-spin mr-2">⟳</span> Planning...</> : <><Sparkles size={16} className="mr-1" /> Generate AI Plan</>}
              </Button>
            </div>
          </div>

          {plan && (
            <div className="mt-5 pt-5 border-t border-saffron-200">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <h4 className="text-sm font-semibold text-navy-800">{plan.title}</h4>
                <Badge variant={plan.source === 'llm' ? 'success' : 'default'}>
                  {plan.source === 'llm' ? `AI · ${plan.model}` : 'Rule-based'}
                </Badge>
              </div>
              <p className="text-xs text-navy-500 mb-4">{plan.summary}</p>

              {plan.focusAreas && plan.focusAreas.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-navy-600 uppercase tracking-wide mb-2 flex items-center gap-1">
                    <Target size={12} /> Focus Areas
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {plan.focusAreas.map((f, i) => (
                      <Badge key={i} variant="warning">
                        {f.competency} · gap {f.gap}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {plan.weeks.map(w => (
                  <div key={w.week} className="border border-navy-100 rounded-xl p-4 bg-white">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-7 h-7 rounded-full bg-saffron-500 text-white flex items-center justify-center text-xs font-bold">
                        {w.week}
                      </span>
                      <CalendarDays size={14} className="text-navy-300" />
                      <p className="text-sm font-semibold text-navy-800">{w.theme}</p>
                    </div>
                    <div className="space-y-2">
                      {w.courses.map((c, ci) => (
                        <div key={ci} className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-navy-50 border border-navy-100">
                          <div className="flex items-center gap-2 min-w-0">
                            <BookOpen size={14} className="text-saffron-500 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-xs font-medium text-navy-800 truncate">{c.title}</p>
                              <p className="text-[10px] text-navy-400">{c.courseCode} · {c.provider}</p>
                            </div>
                          </div>
                          {c.courseId && (
                            <Button size="sm" variant="secondary" onClick={() => navigate(`/courses/${c.courseId}`)}>
                              Open Course
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                    {(w.practice || w.assessment || w.outcome) && (
                      <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2">
                        {w.practice && <p className="text-[11px] text-navy-500"><span className="font-medium text-navy-700">Practice:</span> {w.practice}</p>}
                        {w.assessment && <p className="text-[11px] text-navy-500"><span className="font-medium text-navy-700">Assess:</span> {w.assessment}</p>}
                        {w.outcome && <p className="text-[11px] text-navy-500"><span className="font-medium text-navy-700">Outcome:</span> {w.outcome}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {plan.certPath && plan.certPath.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-navy-600 uppercase tracking-wide mb-2 flex items-center gap-1">
                    <Award size={12} /> Suggested Certification Path
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {plan.certPath.map((cert, i) => (
                      <span key={i} className="px-2 py-1 bg-white border border-navy-200 rounded-full text-[10px] text-navy-600">
                        {cert}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4 flex items-center gap-1.5">
                <Circle size={10} className="text-navy-300" />
                <p className="text-[10px] text-navy-400">{t('AI-generated plan — review with an authorized trainer before following it.', 'एआई-जनित योजना — इसका पालन करने से पहले किसी अधिकृत प्रशिक्षक से समीक्षा करें।')}</p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}