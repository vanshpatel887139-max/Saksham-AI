import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/layout/Header';
import { Card, Button, Tooltip, Modal } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { competencies } from '../data/mockData';
import { getRoleRequirements, selectTestCompetencies } from '../services/appService';
import { useStagger } from '../hooks/useStagger';
import { Info, HelpCircle, PlayCircle, RefreshCw } from 'lucide-react';

const levelLabels = ['Beginner', 'Basic', 'Intermediate', 'Advanced', 'Expert'];
const categoryColors: Record<string, string> = {
  Statistical: 'bg-blue-50 border-blue-200',
  Technical: 'bg-purple-50 border-purple-200',
  'Digital Governance': 'bg-green-50 border-green-200',
  Behavioural: 'bg-amber-50 border-amber-200',
};

/** True if any tested competency was assessed after the stored breakdown. */
function testedAtAfterBreakdown(
  scores: { source?: string; testedAt?: string | null }[],
  breakdownAt: string
): boolean {
  const cutoff = Date.parse(breakdownAt);
  if (Number.isNaN(cutoff)) return false;
  return scores.some(
    s => s.source === 'tested' && !!s.testedAt && Date.parse(s.testedAt) > cutoff
  );
}

export default function CompetencyPage() {
  const { user, selectedRole, setSelectedRole } = useApp();
  const { animate, staggerStyle } = useStagger();
  const navigate = useNavigate();
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [retakeOpen, setRetakeOpen] = useState(false);

  const scoreList = user?.competencies ?? [];
  const testMeta = user?.testMeta;
  const questionRecords = user?.assessmentQuestions ?? [];

  // A retake is only possible if this role actually has testable competencies.
  const focusCount = selectTestCompetencies(selectedRole, scoreList).length;
  const hasTestedResults = scoreList.some(s => s.source === 'tested');
  const canStartTest = focusCount > 0;

  const grouped = competencies.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {} as Record<string, typeof competencies>);

  const roleReqs = getRoleRequirements();
  const currentRoleReq = roleReqs.find(r => r.role === selectedRole)?.requirements || [];

  // Cheap derivations — no memo needed, and memoizing on arrays that are
  // rebuilt every render gives no benefit anyway.
  const scoreById = new Map(scoreList.map(s => [s.competencyId, s]));
  const testedSet = new Set(
    scoreList.filter(s => s.source === 'tested').map(s => s.competencyId)
  );

  // Only the latest attempt is kept server-side, so the stored breakdown
  // describes the most recent test. Hide it once that test is older than the
  // newest tested result — otherwise a retake that failed to persist its paper
  // would show a stale breakdown as if it were current.
  const breakdownIsCurrent =
    questionRecords.length > 0 &&
    !!testMeta?.takenAt &&
    !testedAtAfterBreakdown(scoreList, testMeta.takenAt);

  return (
    <div>
      <Header title="Competency Assessment" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(0, animate)}>
          <div>
            <p className="text-sm text-navy-400">Your proficiency snapshot based on the latest assessment</p>
            {testMeta?.takenAt && breakdownIsCurrent && (
              <p className="mt-1 text-xs text-navy-400">
                Last test: {new Date(testMeta.takenAt).toLocaleString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-navy-600">Target Role:</label>
              <select
                value={selectedRole}
                onChange={e => setSelectedRole(e.target.value)}
                className="px-3 py-1.5 border border-navy-200 rounded-lg text-sm bg-white"
              >
                {roleReqs.map(r => (
                  <option key={r.role} value={r.role}>
                    {r.role}
                  </option>
                ))}
              </select>
            </div>
            {breakdownIsCurrent && (
              <Button variant="secondary" onClick={() => setBreakdownOpen(true)}>
                <HelpCircle size={16} className="mr-1" />
                View Question Breakdown
              </Button>
            )}
            {canStartTest && (
              <Button
                onClick={() => {
                  if (hasTestedResults) setRetakeOpen(true);
                  else navigate('/competency-test');
                }}
              >
                {hasTestedResults ? (
                  <>
                    <RefreshCw size={16} className="mr-1" /> Retake Test
                  </>
                ) : (
                  <>
                    <PlayCircle size={16} className="mr-1" /> Start Assessment
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

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
                const req = currentRoleReq.find(r => r.competencyId === comp.id);
                const required = req?.level || 3;
                const sc = scoreById.get(comp.id);
                const level = sc?.level ?? 3;
                const tested = testedSet.has(comp.id);
                return (
                  <div key={comp.id} className={`p-4 rounded-lg border ${categoryColors[category]} ${tested ? 'ring-1 ring-indigo-200' : ''}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-navy-800">{comp.name}</p>
                      <div className="flex items-center gap-1">
                        <span className="text-[10px] px-1.5 py-0.5 bg-white/60 rounded text-navy-500">Req: Lv.{required}</span>
                        {tested ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-600 text-white">Tested</span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/70 text-navy-500">Not covered</span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-navy-400 mb-3">{comp.description}</p>
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-1">
                        {[1, 2, 3, 4, 5].map(lv => (
                          <span
                            key={lv}
                            className={`flex-1 px-2 py-1.5 rounded text-center text-xs font-medium transition-all ${
                              level === lv
                                ? 'bg-saffron-500 text-white shadow-sm'
                                : 'bg-white/60 text-navy-500'
                            }`}
                          >
                            {lv}
                          </span>
                        ))}
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-navy-400">{levelLabels[level - 1] || '—'}</div>
                        {sc?.source === 'tested' && sc.accuracy !== undefined && (
                          <div className="text-[10px] text-navy-400">{Math.round(sc.accuracy)}% accuracy</div>
                        )}
                        {sc?.source === 'tested' && sc.selfRatedLevel && sc.selfRatedLevel !== level && (
                          <div className="text-[10px] text-amber-600">
                            Self {sc.selfRatedLevel} → {level}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}

        <Modal
          open={retakeOpen}
          onClose={() => setRetakeOpen(false)}
          title="Retake competency test?"
          maxWidth="max-w-lg"
        >
          <p className="text-sm leading-relaxed text-navy-600">
            This will run a fresh test covering the {focusCount} highest-priority competencies
            for <span className="font-semibold">{selectedRole}</span>.
          </p>
          <div className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800">
            <div className="font-semibold">What changes</div>
            <ul className="mt-1.5 space-y-1 list-disc pl-4">
              <li>The {focusCount} tested competencies get new levels from your answers.</li>
              <li>Your previous question breakdown is replaced by this attempt.</li>
              <li>
                The other {scoreList.length - focusCount} competencies keep their current level and
                stay marked as not covered by a test.
              </li>
            </ul>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRetakeOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                setRetakeOpen(false);
                navigate('/competency-test');
              }}
            >
              Start retake
            </Button>
          </div>
        </Modal>

        <Modal
          open={breakdownOpen}
          onClose={() => setBreakdownOpen(false)}
          title="Test Question Breakdown"
          maxWidth="max-w-5xl"
        >
          <div className="space-y-6 max-h-[70vh] overflow-auto pr-1">
            {questionRecords.length === 0 ? (
              <p className="text-sm text-navy-400">No question breakdown available for the latest test.</p>
            ) : (
              questionRecords.map(q => {
                const correct = q.chosenIndex !== null && q.chosenIndex === q.correctIndex;
                return (
                  <div key={q.position} className="rounded-xl border border-navy-100 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="text-xs uppercase tracking-wide text-navy-400">
                          Q{q.position + 1} · {q.competencyName}
                        </div>
                        <h4 className="mt-1 text-sm font-semibold text-navy-900">{q.prompt}</h4>
                      </div>
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          correct ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
                        }`}
                      >
                        {correct ? 'Correct' : 'Incorrect'}
                      </span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {(q.options || []).map((opt: string, oi: number) => {
                        const chosen = oi === q.chosenIndex;
                        const isCorrect = oi === q.correctIndex;
                        return (
                          <div
                            key={oi}
                            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                              isCorrect
                                ? 'border-green-300 bg-green-50'
                                : chosen
                                  ? 'border-amber-300 bg-amber-50'
                                  : 'border-navy-100 bg-white'
                            }`}
                          >
                            <span className="text-xs font-semibold text-navy-400">{String.fromCharCode(65 + oi)}</span>
                            <span className="text-navy-700">{opt}</span>
                            {isCorrect && <span className="ml-auto text-xs font-medium text-green-700">Correct</span>}
                            {chosen && !isCorrect && (
                              <span className="ml-auto text-xs font-medium text-amber-700">Your answer</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {q.explanation && (
                      <p className="mt-3 rounded-lg bg-navy-50 px-3 py-2 text-xs leading-relaxed text-navy-600">
                        {q.explanation}
                      </p>
                    )}
                    <div className="mt-2 text-xs text-navy-400">
                      Difficulty: {q.difficulty}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </Modal>
      </div>
    </div>
  );
}

