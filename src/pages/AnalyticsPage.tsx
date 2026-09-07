import { useEffect } from 'react';
import Header from '../components/layout/Header';
import { Card, Badge } from '../components/ui/UIComponents';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, ComposedChart } from 'recharts';
import { useApp } from '../store/AppContext';
import { TrendingUp, Sparkles } from 'lucide-react';

const trainingEffectiveness = [
  { course: 'Python', before: 1.5, after: 3.2 },
  { course: 'Data Viz', before: 2.0, after: 3.5 },
  { course: 'SQL', before: 2.0, after: 3.0 },
  { course: 'Survey', before: 3.0, after: 3.8 },
];

const engagementData = [
  { month: 'Apr', hours: 120, completions: 8 },
  { month: 'May', hours: 145, completions: 11 },
  { month: 'Jun', hours: 160, completions: 15 },
  { month: 'Jul', hours: 180, completions: 18 },
  { month: 'Aug', hours: 210, completions: 22 },
  { month: 'Sep', hours: 195, completions: 24 },
];

const emergingSkills = [
  { skill: 'AI/ML in Statistics', demand: 85 },
  { skill: 'Cloud Data Platforms', demand: 72 },
  { skill: 'Real-time Analytics', demand: 68 },
  { skill: 'Geospatial Analysis', demand: 55 },
];

const pieColors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e'];

export default function AnalyticsPage() {
  const { forecast, loadForecast } = useApp();

  useEffect(() => {
    loadForecast();
  }, [loadForecast]);

  const forecastChart = forecast ? [
    ...forecast.readinessTrend.map(p => ({ label: p.label, readiness: p.value })),
  ] : [];

  const future = forecast?.future || [];
  const combined = [
    ...engagementData.map(e => ({ label: e.month, completions: e.completions })),
    ...future.map(f => ({ label: f.label, completions: Math.round(f.completions) })),
  ];

  return (
    <div>
      <Header title="Analytics" />
      <div className="p-6 space-y-6">
        {/* Predictive Analytics panel */}
        {forecast && (
          <Card className="border-saffron-200 bg-gradient-to-br from-white to-saffron-50">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp size={18} className="text-saffron-600" />
                <h3 className="text-sm font-semibold text-navy-800">Predictive Analytics — Skill Demand & Readiness Forecast</h3>
                <Badge variant="warning">Linear regression</Badge>
              </div>
              <Badge variant="success">Next 3 quarters</Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={combined}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="completions" fill="#f97316" name="Course Completions" radius={[4, 4, 0, 0]} />
                  <Line type="monotone" dataKey="completions" stroke="#0d1320" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>

              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={forecastChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="x" />
                  <Tooltip />
                  <Line type="monotone" dataKey="readiness" stroke="#0d1320" strokeWidth={2} name="Avg readiness level" dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-4 bg-white border border-saffron-200 rounded-xl p-4">
              <p className="text-xs font-semibold text-saffron-700 mb-2 flex items-center gap-1"><Sparkles size={12} /> Model insights</p>
              <ul className="space-y-1">
                {forecast.insights.map((ins, i) => (
                  <li key={i} className="text-xs text-navy-600">• {ins}</li>
                ))}
              </ul>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Training Effectiveness (Before vs After)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={trainingEffectiveness}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="course" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="before" fill="#94a3b8" name="Before" radius={[4, 4, 0, 0]} />
                <Bar dataKey="after" fill="#f97316" name="After" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-navy-800 mb-4">Learner Engagement Trends</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={engagementData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="hours" stroke="#3b82f6" strokeWidth={2} name="Hours" />
                <Line type="monotone" dataKey="completions" stroke="#22c55e" strokeWidth={2} name="Completions" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <Card>
          <h3 className="text-sm font-semibold text-navy-800 mb-4">Emerging Skill Requirements</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {emergingSkills.map((s, i) => (
              <div key={s.skill} className="p-4 bg-gradient-to-br from-navy-50 to-navy-100 rounded-lg">
                <p className="text-sm font-medium text-navy-700 mb-2">{s.skill}</p>
                <div className="w-full h-3 bg-navy-200 rounded-full">
                  <div className="h-3 bg-gradient-to-r from-saffron-400 to-saffron-600 rounded-full transition-all" style={{ width: `${s.demand}%` }} />
                </div>
                <p className="text-xs text-navy-400 mt-1">{s.demand}% demand growth</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-navy-800 mb-4">Competency Distribution by Department</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={[
                  { name: 'NSSO', value: 45 },
                  { name: 'Census', value: 30 },
                  { name: 'DGCIS', value: 25 },
                  { name: 'NSSTA', value: 20 },
                ]}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {[45, 30, 25, 20].map((_, i) => <Cell key={i} fill={pieColors[i]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}