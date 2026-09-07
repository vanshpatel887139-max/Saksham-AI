import { useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Button, Tooltip } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { competencies } from '../data/mockData';
import { getRoleRequirements } from '../services/appService';
import { useStagger } from '../hooks/useStagger';
import { Save, Info } from 'lucide-react';

const levelLabels = ['Beginner', 'Basic', 'Intermediate', 'Advanced', 'Expert'];
const categoryColors: Record<string, string> = {
  'Statistical': 'bg-blue-50 border-blue-200',
  'Technical': 'bg-purple-50 border-purple-200',
  'Digital Governance': 'bg-green-50 border-green-200',
  'Behavioural': 'bg-amber-50 border-amber-200',
};

export default function CompetencyPage() {
  const { user, updateCompetencies, selectedRole, setSelectedRole, calculateGaps } = useApp();
  const { animate, staggerStyle } = useStagger();
  const [scores, setScores] = useState<Record<string, number>>(
    Object.fromEntries(user?.competencies.map(c => [c.competencyId, c.level]) || competencies.map(c => [c.id, 3]))
  );
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    const newScores = Object.entries(scores).map(([competencyId, level]) => ({ competencyId, level }));
    await updateCompetencies(newScores);
    await calculateGaps();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const grouped = competencies.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {} as Record<string, typeof competencies>);

  const roleReqs = getRoleRequirements();

  return (
    <div>
      <Header title="Competency Assessment" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(0, animate)}>
          <div>
            <p className="text-sm text-navy-400">Rate your proficiency in each competency area (1-5 scale)</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-navy-600">Target Role:</label>
              <select
                value={selectedRole}
                onChange={e => setSelectedRole(e.target.value)}
                className="px-3 py-1.5 border border-navy-200 rounded-lg text-sm bg-white"
              >
                {roleReqs.map(r => <option key={r.role} value={r.role}>{r.role}</option>)}
              </select>
            </div>
            <Button onClick={handleSave}>
              <Save size={16} className="mr-1" /> Save Assessment
            </Button>
          </div>
        </div>

        {saved && (
          <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
            Assessment saved successfully! Skill gap analysis has been updated.
          </div>
        )}

        {Object.entries(grouped).map(([category, comps], i) => (
          <Card key={category} className="stagger-fade-up" style={staggerStyle(1 + i, animate)}>
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-base font-semibold text-navy-800">{category} Competencies</h3>
              <Tooltip text={`Competencies in the ${category} domain`}>
                <Info size={14} className="text-navy-400" />
              </Tooltip>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {comps.map(comp => {
                const req = roleReqs.find(r => r.role === selectedRole)?.requirements.find(r => r.competencyId === comp.id);
                const required = req?.level || 3;
                return (
                  <div key={comp.id} className={`p-4 rounded-lg border ${categoryColors[category]}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-navy-800">{comp.name}</p>
                      <span className="text-[10px] px-1.5 py-0.5 bg-white/60 rounded text-navy-500">Req: Lv.{required}</span>
                    </div>
                    <p className="text-xs text-navy-400 mb-3">{comp.description}</p>
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map(level => (
                        <button
                          key={level}
                          onClick={() => setScores(prev => ({ ...prev, [comp.id]: level }))}
                          className={`flex-1 py-1.5 rounded text-xs font-medium transition-all cursor-pointer ${
                            scores[comp.id] === level
                              ? 'bg-saffron-500 text-white shadow-sm'
                              : level <= (scores[comp.id] || 0)
                              ? 'bg-saffron-200 text-saffron-700'
                              : 'bg-white/60 text-navy-400 hover:bg-white'
                          }`}
                        >
                          {level}
                        </button>
                      ))}
                    </div>
                    <p className="text-[10px] text-navy-400 mt-1.5 text-center">{levelLabels[(scores[comp.id] || 1) - 1]}</p>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}

        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 stagger-fade-up" style={staggerStyle(6, animate)}>
          <p className="text-xs text-blue-700">
            <Info size={12} className="inline mr-1" />
            Scale: 1 = Beginner, 2 = Basic, 3 = Intermediate, 4 = Advanced, 5 = Expert
          </p>
        </div>
      </div>
    </div>
  );
}
