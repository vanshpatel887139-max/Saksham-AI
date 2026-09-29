import { useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp, useI18n } from '../store/AppContext';
import { CompetencyTest, CompetencyTestResult } from '../types';
import {
  getAllCompetencies, getRoleRequirements,
  deriveCompetencyTestLevels, applyCompetencyTestToProfile,
  selectTestCompetencies, buildQuestionRecords,
  TEST_SUBSET_SIZE, QUESTIONS_PER_COMPETENCY,
} from '../services/appService';
import { apiGenerateCompetencyTest, apiSubmitCompetencyTest } from '../services/api';

type Stage = 'intro' | 'self-rating' | 'starting' | 'taking' | 'grading' | 'results';

const LEVEL_LABELS: Record<number, string> = {
  1: 'Beginner',
  2: 'Basic',
  3: 'Competent',
  4: 'Proficient',
  5: 'Expert',
};

const LEVEL_LABELS_HI: Record<number, string> = {
  1: 'शुरुआती',
  2: 'बुनियादी',
  3: 'सक्षम',
  4: 'प्रवीण',
  5: 'विशेषज्ञ',
};

export default function CompetencyTestPage() {
  const { user, selectedRole, updateCompetencies, calculateGaps, setLocalAssessmentRecords } = useApp();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>('intro');
  const [test, setTest] = useState<CompetencyTest | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [current, setCurrent] = useState(0);
  const [results, setResults] = useState<CompetencyTestResult[]>([]);
  const [selfRatings, setSelfRatings] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const levelLabel = (lv: number) => t(LEVEL_LABELS[lv], LEVEL_LABELS_HI[lv]);

  const competencies = useMemo(() => getAllCompetencies(), []);
  const roleLabel = useMemo(() => {
    const req = getRoleRequirements().find(r => r.role === selectedRole);
    return req ? req.role : selectedRole;
  }, [selectedRole]);

  // Only the highest-priority slice of the 32 role requirements is testable —
  // spreading 18 questions across all of them would give one each.
  const focusCompetencies = useMemo(
    () => selectTestCompetencies(selectedRole, user?.competencies ?? []),
    [selectedRole, user?.competencies]
  );
  const testCompetencyIds = useMemo(
    () => focusCompetencies.map(c => c.competencyId),
    [focusCompetencies]
  );

  const focusMeta = useMemo(
    () => focusCompetencies.map(fc => ({
      ...fc,
      name: competencies.find(c => c.id === fc.competencyId)?.name ?? fc.competencyId,
    })),
    [focusCompetencies, competencies]
  );

  const answeredCount = useMemo(
    () => answers.filter(a => a !== null && a !== undefined).length,
    [answers]
  );
  const allAnswered = !!test && answeredCount === test.questions.length;
  const selfRatedCount = Object.keys(selfRatings).length;

  const startTest = useCallback(async () => {
    setError(null);
    setStage('starting');
    // Falls back to the local bank when the backend is unreachable.
    const built = await apiGenerateCompetencyTest(
      selectedRole,
      roleLabel,
      testCompetencyIds,
      TEST_SUBSET_SIZE * QUESTIONS_PER_COMPETENCY,
      QUESTIONS_PER_COMPETENCY
    );
    const questions = built?.questions ?? [];
    if (questions.length === 0) {
      setError(t('No questions could be generated for this role. Please try again.', 'इस पद के लिए कोई प्रश्न तैयार नहीं हो सके। कृपया पुनः प्रयास करें।'));
      setStage('intro');
      return;
    }
    setTest(built);
    setAnswers(new Array(questions.length).fill(null));
    setCurrent(0);
    setStage('taking');
  }, [selectedRole, roleLabel, testCompetencyIds, t]);

  const submitTest = useCallback(async () => {
    if (!test || !allAnswered) return;
    setStage('grading');
    setError(null);
    // Falls back to local grading when the backend is unreachable.
    const graded = await apiSubmitCompetencyTest(test, answers, user?.id, selfRatings);
    const levels = graded?.results?.length
      ? graded.results
      : deriveCompetencyTestLevels(test.questions, answers);
    if (levels.length === 0) {
      setError(t('The test could not be graded. Your profile was left unchanged.', 'परीक्षण का मूल्यांकन नहीं हो सका। आपकी प्रोफ़ाइल में कोई बदलाव नहीं किया गया है।'));
      setStage('results');
      return;
    }
    // Prefer the timestamp the backend stamped at submit time; the offline
    // path has no backend response, so fall back to generation time.
    const gradedTest = {
      ...test,
      results: levels,
      locked: true,
      takenAt: graded?.takenAt || test.takenAt,
      gradedOffline: graded?.gradedOffline,
    };
    const applied = applyCompetencyTestToProfile(
      { competencies: user?.competencies ?? [] },
      gradedTest,
      selfRatings
    );
    // The online path gets testMeta / assessmentQuestions back from
    // `apiUpdateCompetencies`. Offline that call throws, so build the paper here
    // from the local bank and stamp it into profile state directly.
    if (gradedTest.gradedOffline) {
      setLocalAssessmentRecords(
        buildQuestionRecords(test, answers),
        test.id,
        gradedTest.takenAt ?? new Date().toISOString()
      );
    }
    await updateCompetencies(applied.competencies);
    await calculateGaps(selectedRole);
    setTest(gradedTest);
    setResults(levels);
    // A successful grade belongs on the report, which is where the breakdown
    // lives. The results stage below stays reachable for grading failures.
    navigate('/competency');
  }, [test, answers, allAnswered, user, selectedRole, selfRatings, updateCompetencies, calculateGaps, setLocalAssessmentRecords, navigate, t]);

  const goToResults = useCallback(() => {
    navigate('/competency');
  }, [navigate]);

  const retake = useCallback(() => {
    setTest(null);
    setAnswers([]);
    setCurrent(0);
    setResults([]);
    setError(null);
    // Must also clear self-ratings: the "Skip self-rating" path resets them,
    // so a retake that kept them would silently re-submit stale ratings and
    // write them into selfRatedLevel.
    setSelfRatings({});
    setStage('intro');
  }, []);

  if (stage === 'intro') {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <div className="rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
          <span className="inline-flex rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
            {t('Role-Based Competency Test', 'पद-आधारित दक्षता परीक्षण')}
          </span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">
            {t('Verify your', 'अपनी')} {roleLabel} {t('competencies', 'दक्षताएँ सत्यापित करें')}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">
            {t('Answer a short set of role-specific questions. Your responses derive an objective competency level (1–5) for each assessed skill, which updates your profile and skill-gap analysis in place of self-rating — so recommendations and your learning path stay accurate.', 'पद-विशिष्ट प्रश्नों का एक संक्षिप्त समूह हल करें। आपके उत्तरों से प्रत्येक मूल्यांकित कौशल के लिए वस्तुनिष्ठ दक्षता स्तर (1–5) निर्धारित होगा, जो स्व-मूल्यांकन के स्थान पर आपकी प्रोफ़ाइल और कौशल-अंतराल विश्लेषण को अद्यतन करेगा — जिससे सिफ़ारिशें और आपका सीखने का मार्ग सटीक बने रहेंगे।')}
          </p>
          <div className="mt-4 rounded-xl bg-indigo-50/60 p-4 text-sm text-gray-700">
            <div className="font-semibold text-indigo-900">{t("What you'll get", 'आपको क्या मिलेगा')}</div>
            <ul className="mt-2 space-y-1">
              <li>
                {t('Derived levels for', 'निर्धारित स्तर')} {testCompetencyIds.length} {t('priority competencies', 'प्राथमिकता दक्षताओं के लिए')}
                {testCompetencyIds.length > 0 && ` (${testCompetencyIds.length * QUESTIONS_PER_COMPETENCY} ${t('questions', 'प्रश्न')})`}
              </li>
              <li>{t('Compare your own view against the objective result', 'अपने स्वयं के आकलन की तुलना वस्तुनिष्ठ परिणाम से करें')}</li>
              <li>{t('Automatic update to skill gaps, radar & course recommendations', 'कौशल अंतराल, रडार और पाठ्यक्रम सिफ़ारिशों में स्वतः अद्यतन')}</li>
            </ul>
          </div>
          {focusMeta.length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t('This test covers', 'इस परीक्षण में शामिल')}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {focusMeta.map(fc => (
                  <span
                    key={fc.competencyId}
                    title={t(`Required level ${fc.level} for this role`, `इस पद के लिए आवश्यक स्तर ${fc.level}`)}
                    className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700"
                  >
                    {fc.name} <span className="text-gray-400">{t(`L${fc.level}`, `स्तर ${fc.level}`)}</span>
                  </span>
                ))}
              </div>
              <p className="mt-2 text-xs text-gray-500">
                {t('Chosen by role priority and your current level. The other competencies keep their existing level and are marked as not yet assessed.', 'पद की प्राथमिकता और आपके वर्तमान स्तर के आधार पर चयनित। अन्य दक्षताएँ अपना वर्तमान स्तर बनाए रखेंगी और अभी तक मूल्यांकित नहीं के रूप में चिह्नित रहेंगी।')}
              </p>
            </div>
          )}
          {error && (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {error}
            </div>
          )}
          <button
            onClick={() => setStage('self-rating')}
            disabled={testCompetencyIds.length === 0}
            className="mt-6 w-full rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {testCompetencyIds.length > 0 ? t('Start Competency Test', 'दक्षता परीक्षण प्रारंभ करें') : t('No testable competencies', 'कोई परीक्षण-योग्य दक्षता नहीं')}
          </button>
        </div>
      </div>
    );
  }

  if (stage === 'self-rating') {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <div className="rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
          <span className="inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            {t('Step 1 of 2 · Optional', 'चरण 1 / 2 · वैकल्पिक')}
          </span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">{t('How do you rate yourself?', 'आप स्वयं को कैसा आँकते हैं?')}</h1>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">
            {t('This is entirely optional. Rating yourself lets us show a perception gap — the difference between how confident you are and how you actually performed. Skip it and we will still derive your levels from the test alone.', 'यह पूर्णतः वैकल्पिक है। स्वयं को आँकने से हम एक धारणा-अंतर दिखा पाते हैं — आपके आत्मविश्वास और आपके वास्तविक प्रदर्शन के बीच का अंतर। इसे छोड़ने पर भी हम केवल परीक्षण से आपके स्तर निर्धारित करेंगे।')}
          </p>

          <div className="mt-5 space-y-3">
            {focusMeta.map(fc => (
              <div key={fc.competencyId} className="rounded-xl border border-gray-200 p-4">
                <div className="text-sm font-semibold text-gray-900">{fc.name}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {[1, 2, 3, 4, 5].map(lv => (
                    <button
                      key={lv}
                      type="button"
                      onClick={() =>
                        setSelfRatings(s => ({ ...s, [fc.competencyId]: lv }))
                      }
                      title={levelLabel(lv)}
                      className={`h-9 w-9 rounded-lg border text-sm font-semibold transition ${
                        selfRatings[fc.competencyId] === lv
                          ? 'border-indigo-600 bg-indigo-600 text-white'
                          : 'border-gray-200 bg-white text-gray-600 hover:border-indigo-300'
                      }`}
                    >
                      {lv}
                    </button>
                  ))}
                  {selfRatings[fc.competencyId] && (
                    <span className="self-center pl-1 text-xs text-gray-500">
                      {levelLabel(selfRatings[fc.competencyId])}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {error}
            </div>
          )}

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={() => {
                setSelfRatings({});
                setStage('starting');
                void startTest();
              }}
              className="flex-1 rounded-lg border border-gray-200 px-5 py-3 text-sm font-semibold text-gray-600 transition hover:bg-gray-50"
            >
              {t('Skip self-rating', 'स्व-मूल्यांकन छोड़ें')}
            </button>
            <button
              onClick={() => {
                setStage('starting');
                void startTest();
              }}
              className="flex-1 rounded-lg bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
            >
              {t('Continue', 'जारी रखें')}{selfRatedCount > 0 ? ` (${selfRatedCount} ${t('rated', 'आँके गए')})` : ''}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (stage === 'starting') {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
          <p className="mt-4 text-sm font-medium text-gray-600">{t('Preparing your questions…', 'आपके प्रश्न तैयार किए जा रहे हैं…')}</p>
        </div>
      </div>
    );
  }

  if (stage === 'taking' && test) {
    const q = test.questions[current];
    if (!q) {
      return (
        <div className="mx-auto max-w-2xl px-4 py-10">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
            {t('This test has no questions available. Your profile was left unchanged.', 'इस परीक्षण में कोई प्रश्न उपलब्ध नहीं है। आपकी प्रोफ़ाइल में कोई बदलाव नहीं किया गया है।')}
            <button onClick={retake} className="mt-4 block font-semibold underline">{t('Back', 'पीछे')}</button>
          </div>
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <div className="rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span>
              {t('Question', 'प्रश्न')} {current + 1} {t('of', 'में से')} {test.questions.length}
            </span>
            <span className="rounded-full bg-indigo-50 px-3 py-1 font-medium text-indigo-700">
              {answeredCount}/{test.questions.length} {t('answered', 'उत्तरित')}
            </span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all"
              style={{ width: `${((current + 1) / test.questions.length) * 100}%` }}
            />
          </div>          <h2 className="mt-4 text-lg font-semibold text-gray-900">{q.prompt}</h2>
          <div className="mt-1 text-xs font-medium text-gray-500">{q.competencyName}</div>
          <div className="mt-4 space-y-2">
            {q.options.map((opt, oi) => (
              <label
                key={oi}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${
                  answers[current] === oi ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-indigo-200'
                }`}
              >
                <input
                  type="radio"
                  name={`q-${current}`}
                  checked={answers[current] === oi}
                  onChange={() => setAnswers(a => a.map((v, i) => (i === current ? oi : v)))}
                  className="h-4 w-4 accent-indigo-600"
                />
                {opt}
              </label>
            ))}
          </div>
          <div className="mt-6 flex items-center justify-between">
            <button
              onClick={() => setCurrent(c => Math.max(0, c - 1))}
              disabled={current === 0}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 disabled:opacity-40"
            >
              {t('Back', 'पीछे')}
            </button>
            {current < test.questions.length - 1 ? (
              <button
                onClick={() => setCurrent(c => c + 1)}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                {t('Next', 'आगे')}
              </button>
            ) : (
              <button
                onClick={submitTest}
                disabled={!allAnswered}
                title={allAnswered ? undefined : `${t('Answer all', 'सभी')} ${test.questions.length} ${t('questions to submit', 'प्रश्नों के उत्तर देकर सबमिट करें')}`}
                className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t('Submit Test', 'परीक्षण सबमिट करें')}
              </button>
            )}
          </div>
          {!allAnswered && (
            <p className="mt-3 text-right text-xs text-gray-500">
              {t('Answer every question to enable submission.', 'सबमिट करने के लिए प्रत्येक प्रश्न का उत्तर दें।')}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (stage === 'grading') {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
          <p className="mt-4 text-sm font-medium text-gray-600">{t('Deriving competency levels…', 'दक्षता स्तर निर्धारित किए जा रहे हैं…')}</p>
        </div>
      </div>
    );
  }

  const selfMap = new Map((user?.competencies ?? []).map(c => [c.competencyId, c]));

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900">{t('Test Complete', 'परीक्षण पूर्ण')}</h1>
        <p className="mt-1 text-sm text-gray-600">
          {error
            ? error
            : t('Derived competency levels applied to your profile. Your skill-gap analysis, radar and recommendations are updated.', 'निर्धारित दक्षता स्तर आपकी प्रोफ़ाइल पर लागू कर दिए गए हैं। आपका कौशल-अंतराल विश्लेषण, रडार और सिफ़ारिशें अद्यतन कर दी गई हैं।')}
        </p>

        <div className="mt-6 space-y-3">
          {results.map(r => {
            // Prefer the rating just given; fall back to the stored self-rating.
            const self = selfRatings[r.competencyId] ?? r.selfRatedLevel ?? selfMap.get(r.competencyId)?.selfRatedLevel ?? 0;
            return (
              <div key={r.competencyId} className="flex items-center justify-between rounded-xl border border-gray-100 bg-gray-50/60 px-4 py-3">
                <div>
                  <div className="text-sm font-semibold text-gray-800">{r.competencyName}</div>
                  <div className="text-xs text-gray-500">
                    {r.correctCount}/{r.questionsAttempted} {t('correct', 'सही')} · {r.accuracyPct}% {t('accuracy', 'सटीकता')} · {t('difficulty up to', 'कठिनाई स्तर तक')} {r.highestDifficultyCorrect}
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-1">
                    <span className={`text-xl font-bold ${r.derivedLevel >= 4 ? 'text-emerald-600' : r.derivedLevel >= 3 ? 'text-indigo-600' : 'text-amber-600'}`}>
                      {t('Level', 'स्तर')} {r.derivedLevel}
                    </span>
                  </div>
                  {self > 0 && (
                    <div className="text-xs text-gray-500">
                      {t('Self', 'स्वयं')} {self} → {t('Derived', 'निर्धारित')} {r.derivedLevel}{' '}
                      <span className={r.derivedLevel < self ? 'text-amber-600' : 'text-emerald-600'}>
                        {r.derivedLevel === self ? t('(matched)', '(मेल खाता)') : r.derivedLevel < self ? `(−${self - r.derivedLevel} ${t('perception gap', 'धारणा अंतर')})` : `(+${r.derivedLevel - self})`}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            onClick={goToResults}
            className="flex-1 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            {t('View full competency report', 'पूर्ण दक्षता रिपोर्ट देखें')}
          </button>
          <button
            onClick={retake}
            className="rounded-lg border border-indigo-200 px-5 py-2.5 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-50"
          >
            {t('Retake Test', 'परीक्षण पुनः दें')}
          </button>
        </div>
      </div>
    </div>
  );
}
