import Header from '../components/layout/Header';
import { Card, Badge } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { mockOrgLearners } from '../services/appService';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, Legend } from 'recharts';
import { Users, BookOpen, Clock, TrendingUp, AlertTriangle, Search } from 'lucide-react';
import { useState } from 'react';

const deptScores = [
  { dept: 'NSSO', avgCompetency: 2.7 },
  { dept: 'Census', avgCompetency: 2.6 },
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
  const [searchTerm, setSearchTerm] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');

  const filtered = mockOrgLearners.filter(l => {
    if (deptFilter !== 'all' && l.department !== deptFilter) return false;
    if (searchTerm && !l.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const stats = [
    { icon: Users, label: 'Total Officials', value: 156, color: 'text-navy-600', bg: 'bg-navy-50' },
    { icon: BookOpen, label: 'Active Learners', value: 89, color: 'text-green-600', bg: 'bg-green-50' },
    { icon: TrendingUp, label: 'Completion Rate', value: '68%', color: 'text-saffron-600', bg: 'bg-saffron-50' },
    { icon: Clock, label: 'Total Learning Hours', value: '1,240', color: 'text-blue-600', bg: 'bg-blue-50' },
    { icon: AlertTriangle, label: 'High-Priority Gaps', value: 34, color: 'text-red-600', bg: 'bg-red-50' },
  ];

  const gapDistribution = [
    { name: 'High', value: 34 },
    { name: 'Medium', value: 48 },
    { name: 'Low', value: 62 },
    { name: 'No Gap', value: 124 },
  ];

  return (
    <div>
      <Header title="Administrator Dashboard" />
      <div className="p-6 space-y-6">
        <div className="bg-gradient-to-r from-navy-800 to-navy-900 rounded-2xl p-6 text-white">
          <h2 className="text-xl font-bold mb-1">Organization Overview</h2>
          <p className="text-navy-200 text-sm">Skill intelligence across {user?.department || 'NSSO'} — 156 officials tracked</p>
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
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Skill Gap Distribution</h3>
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
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Department-wise Competency Scores</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={deptScores}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="avgCompetency" fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Course Completion Trends</h3>
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
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Top 5 Missing Skills</h3>
            <div className="space-y-3">
              {topMissing.map((s, i) => (
                <div key={s.skill} className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-navy-100 flex items-center justify-center text-xs font-bold text-navy-600">{i + 1}</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium text-navy-700">{s.skill}</p>
                      <span className="text-xs text-navy-400">{s.count} officials</span>
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
            <h3 className="text-sm font-semibold text-navy-800">Learner Directory</h3>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder="Search learners..."
                  className="pl-8 pr-3 py-1.5 border border-navy-200 rounded-lg text-xs w-40"
                />
              </div>
              <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)} className="px-3 py-1.5 border border-navy-200 rounded-lg text-xs bg-white">
                <option value="all">All Departments</option>
                <option value="NSSO">NSSO</option>
                <option value="Census Division">Census</option>
                <option value="DGCIS">DGCIS</option>
                <option value="NSSTA">NSSTA</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-navy-100">
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">Name</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">Department</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-navy-500">Role</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">Competency</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">High Gaps</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">Completed</th>
                  <th className="text-center py-2 px-3 text-xs font-semibold text-navy-500">Status</th>
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
