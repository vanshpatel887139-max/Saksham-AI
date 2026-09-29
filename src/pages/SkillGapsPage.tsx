import Header from '../components/layout/Header';
import { Card, Badge, Tooltip } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Cell } from 'recharts';
import { AlertTriangle, Info } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';

const priorityColors: Record<string, string> = {
  'High': 'bg-red-100 text-red-700 border-red-200',
  'Medium': 'bg-amber-100 text-amber-700 border-amber-200',
  'Low': 'bg-blue-100 text-blue-700 border-blue-200',
  'No Gap': 'bg-green-100 text-green-700 border-green-200',
};

const barColors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e'];

export default function SkillGapsPage() {
  const { skillGaps, selectedRole, user } = useApp();
  const { animate, staggerStyle } = useStagger();
  const { t } = useI18n();

  const radarData = ['Statistical', 'Technical', 'Digital Governance', 'Behavioural'].map(cat => {
    const subset = skillGaps.filter(g => g.category === cat);
    if (subset.length === 0) return null;
    return {
      competency: cat === 'Digital Governance' ? t('Digital Gov', 'डिजिटल शासन') : t(cat, cat === 'Statistical' ? 'सांख्यिकी' : cat === 'Technical' ? 'तकनीकी' : 'व्यवहारिक'),
      current: Number((subset.reduce((a, g) => a + g.currentLevel, 0) / subset.length).toFixed(2)),
      required: Number((subset.reduce((a, g) => a + g.requiredLevel, 0) / subset.length).toFixed(2)),
    };
  }).filter(Boolean) as { competency: string; current: number; required: number }[];

  const top3Gaps = skillGaps.filter(g => g.priority === 'High' || g.priority === 'Medium').slice(0, 3);
  const gapBarData = skillGaps.filter(g => g.gap > 0).map(g => ({
    name: g.competencyName,
    gap: g.gap,
    priority: g.priority,
  }));

  const statCards = [
    { label: t('High Priority Gaps', 'उच्च प्राथमिकता अंतर'), value: skillGaps.filter(g => g.priority === 'High').length, color: 'text-red-600', bg: 'bg-red-50' },
    { label: t('Medium Priority Gaps', 'मध्यम प्राथमिकता अंतर'), value: skillGaps.filter(g => g.priority === 'Medium').length, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: t('Low Priority Gaps', 'निम्न प्राथमिकता अंतर'), value: skillGaps.filter(g => g.priority === 'Low').length, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: t('Overall Competency', 'समग्र दक्षता'), value: `${(user?.competencies.reduce((a, c) => a + c.level, 0) || 0) / (user?.competencies.length || 1)}/5`, color: 'text-navy-600', bg: 'bg-navy-50' },
  ];

  return (
    <div>
      <Header title={t('Skill Gap Analysis', 'कौशल अंतर विश्लेषण')} />
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-2 stagger-fade-up" style={staggerStyle(0, animate)}>
          <Badge variant="info">{t('Target Role:', 'लक्ष्य भूमिका:')} {selectedRole}</Badge>
          <span className="text-xs text-navy-400">{t('Analysis based on your competency assessment vs. role requirements', 'यह विश्लेषण आपके दक्षता मूल्यांकन एवं भूमिका आवश्यकताओं के आधार पर किया गया है')}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {statCards.map((s, i) => (
            <Card key={i} className={`${s.bg} stagger-fade-up`} style={staggerStyle(1 + i, animate)}>
              <p className="text-xs text-navy-400 mb-1">{s.label}</p>
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            </Card>
          ))}
        </div>

        {top3Gaps.length > 0 && (
          <Card className="stagger-fade-up" style={staggerStyle(5, animate)}>
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle size={18} className="text-red-500" />
              <h2 className="text-base font-semibold text-navy-800">{t('Top Skill Gaps to Address', 'संबोधित करने हेतु प्रमुख कौशल अंतर')}</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {top3Gaps.map((gap, i) => (
                <div key={gap.competencyId} className={`p-4 rounded-lg border ${priorityColors[gap.priority]}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold">#{i + 1}</span>
                    <Badge variant={gap.priority === 'High' ? 'danger' : gap.priority === 'Medium' ? 'warning' : 'info'}>{gap.priority}</Badge>
                  </div>
                  <h3 className="font-semibold text-navy-800 mb-1">{gap.competencyName}</h3>
                  <p className="text-xs text-navy-500 mb-2">{gap.category}</p>
                  <div className="flex items-center gap-2 text-xs">
                    <span>{t('Current: Lv.', 'वर्तमान: स्तर')} {gap.currentLevel}</span>
                    <span className="text-navy-300">→</span>
                    <span>{t('Required: Lv.', 'आवश्यक: स्तर')} {gap.requiredLevel}</span>
                    <span className="font-bold text-red-600">{t('Gap:', 'अंतर:')} {gap.gap}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="stagger-fade-up" style={staggerStyle(6, animate)}>
            <h2 className="text-base font-semibold text-navy-800 mb-4">{t('Competency Radar', 'दक्षता रेडार')}</h2>
            <ResponsiveContainer width="100%" height={350}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#d9e1ed" />
                <PolarAngleAxis dataKey="competency" tick={{ fontSize: 11, fill: '#344f80' }} />
                <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fontSize: 10 }} />
                <Radar name={t('Current', 'वर्तमान')} dataKey="current" stroke="#f97316" fill="#f97316" fillOpacity={0.3} />
                <Radar name={t('Required', 'आवश्यक')} dataKey="required" stroke="#0d1320" fill="#0d1320" fillOpacity={0.1} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="stagger-fade-up" style={staggerStyle(7, animate)}>
            <h2 className="text-base font-semibold text-navy-800 mb-4">{t('Gap Distribution', 'अंतर वितरण')}</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={gapBarData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#344f80' }} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 5]} />
                <RTooltip />
                <Bar dataKey="gap" radius={[4, 4, 0, 0]}>
                  {gapBarData.map((entry, index) => (
                    <Cell key={index} fill={barColors[index % barColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <Card className="stagger-fade-up" style={staggerStyle(8, animate)}>
          <h2 className="text-base font-semibold text-navy-800 mb-4">{t('All Competency Gaps', 'सभी दक्षता अंतर')}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-navy-100">
                  <th className="text-left py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Competency', 'दक्षता')}</th>
                  <th className="text-center py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Category', 'श्रेणी')}</th>
                  <th className="text-center py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Current', 'वर्तमान')}</th>
                  <th className="text-center py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Required', 'आवश्यक')}</th>
                  <th className="text-center py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Gap', 'अंतर')}</th>
                  <th className="text-center py-3 px-4 text-xs font-semibold text-navy-500 uppercase">{t('Priority', 'प्राथमिकता')}</th>
                </tr>
              </thead>
              <tbody>
                {skillGaps.map(g => (
                  <tr key={g.competencyId} className="border-b border-navy-50 hover:bg-navy-50">
                    <td className="py-3 px-4 font-medium text-navy-800">
                      {g.competencyName}
                      <Tooltip text={`${t('Gap:', 'अंतर:')} ${g.gap} ${g.gap !== 1 ? t('levels', 'स्तर') : t('level', 'स्तर')}`}>
                        <Info size={12} className="inline ml-1 text-navy-300" />
                      </Tooltip>
                    </td>
                    <td className="text-center py-3 px-4 text-navy-500">{g.category}</td>
                    <td className="text-center py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-saffron-100 text-saffron-700 text-xs font-medium">{t('Lv.', 'स्तर')} {g.currentLevel}</span>
                    </td>
                    <td className="text-center py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-navy-100 text-navy-700 text-xs font-medium">{t('Lv.', 'स्तर')} {g.requiredLevel}</span>
                    </td>
                    <td className="text-center py-3 px-4">
                      <span className={`font-bold ${g.gap >= 3 ? 'text-red-600' : g.gap === 2 ? 'text-amber-600' : g.gap === 1 ? 'text-blue-600' : 'text-green-600'}`}>
                        {g.gap}
                      </span>
                    </td>
                    <td className="text-center py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${priorityColors[g.priority]}`}>{g.priority}</span>
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
