import Header from '../components/layout/Header';
import { Card, Badge } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { mockOrgLearners } from '../services/appService';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, Legend } from 'recharts';
import { Users, BookOpen, Clock, TrendingUp, AlertTriangle, Search } from 'lucide-react';
import { useState } from 'react';

const deptScores = [
  { dept: 'National Sample Survey Office', avgCompetency: 2.7 },
  { dept: 'Census Division', avgCompetency: 2.6 },
  { dept: 'DGCIS', avgCompetency: 3.3 },
  { dept: 'NSSTA', avgCompetency: 3.9 },
];

const completionTrend = [
  { month: 'Jul', completions: 12 },
  { month: 'Aug', completions: 18 },
  { month: 'Sep', completions: 24 },
];

const topMissing = [
  { skill: 'Python', count: 7 },
  { skill: 'AI/ML', count: 8 },
  { skill: 'Data Viz', count: 5 },
  { skill: 'SQL', count: 4 },
  { skill: 'Leadership', count: 3 },
];

const pieColors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e'];

export default function AdminDashboardPage() {
  const { user } = useApp();
  const { t } = useI18n();
  const [searchTerm, setSearchTerm] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');

  const filtered = mockOrgLearners.filter(l => {
    if (deptFilter !== 'all' && l.department !== deptFilter) return false;
    if (searchTerm && !l.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const totalOfficials = mockOrgLearners.length;
  const activeCount = mockOrgLearners.filter(l => l.status === 'Active').length;
  const avgCompleted = mockOrgLearners.reduce((a, l) => a + l.completed, 0) / mockOrgLearners.length;
  const maxCompleted = Math.max(...mockOrgLearners.map(l => l.completed));
  const completionRate = Math.round((avgCompleted / maxCompleted) * 100);
  const highGapCount = mockOrgLearners.filter(l => l.gaps >= 4).length;

  const stats = [
    { icon: Users, label: t('Total Officials', 'कुल अधिकारी'), value: totalOfficials, color: 'text-navy-600', bg: 'bg-navy-50' },
    { icon: BookOpen, label: t('Active Learners', 'सक्रिय शिक्षार्थी'), value: activeCount, color: 'text-green-600', bg: 'bg-green-50' },
    { icon: TrendingUp, label: t('Completion Rate', 'पूर्णता दर'), value: `${completionRate}%`, color: 'text-saffron-600', bg: 'bg-saffron-50' },
    { icon: Clock, label: t('Avg Courses Completed', 'औसत पूर्ण कोर्स'), value: avgCompleted.toFixed(1), color: 'text-blue-600', bg: 'bg-blue-50' },
    { icon: AlertTriangle, label: t('High-Priority Gaps', 'उच्च-प्राथमिकता गैप'), value: highGapCount, color: 'text-red-600', bg: 'bg-red-50' },
  ];

  const gapDistribution = [
    { name: t('High', 'उच्च'), value: mockOrgLearners.filter(l => l.gaps >= 4).length },
    { name: t('Medium', 'मध्यम'), value: mockOrgLearners.filter(l => l.gaps === 3).length },
    { name: t('Low', 'निम्न'), value: mockOrgLearners.filter(l => l.gaps === 2).length },
    { name: t('No Gap', 'कोई गैप नहीं'), value: mockOrgLearners.filter(l => l.gaps <= 1).length },
  ];

  return (
    <div>
      <Header title={t('Administrator Dashboard', 'प्रशासक डैशबोर्ड')} />
      <div className="p-6 space-y-6">
        <div className="bg-gradient-to-r from-navy-800 to-navy-900 rounded-2xl p-6 text-white">
          <h2 className="text-xl font-bold mb-1">{t('Organization Overview', 'संगठन अवलोकन')}</h2>
          <p className="text-navy-200 text-sm">{t('Skill intelligence across', 'कौशल बुद्धिमत्ता —')} {user?.department || 'National Sample Survey Office'} — {totalOfficials} {t('officials tracked', 'अधिकारियों पर नज़र रखी जा रही है')}</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {stats.map((s, i) => (
            <Card key={i} className={s.bg}>
              <s.icon size={20} className={`${s.color} mb-2`} />
              <p className="text-xl font-bold text-navy-800">{s.value}</p>
              <p className="text-xs text-navy-400 mt-0.5">{s.label}</p>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">{t('Skill Gap Distribution', 'स्किल गैप वितरण')}</h3>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={gapDistribution} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {gapDistribution.map((_, i) => <Cell key={i} fill={pieColors[i]} />)}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">{t('Department-wise Competency Scores', 'विभागवार दक्षता अंक')}</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={deptScores}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="dept" tick={{ fontSize: 9 }} interval={0} />
                <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="avgCompetency" fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">{t('Course Completion Trends', 'कोर्स पूर्णता की प्रवृत्तियाँ')}</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={completionTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="completions" stroke="#f97316" strokeWidth={2} dot={{ fill: '#f97316' }} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">{t('Top 5 Missing Skills', 'शीर्ष 5 अनुपस्थित कौशल')}</h3>
            <div className="space-y-3">
              {topMissing.map((s, i) => (
                <div key={s.skill} className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-navy-100 flex items-center justify-center text-xs font-bold text-navy-600">{i + 1}</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium text-navy-700">{s.skill}</p>
                      <span className="text-xs text-navy-400">{s.count} {t('officials', 'अधिकारी')}</span>
                    </div>
                    <div className="w-full h-2 bg-navy-100 rounded-full">
                      <div className="h-2 bg-saffron-400 rounded-full" style={{ width: `${(s.count / 8) * 100}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-navy-800">{t('Learner Directory', 'शिक्षार्थी निर्देशिका')}</h3>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder={t('Search learners...', 'शिक्षार्थी खोजें...')}
                  className="pl-8 pr-3 py-1.5 border border-navy-200 rounded-lg text-xs w-40"
                />
              </div>
              <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)} className="px-3 py-1.5 border border-navy-200 rounded-lg text-xs bg-white">
                <option value="all">{t('All Departments', 'सभी विभाग')}</option>
                <option value="National Sample Survey Office">National Sample Survey Office</option>
                <option value="Census Division">Census Division</option>
                <option value="DGCIS">DGCIS</option>
                <option value="NSSTA">NSSTA</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-navy-100">
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">{t('Name', 'नाम')}</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">{t('Department', 'विभाग')}</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">{t('Role', 'भूमिका')}</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">{t('Competency', 'दक्षता')}</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">{t('High Gaps', 'उच्च गैप')}</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">{t('Completed', 'पूर्ण')}</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">{t('Status', 'स्थिति')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(l => (
                  <tr key={l.name} className="border-b border-navy-50 hover:bg-navy-50">
                    <td className="py-2 px-3 font-medium text-navy-800">{l.name}</td>
                    <td className="py-2 px-3 text-navy-500">{l.department}</td>
                    <td className="py-2 px-3 text-navy-500">{l.role}</td>
                    <td className="text-center py-2 px-3">
                      <span className="px-2 py-0.5 rounded bg-navy-100 text-navy-700 text-xs font-medium">{l.competency}/5</span>
                    </td>
                    <td className="text-center py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${l.gaps >= 4 ? 'bg-red-100 text-red-700' : l.gaps >= 2 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
                        {l.gaps}
                      </span>
                    </td>
                    <td className="text-center py-2 px-3 text-navy-600">{l.completed}</td>
                    <td className="text-center py-2 px-3">
                      <Badge variant={l.status === 'Active' ? 'success' : 'default'}>{l.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
