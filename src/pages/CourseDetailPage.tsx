import { useNavigate, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Button, Badge, ProgressBar, EmptyState } from '../components/ui/UIComponents';
import CodeRunner from '../components/CodeRunner';
import { useApp } from '../store/AppContext';
import { apiGetCourseDetail } from '../services/api';
import { Course, CourseModule } from '../types';
import { ArrowLeft, Clock, Star, Play, CheckCircle2, BookOpen, Bot, ChevronRight, Code2 } from 'lucide-react';

export default function CourseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, completeModule, enrollInCourse, skillGaps } = useApp();
  const [course, setCourse] = useState<Course | null>(null);
  const [activeModule, setActiveModule] = useState<CourseModule | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState(0);
  const [bumpNotice, setBumpNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      apiGetCourseDetail(id, user?.id).then(c => {
        setCourse(c);
        setLoading(false);
      });
    }
  }, [id, user]);

  if (loading) return <div><Header title="Course" /><div className="p-6">Loading course...</div></div>;
  if (!course) return <div><Header title="Course" /><div className="p-6"><EmptyState icon="📭" title="Course not found" description="The course you are looking for does not exist." /></div></div>;

  const enrolled = course.enrolled || false;
  const modules = course.modules || [];

  const startModule = (m: CourseModule) => {
    setActiveModule(m);
    setAnswers(modules[modules.indexOf(m)]?.type === 'quiz' ? Array(m.type === 'quiz' ? 3 : 0).fill(null) : []);
    setSubmitted(false);
    setScore(0);
    setBumpNotice(null);
  };

  const isQuiz = activeModule?.type === 'quiz';
  const microQuestions = [
    { q: `What is the main takeaway of "${activeModule?.title}"?`, o: ['It aligns with official statistics practice', 'It is only about theory', 'It replaces all other methods', 'It has no practical value'], c: 0 },
    { q: `How does understanding "${activeModule?.title}" support your target role?`, o: ['By strengthening relevant competencies', 'It does not matter', 'By reducing responsibilities', 'By skipping assessments'], c: 0 },
    { q: `Which competency does "${activeModule?.title}" most directly build?`, o: ['The one linked to this course', 'Unrelated soft skills', 'Technical only', 'None of these'], c: 0 },
  ];

  const handleAnswer = (idx: number, opt: number) => {
    setAnswers(prev => { const n = [...prev]; n[idx] = opt; return n; });
  };

  const submitAssessment = async () => {
    if (!activeModule || !course) return;
    const sc = answers.reduce<number>((acc, a, i) => acc + (a !== null && a === microQuestions[i].c ? 1 : 0), 0);
    setScore(sc);
    setSubmitted(true);
    const result = await completeModule(course.id, activeModule.title, sc);
    if (result.bumped && result.bumped.length > 0) {
      setBumpNotice(`🎉 Course complete! ${result.bumped.map(b => `${b.name}: Level ${b.before} → ${b.after}`).join(', ')}`);
    } else if (result.courseComplete) {
      setBumpNotice('🏆 You completed all modules of this course!');
    } else {
      setBumpNotice(`✅ Module completed. Course progress is now ${result.progress}%.`);
    }
  };

  const markComplete = async () => {
    if (!activeModule || !course) return;
    const result = await completeModule(course.id, activeModule.title, 0);
    setSubmitted(true);
    setScore(0);
    if (result.bumped && result.bumped.length > 0) {
      setBumpNotice(`🎉 Course complete! ${result.bumped.map(b => `${b.name}: Level ${b.before} → ${b.after}`).join(', ')}`);
    } else if (result.courseComplete) {
      setBumpNotice('🏆 You completed all modules of this course!');
    } else {
      setBumpNotice(`✅ Module completed. Course progress is now ${result.progress}%.`);
    }
  };

  const reasonCount = skillGaps.filter(g => course.skillsCovered.includes(g.competencyName)).length;

  return (
    <div>
      <Header title={course.title} />
      <div className="p-6 space-y-6">
        <button onClick={() => navigate('/courses')} className="flex items-center gap-1 text-sm text-navy-500 hover:text-navy-800 cursor-pointer">
          <ArrowLeft size={16} /> Back to Course Catalogue
        </button>

        <div className="bg-gradient-to-r from-navy-800 to-navy-900 rounded-2xl p-6 text-white">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <span className="text-5xl">{course.thumbnail}</span>
              <div>
                <div className="flex gap-2 mb-1">
                  <Badge variant="info">{course.provider}</Badge>
                  <Badge variant={course.difficulty === 'Advanced' ? 'danger' : course.difficulty === 'Intermediate' ? 'warning' : 'success'}>{course.difficulty}</Badge>
                </div>
                <h2 className="text-xl font-bold">{course.title}</h2>
                <p className="text-sm text-navy-200 mt-1">{course.courseCode} • {course.description}</p>
                <div className="flex items-center gap-4 mt-2 text-xs text-navy-300">
                  <span className="flex items-center gap-1"><Clock size={12} /> {course.duration}</span>
                  <span className="flex items-center gap-1"><Star size={12} className="text-amber-400" /> {course.rating}</span>
                  <span>{course.language}</span>
                  <span>{modules.length} modules</span>
                </div>
                {reasonCount > 0 && (
                  <div className="mt-2 px-2 py-1 bg-saffron-500/20 border border-saffron-500/30 rounded text-[11px] text-saffron-200">
                    Recommended — addresses {reasonCount} of your current skill gap{reasonCount > 1 ? 's' : ''}
                  </div>
                )}
              </div>
            </div>
            {!enrolled ? (
              <Button onClick={() => { enrollInCourse(course.id); setCourse({ ...course, enrolled: true }); }}>
                <BookOpen size={16} className="mr-1" /> Enroll Now
              </Button>
            ) : (
              <div className="w-40">
                <div className="flex justify-between text-xs mb-1"><span>Progress</span><span>{course.progress}%</span></div>
                <ProgressBar value={course.progress} max={100} size="sm" showLabel={false} />
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1">
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Course Modules</h3>
            <div className="space-y-2">
              {modules.map((m, i) => (
                <button
                  key={m.title}
                  onClick={() => startModule(m)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-colors cursor-pointer ${m.completed ? 'bg-green-50 border-green-200' : activeModule?.title === m.title ? 'bg-navy-50 border-navy-200' : 'bg-white border-navy-100 hover:bg-navy-50'}`}
                >
                  {m.completed ? <CheckCircle2 size={18} className="text-green-500 shrink-0" /> : <Play size={18} className="text-saffron-500 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-navy-800 truncate flex items-center gap-1">
                      {m.type === 'quiz' && <Bot size={12} className="text-purple-500" />}
                      {i + 1}. {m.title}
                    </p>
                    <p className="text-[11px] text-navy-400">{m.duration} • {m.type}</p>
                  </div>
                  <ChevronRight size={16} className="text-navy-300 shrink-0" />
                </button>
              ))}
            </div>
          </Card>

          <Card className="lg:col-span-2">
            {!activeModule ? (
              <>
                <h3 className="text-sm font-semibold text-navy-800 mb-3">About this course</h3>
                <p className="text-sm text-navy-600 mb-4">{course.description}</p>
                <h4 className="text-sm font-medium text-navy-700 mb-2">Skills covered</h4>
                <div className="flex flex-wrap gap-2">
                  {course.skillsCovered.map(s => (
                    <span key={s} className="px-3 py-1 bg-navy-50 text-navy-700 rounded-full text-xs">{s}</span>
                  ))}
                </div>
                <div className="mt-6 bg-saffron-50 border border-saffron-200 rounded-xl p-4 text-sm text-navy-700">
                  Select a module on the left to begin. Complete every module to boost the linked competencies on your profile (+1 level, up to max 5). Quiz modules include a brief micro-assessment.
                </div>
              </>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-base font-semibold text-navy-800">{activeModule.title}</h3>
                    <p className="text-xs text-navy-400">{activeModule.duration} • {activeModule.type} module</p>
                  </div>
                  <Badge variant={activeModule.completed ? 'success' : 'default'}>{activeModule.completed ? 'Completed' : 'In progress'}</Badge>
                </div>

                <p className="text-sm text-navy-600 bg-navy-50 rounded-lg p-4 mb-4">{activeModule.summary}</p>

                {activeModule.code && (
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Code2 size={14} className="text-saffron-500" />
                      <p className="text-xs font-medium text-navy-700 uppercase tracking-wide">Sandbox — run and edit this module's example code</p>
                    </div>
                    <CodeRunner initialCode={activeModule.code} engine={activeModule.sandbox === 'sql' ? 'sql' : 'python'} />
                  </div>
                )}

                {isQuiz && !submitted ? (
                  <div className="space-y-4">
                    {microQuestions.map((mq, qi) => (
                      <div key={qi} className="border border-navy-100 rounded-lg p-4">
                        <p className="text-sm font-medium text-navy-800 mb-2">{mq.q}</p>
                        <div className="grid gap-2">
                          {mq.o.map((opt, oi) => (
                            <button key={oi} onClick={() => handleAnswer(qi, oi)}
                              className={`text-left text-xs px-3 py-2 rounded-lg border transition-colors cursor-pointer ${answers[qi] === oi ? 'bg-saffron-500 border-saffron-500 text-white' : 'bg-white border-navy-100 text-navy-600 hover:bg-navy-50'}`}>
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                    <Button onClick={submitAssessment} disabled={answers.some(a => a === null)} className="w-full">
                      Submit Micro-Assessment
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className={`rounded-xl p-4 text-sm ${submitted ? (score >= 2 ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-amber-50 border border-amber-200 text-amber-700') : 'bg-navy-50 text-navy-600'}`}>
                      {submitted
                        ? <>You scored <b>{score}/3</b> on the micro-assessment{isQuiz ? `. Completing the assessment records the attempt on your transcript.` : ''}</>
                        : 'Review this module content. For quiz modules, answer the micro-assessment to complete it.'}
                    </div>
                    {bumpNotice && <div className="bg-saffron-50 border border-saffron-200 rounded-xl p-4 text-sm font-medium text-saffron-800">{bumpNotice}</div>}
                    {isQuiz && !submitted && answers.every(a => a !== null) && (
                      <Button onClick={submitAssessment} className="w-full">Submit Micro-Assessment</Button>
                    )}
                    {!isQuiz && !submitted && (
                      <Button onClick={markComplete} className="w-full">Mark Module Complete</Button>
                    )}
                    {activeModule.completed && (
                      <Button variant="secondary" onClick={() => startModule(modules[modules.indexOf(activeModule) + 1] || activeModule)} className="w-full">
                        Go to Next Module <ChevronRight size={16} />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}