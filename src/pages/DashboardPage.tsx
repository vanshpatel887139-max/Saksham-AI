import Header from '../components/layout/Header';
import { Card, Badge, ProgressBar, Button } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts';
import { BookOpen, Clock, Brain, Target, TrendingUp, Flame, Award, ChevronRight, Bell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useStagger } from '../hooks/useStagger';
import { competencies } from '../data/mockData';

export default function DashboardPage() {
  const { animate, staggerStyle } = useStagger();
  const { user, skillGaps, enrolledCourses, quizzes, activities, recommendedCourses } = useApp();
  const navigate = useNavigate();

  if (!user) return null;

  const overallScore = (user.competencies.reduce((a, c) => a + c.level, 0) / user.competencies.length).toFixed(1);
  const highGaps = skillGaps.filter(g => g.priority === 'High').length;
  const completedCourses = enrolledCourses.filter(c => c.progress >= 100).length;
  const avgQuiz = quizzes.length > 0 ? (quizzes.reduce((a, q) => a + (q.score || 0) / q.totalQuestions, 0) / quizzes.length * 100).toFixed(0) : '—';

  // Aggregate radar by category (4 categories) so 32 competencies render cleanly
  const radarData = ['Statistical', 'Technical', 'Digital Governance', 'Behavioural'].map(cat => {
    const ids = competencies.filter(c => c.category === cat).map(c => c.id);
    const vals = user.competencies.filter(c => ids.includes(c.competencyId));
    const avg = vals.length ? vals.reduce((a, c) => a + c.level, 0) / vals.length : 0;
    return { competency: cat === 'Digital Governance' ? 'Digital Gov' : cat, current: Number(avg.toFixed(2)) };
  });

  const statCards = [
    { icon: Target, label: 'Overall Competency', value: `${overallScore}/5`, color: 'text-navy-600', bg: 'bg-navy-50' },
    { icon: BookOpen, label: 'Courses In Progress', value: enrolledCourses.length, color: 'text-saffron-600', bg: 'bg-saffron-50' },
    { icon: Clock, label: 'Learning Hours', value: '24', color: 'text-blue-600', bg: 'bg-blue-50' },
    { icon: Brain, label: 'Quiz Average', value: avgQuiz + (avgQuiz !== '—' ? '%' : ''), color: 'text-purple-600', bg: 'bg-purple-50' },
    { icon: Flame, label: 'Learning Streak', value: '7 days', color: 'text-red-600', bg: 'bg-red-50' },
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

            <div className="mt-4 bg-white/10 rounded-xl p-3 flex items-center gap-2">
              <Bell size={16} className="text-saffron-400" />
              <p className="text-sm text-navy-100">Your Data Visualization competency improved from Level 2 to Level 3 after completing the recommended course and assessment.</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {statCards.map((s, i) => (
            <Card key={i} className={`${s.bg} stagger-fade-up`} style={staggerStyle(1 + i, animate)}>
              <s.icon size={20} className={`${s.color} mb-2`} />
              <p className="text-xl font-bold text-navy-800">{s.value}</p>
              <p className="text-xs text-navy-400 mt-0.5">{s.label}</p>
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
            {recommendedCourses.length > 0 ? (
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
            <div className="space-y-3">
              {activities.slice(0, 5).map(a => (
                <div key={a.id} className="flex items-start gap-3">
                  <span className="text-sm">{a.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-navy-700">{a.action}</p>
                    <p className="text-[10px] text-navy-400 truncate">{a.detail}</p>
                    <p className="text-[10px] text-navy-300">{a.date}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card className="stagger-fade-up" style={staggerStyle(10, animate)}>
          <h3 className="text-sm font-semibold text-navy-800 mb-4">Enrolled Courses Progress</h3>
          <div className="space-y-4">
            {enrolledCourses.length > 0 ? enrolledCourses.map(c => (
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
            )) : (
              <p className="text-sm text-navy-400 text-center py-4">No courses enrolled yet. Visit the Course Catalogue to get started.</p>
            )}
          </div>
        </Card>

        <Card className="stagger-fade-up" style={staggerStyle(11, animate)}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-navy-800">Learning Pathway</h3>
            <Button variant="ghost" size="sm" onClick={() => navigate('/learning-path')}>View Full Path <ChevronRight size={14} /></Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { stage: 'Foundation', progress: 33, color: 'bg-green-500' },
              { stage: 'Role-Specific Skills', progress: 0, color: 'bg-saffron-500' },
              { stage: 'Advanced & Future', progress: 0, color: 'bg-navy-600' },
            ].map(s => (
              <div key={s.stage} className="p-4 bg-navy-50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-2 h-2 rounded-full ${s.color}`} />
                  <p className="text-sm font-medium text-navy-700">{s.stage}</p>
                </div>
                <ProgressBar value={s.progress} max={100} size="sm" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}