import Header from '../components/layout/Header';
import { Card, Badge, ProgressBar, Button } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts';
import { BookOpen, Clock, Brain, Target, TrendingUp, Flame, ChevronRight, Bell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useStagger } from '../hooks/useStagger';
import { competencies } from '../data/mockData';
import { mockActivities } from '../services/appService';

export default function DashboardPage() {
  const { animate, staggerStyle } = useStagger();
  const { user, skillGaps, enrolledCourses, quizzes, activities, notifications, recommendedCourses, dashboard, dataLoading } = useApp();
  const navigate = useNavigate();

  if (!user) return null;

  const overallScore = (user.competencies.reduce((a, c) => a + c.level, 0) / user.competencies.length).toFixed(1);
  const highGaps = skillGaps.filter(g => g.priority === 'High').length;
  const completedCourses = enrolledCourses.filter(c => c.progress >= 100).length;

  // Prefer the server's figures. The local `quizzes` array only holds attempts
  // made in this browser session, so after a refresh it is empty and the
  // average would collapse to a dash even though the learner has a history.
  const quizAverage = dashboard?.quizzes.average ?? (
    quizzes.length > 0
      ? (quizzes.reduce((a, q) => a + (q.score || 0) / q.totalQuestions, 0) / quizzes.length * 100).toFixed(0)
      : null
  );

  // `null` renders as a dash, `0` renders as "0". Those are different claims:
  // a dash means "no data yet", a zero means "measured, and it is nothing".
  // The old code collapsed both to a dash, which is why the dashboard looked
  // empty for a learner who genuinely had completed nothing.
  const learningHours = dashboard ? `${dashboard.learningHours}` : '—';
  const quizAverageLabel = quizAverage === null ? '—' : `${quizAverage}%`;
  const hoursSubtitle = dashboard && dashboard.activeDayCount > 0
    ? `Across ${dashboard.activeDayCount} active day${dashboard.activeDayCount === 1 ? '' : 's'}`
    : 'No activity recorded yet';

  const streakLabel = dashboard
    ? dashboard.streak > 0
      ? `${dashboard.streak} day${dashboard.streak === 1 ? '' : 's'}`
      : '0 days'
    : '—';

  // Distinguishes "you have a 0-day streak" from "your last activity was long
  // ago", which look identical in the number alone. The second one is what a
  // reviewer sees on seeded data, and it is the useful thing to say.
  const streakSubtitle = !dashboard
    ? '—'
    : dashboard.streak > 0
      ? 'Consecutive active days'
      : dashboard.streakAsOf
        ? `Last active ${dashboard.streakAsOf}`
        : 'No activity recorded yet';

  // An empty feed is a worse failure than a slightly stale one, but showing
  // seeded rows as if they were the learner's own would be a lie. Only fall
  // back to the bundled sample when the server is genuinely unreachable.
  const activityFeed = activities.length > 0 ? activities : (dashboard ? [] : mockActivities);
  // While the sign-in burst is still in flight the arrays are legitimately
  // empty — that is "waiting", not "no data", so the feed shows a skeleton
  // rather than telling someone they have no activity a second before their
  // activity arrives.
  const feedLoading = dataLoading && activities.length === 0;
  const latestNotification = notifications.find(n => !n.read) ?? notifications[0] ?? null;

  // The three bar colours are presentation, so they stay in the frontend; the
  // percentages and the stage names come from the server. Falling back to
  // zeros here (rather than the old 33/0/0) keeps the card honest about
  // having no measurement instead of implying progress.
  const PATHWAY_COLORS = ['bg-green-500', 'bg-saffron-500', 'bg-navy-600'];
  const pathwayStages = (dashboard?.pathway ?? []).map((s, i) => ({
    stage: s.stage,
    progress: s.progress,
    met: s.met,
    total: s.total,
    color: PATHWAY_COLORS[i % PATHWAY_COLORS.length],
  }));

  // Aggregate radar by category (4 categories) so 32 competencies render cleanly
  const radarData = ['Statistical', 'Technical', 'Digital Governance', 'Behavioural'].map(cat => {
    const ids = competencies.filter(c => c.category === cat).map(c => c.id);
    const vals = user.competencies.filter(c => ids.includes(c.competencyId));
    const avg = vals.length ? vals.reduce((a, c) => a + c.level, 0) / vals.length : 0;
    return { competency: cat === 'Digital Governance' ? 'Digital Gov' : cat, current: Number(avg.toFixed(2)) };
  });

  const statCards = [
    { icon: Target, label: 'Overall Competency', value: `${overallScore}/5`, sub: `${user.competencies.length} competencies`, color: 'text-navy-600', bg: 'bg-navy-50' },
    { icon: BookOpen, label: 'Courses In Progress', value: enrolledCourses.length, sub: `${completedCourses} completed`, color: 'text-saffron-600', bg: 'bg-saffron-50' },
    { icon: Clock, label: 'Learning Hours', value: learningHours, sub: hoursSubtitle, color: 'text-blue-600', bg: 'bg-blue-50' },
    { icon: Brain, label: 'Quiz Average', value: quizAverageLabel, sub: quizAverage === null ? 'No quizzes taken yet' : `${dashboard?.quizzes.count ?? quizzes.length} attempt${(dashboard?.quizzes.count ?? quizzes.length) === 1 ? '' : 's'}`, color: 'text-purple-600', bg: 'bg-purple-50' },
    { icon: Flame, label: 'Learning Streak', value: streakLabel, sub: streakSubtitle, color: 'text-red-600', bg: 'bg-red-50' },
    { icon: TrendingUp, label: 'Skill Gaps', value: highGaps, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  return (
    <div>
      <Header title="Dashboard" />
      <div className="p-6 space-y-6">
        <div className="stagger-fade-up" style={staggerStyle(0, animate)}>
          <div className="bg-gradient-to-r from-navy-800 to-navy-900 rounded-2xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold mb-1">Welcome back, {user.name.split(' ')[0]}!</h2>
                <p className="text-navy-200 text-sm">Your personalized learning dashboard for Official Statistics</p>
              </div>
              <div className="w-12 h-12 rounded-full bg-saffron-500 flex items-center justify-center font-bold text-lg">
                {user.name.split(' ').map(n => n[0]).join('')}
              </div>
            </div>

            {/* Was a hardcoded sentence that happened to be a copy of
                notification n1, so it showed the same message to every learner
                regardless of what they had actually done. */}
            {latestNotification && (
              <div className="mt-4 bg-white/10 rounded-xl p-3 flex items-start gap-2">
                <Bell size={16} className="text-saffron-400 mt-0.5 shrink-0" />
                <p className="text-sm text-navy-100">{latestNotification.message}</p>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {statCards.map((s, i) => (
            <Card key={i} className={`${s.bg} stagger-fade-up`} style={staggerStyle(1 + i, animate)}>
              <s.icon size={20} className={`${s.color} mb-2`} />
              <p className="text-xl font-bold text-navy-800">{s.value}</p>
              <p className="text-xs text-navy-400 mt-0.5">{s.label}</p>
              {/* Context under the label, so a low number reads as a fact
                  rather than a failure — "0h across 5 active days" and "24h"
                  carry very different weight. */}
              <p className="text-[10px] text-navy-300 mt-0.5">{s.sub}</p>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1 h-full stagger-fade-up" style={staggerStyle(7, animate)}>
            <h3 className="text-sm font-semibold text-navy-800 mb-3">Competency Overview</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#d9e1ed" />
                <PolarAngleAxis dataKey="competency" tick={{ fontSize: 9, fill: '#344f80' }} />
                <PolarRadiusAxis angle={30} domain={[0, 5]} tick={false} />
                <Radar dataKey="current" stroke="#f97316" fill="#f97316" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="lg:col-span-1 h-full stagger-fade-up" style={staggerStyle(8, animate)}>
            <h3 className="text-sm font-semibold text-navy-800 mb-3">Recommended Next Course</h3>
            {dataLoading ? (
              <div className="space-y-3 animate-pulse">
                {[0, 1].map(i => (
                  <div key={i} className="p-3 bg-navy-50 rounded-lg space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-navy-100 rounded" />
                      <div className="h-4 w-16 bg-navy-100 rounded" />
                    </div>
                    <div className="h-3.5 w-3/4 bg-navy-100 rounded" />
                    <div className="h-3 w-1/2 bg-navy-100 rounded" />
                  </div>
                ))}
              </div>
            ) : recommendedCourses.length > 0 ? (
              <div className="space-y-3">
                {recommendedCourses.slice(0, 2).map(c => (
                  <div key={c.id} className="p-3 bg-navy-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{c.thumbnail}</span>
                      <Badge variant="info">{c.provider}</Badge>
                    </div>
                    <p className="text-sm font-medium text-navy-800">{c.title}</p>
                    <p className="text-xs text-navy-400 mt-1">{c.duration} • {c.difficulty}</p>
                    <Button size="sm" className="mt-2 w-full" onClick={() => navigate(`/courses/${c.id}`)}>Enroll Now</Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-navy-400">Complete your assessment to get recommendations</p>
            )}
          </Card>

          <Card className="lg:col-span-1 h-full stagger-fade-up" style={staggerStyle(9, animate)}>
            <h3 className="text-sm font-semibold text-navy-800 mb-3">Recent Activity</h3>
            {feedLoading ? (
              <div className="space-y-3 animate-pulse">
                {[0, 1, 2].map(i => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-5 h-5 bg-navy-100 rounded" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 w-2/3 bg-navy-100 rounded" />
                      <div className="h-2.5 w-1/3 bg-navy-100 rounded" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activityFeed.length === 0 ? (
                <p className="text-sm text-navy-400">No activity yet. Enroll in a course or take an assessment to get started.</p>
              ) : activityFeed.slice(0, 5).map(a => (
                <div key={a.id} className="flex items-start gap-3">
                  <span className="text-sm">{a.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-navy-700">{a.action}</p>
                    <p className="text-[10px] text-navy-400 truncate">{a.detail}</p>
                    <p className="text-[10px] text-navy-300">{a.date}</p>
                  </div>
                </div>
              ))}
          </Card>
        </div>

        <Card className="stagger-fade-up" style={staggerStyle(10, animate)}>
          <h3 className="text-sm font-semibold text-navy-800 mb-4">Enrolled Courses Progress</h3>
          {dataLoading ? (
            <div className="space-y-4 animate-pulse">
              {[0, 1, 2].map(i => (
                <div key={i} className="flex items-center gap-4">
                  <div className="w-8 h-8 bg-navy-100 rounded" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div className="h-3.5 w-1/2 bg-navy-100 rounded" />
                      <div className="h-3 w-8 bg-navy-100 rounded" />
                    </div>
                    <div className="h-2 w-full bg-navy-100 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : enrolledCourses.length > 0 ? (
            <div className="space-y-4">
              {enrolledCourses.map(c => (
                <div key={c.id} className="flex items-center gap-4">
                  <span className="text-2xl">{c.thumbnail}</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium text-navy-800">{c.title}</p>
                      <span className="text-xs text-navy-500">{c.progress}%</span>
                    </div>
                    <ProgressBar value={c.progress} max={100} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-navy-400 text-center py-4">No courses enrolled yet. Visit the Course Catalogue to get started.</p>
          )}
        </Card>

        <Card className="stagger-fade-up" style={staggerStyle(11, animate)}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-navy-800">Learning Pathway</h3>
            <Button variant="ghost" size="sm" onClick={() => navigate('/learning-path')}>View Full Path <ChevronRight size={14} /></Button>
          </div>
          {/* Was a hardcoded 33/0/0. Now each bar is the share of that band's
              competencies already meeting the target role's required level. */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {pathwayStages.length === 0 ? (
              <p className="text-sm text-navy-400">
                {dashboard ? 'Set a target role to see your pathway progress.' : 'Loading your pathway…'}
              </p>
            ) : pathwayStages.map(s => (
              <div key={s.stage} className="p-4 bg-navy-50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-2 h-2 rounded-full ${s.color}`} />
                  <p className="text-sm font-medium text-navy-700">{s.stage}</p>
                </div>
                <ProgressBar value={s.progress} max={100} size="sm" />
                <p className="text-xs text-navy-400 mt-1.5">
                  {s.total > 0 ? `${s.met}/${s.total} competencies` : 'No competencies at this level for your target role'}
                </p>
              </div>
            ))}
          </div>
          {dashboard?.targetRole && (
            <p className="text-xs text-navy-400 mt-3">Measured against the requirements for {dashboard.targetRole}.</p>
          )}
        </Card>
      </div>
    </div>
  );
}