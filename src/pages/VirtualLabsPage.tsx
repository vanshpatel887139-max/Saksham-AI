import { useEffect, useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Badge, Button } from '../components/ui/UIComponents';
import CodeRunner from '../components/CodeRunner';
import { useApp, useI18n } from '../store/AppContext';
import { BarChart3, Brain, MapPin, FlaskConical } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, LineChart, Line, Tooltip, Cell } from 'recharts';
import { apiGetIndicators, apiGetSeries } from '../services/api';
import { setDatasetTables, Row } from '../services/sqlEngine';
import { StatIndicator } from '../types';

// ---------------- linear regression (mock ML) ----------------
function fitLine(xs: number[], ys: number[]) {
  const n = xs.length;
  const xbar = xs.reduce((a, b) => a + b, 0) / n;
  const ybar = ys.reduce((a, b) => a + b, 0) / n;
  const num = xs.reduce((a, x, i) => a + (x - xbar) * (ys[i] - ybar), 0);
  const den = xs.reduce((a, x) => a + (x - xbar) ** 2, 0);
  const slope = den ? num / den : 0;
  const intercept = ybar - slope * xbar;
  const predict = (x: number) => slope * x + intercept;
  const ssRes = ys.reduce((a, y, i) => a + (y - predict(xs[i])) ** 2, 0);
  const ssTot = ys.reduce((a, y) => a + (y - ybar) ** 2, 0);
  const r2 = ssTot ? 1 - ssRes / ssTot : 1;
  return { slope, intercept, predict, r2 };
}

const PY_ERROR_DEMO = "print('Calculating CPI...')\nrate = float('nan')\n# ReferenceError: name never defined\nprint('Inflation this quarter:', cpi_rate)";

export default function VirtualLabsPage() {
  const { labs } = useApp();
  const { t } = useI18n();
  const { animate, staggerStyle } = useStagger();
  const [activeLab, setActiveLab] = useState(labs[0]?.id ?? 'lab-python');

  return (
    <div>
      <Header title={t('Virtual Labs', 'वर्चुअल लैब')} />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(0, animate)}>
          <p className="text-sm text-navy-500 max-w-2xl">
            {t('Hands-on sandboxes for Official Statistics — practice Python, run SQL against real World Bank India statistics, build visualizations, fit regression models and explore GIS alongside your learning modules.', 'आधिकारिक सांख्यिकी हेतु व्यावहारिक सैंडबॉक्स — अपने अध्ययन मॉड्यूल के साथ Python का अभ्यास करें, विश्व बैंक के वास्तविक भारत आँकड़ों पर SQL चलाएँ, विज़ुअलाइज़ेशन बनाएँ, रिग्रेशन मॉडल फ़िट करें और GIS का अन्वेषण करें।')}
          </p>
          <Badge variant="info">{t('Interactive', 'इंटरैक्टिव')}</Badge>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1 stagger-fade-up" style={staggerStyle(1, animate)}>
          {labs.map(l => (
            <button key={l.id} onClick={() => setActiveLab(l.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm whitespace-nowrap transition-colors cursor-pointer ${activeLab === l.id ? 'bg-navy-700 text-white border-navy-700' : 'bg-white border-navy-100 text-navy-600 hover:bg-navy-50'}`}>
              <span>{l.icon}</span> {l.title}
            </button>
          ))}
        </div>

        {activeLab === 'lab-python' && <div className="stagger-fade-up" style={staggerStyle(2, animate)}><PythonLab /></div>}
        {activeLab === 'lab-sql' && <div className="stagger-fade-up" style={staggerStyle(2, animate)}><SQLLab /></div>}
        {activeLab === 'lab-viz' && <div className="stagger-fade-up" style={staggerStyle(2, animate)}><VizLab /></div>}
        {activeLab === 'lab-ml' && <div className="stagger-fade-up" style={staggerStyle(2, animate)}><MLLab /></div>}
        {activeLab === 'lab-gis' && <div className="stagger-fade-up" style={staggerStyle(2, animate)}><GISLab /></div>}
      </div>
    </div>
  );
}

function PythonLab() {
  const { labs } = useApp();
  const { t } = useI18n();
  const lab = labs.find(l => l.id === 'lab-python')!;
  const presets = lab.exercises.map(e => ({ title: e.title, code: e.code })).filter(e => e.title !== undefined) as { title: string; code: string }[];
  const pythonPresets = [
    ...presets,
    { title: t('Error demo', 'त्रुटि प्रदर्शन'), code: PY_ERROR_DEMO },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">{t('🐍 Interactive Python Sandbox', '🐍 इंटरैक्टिव Python सैंडबॉक्स')}</h3>
          <p className="text-xs text-navy-400 mt-1">{t('Real CPython execution — syntax errors and tracebacks (NameError, TypeError, ZeroDivisionError…) are shown for any error.', 'वास्तविक CPython निष्पादन — सिंटैक्स त्रुटियाँ और ट्रेसबैक (NameError, TypeError, ZeroDivisionError…) किसी भी त्रुटि हेतु प्रदर्शित किए जाते हैं।')}</p>
        </div>
        <Badge variant="success">{t('Real CPython', 'वास्तविक CPython')}</Badge>
      </div>
      <CodeRunner initialCode={presets[0]?.code ?? ''} presets={pythonPresets} engine="python" />
    </Card>
  );
}

function SQLLab() {
  // The lab is a client-side SQL sandbox (see services/sqlEngine.ts) — it does
  // not execute SQL against the live database, which would mean letting a
  // browser run arbitrary queries against a real Postgres. Instead the real
  // World Bank rows are fetched and installed as the sandbox's tables, so
  // learners practise SELECT/WHERE/ORDER BY/aggregates on genuine statistics.
  const [indicators, setIndicators] = useState<StatIndicator[]>([]);
  const [observations, setObservations] = useState<Row[]>([]);
  const [loadError, setLoadError] = useState('');
  const [attribution, setAttribution] = useState<StatIndicator | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const inds = await apiGetIndicators();
        if (cancelled) return;

        // Two series with a long shared span, so a JOIN or a grouped aggregate
        // has something to work with. Health and Education give the clearest
        // real-world contrast (rising life expectancy, falling fertility).
        const picks = ['SP.DYN.LE00.IN', 'SP.DYN.TFRT.IN', 'SE.ADT.LITR.ZS']
          .map(code => inds.find(i => i.code === code))
          .filter((i): i is StatIndicator => Boolean(i));
        if (picks.length === 0) throw new Error('No indicators returned by the API');

        const series = await Promise.all(picks.map(i => apiGetSeries(i.code)));
        if (cancelled) return;

        const obs: Row[] = series.flatMap(s =>
          s.points.map(p => ({
            indicator_code: s.indicator.code,
            year: p.year,
            value: p.value ?? 0,
          })),
        );
        const meta: Row[] = inds.map(i => ({
          code: i.code,
          name: i.name,
          category: i.category,
          unit: i.unit ?? '',
        }));

        setDatasetTables({ indicators: meta, observations: obs });
        setIndicators(inds);
        setObservations(obs);
        setAttribution(picks[0]);
      } catch (e) {
        if (!cancelled) setLoadError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const sqlPresets = [
    { title: t('All indicators', 'सभी संकेतक'), code: 'SELECT code, name, category FROM indicators ORDER BY category' },
    { title: t('Life expectancy over time', 'समय के साथ आयु स्थायित्व'), code: "SELECT year, value FROM observations WHERE indicator_code = 'SP.DYN.LE00.IN' ORDER BY year" },
    { title: t('Since 2000', '2000 के बाद से'), code: "SELECT year, value FROM observations WHERE indicator_code = 'SP.DYN.LE00.IN' AND year > 2000 ORDER BY year DESC" },
    { title: t('Count observations', 'प्रेक्षणों की गिनती'), code: 'SELECT COUNT(*) FROM observations' },
    { title: t('Average life expectancy', 'औसत आयु स्थायित्व'), code: "SELECT AVG(value) FROM observations WHERE indicator_code = 'SP.DYN.LE00.IN'" },
    { title: t('Health indicators', 'स्वास्थ्य संकेतक'), code: "SELECT code, name FROM indicators WHERE category = 'Health'" },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">{t('🗃️ SQL on World Bank India Data', '🗃️ विश्व बैंक भारत आँकड़ों पर SQL')}</h3>
          <p className="text-xs text-navy-400 mt-1">SELECT / WHERE / ORDER BY / {t('aggregates on', 'समुच्चय क्रियाओं सहित —')} {observations.length || '…'} {t('real observations across', 'वास्तविक प्रेक्षण तथा')} {indicators.length || '…'} {t('indicators.', 'संकेतकों पर कार्य करती हैं।')} {t('Invalid queries report an error.', 'अमान्य क्वेरी पर त्रुटि दर्शाई जाती है।')}</p>
        </div>
        <Badge variant="success">{t('Real query engine', 'वास्तविक क्वेरी इंजन')}</Badge>
      </div>
      {loadError && (
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
          {t('Could not load the live dataset', 'लाइव डेटासेट लोड नहीं हो सका')} ({loadError}). {t('The sandbox is running on its built-in sample rows, which are placeholders — sign in and check the API before quoting any number from here.', 'सैंडबॉक्स अपने अंतर्निहित नमूना पंक्तियों पर चल रहा है, जो केवल प्लेसहोल्डर हैं — यहाँ से कोई भी संख्या उद्धृत करने से पूर्व साइन इन करें और API जाँचें।')}
        </p>
      )}
      {!loadError && attribution && (
        <p className="mb-3 rounded-lg border border-navy-100 bg-navy-50 px-3 py-2 text-[11px] text-navy-500">
          {t('Source:', 'स्रोत:')} {attribution.source} · {attribution.license} · {attribution.source_url}
          {' · '}{attribution.provenance}
        </p>
      )}
      <CodeRunner initialCode={sqlPresets[0].code} presets={sqlPresets} engine="sql" />
    </Card>
  );
}

function VizLab() {
  const { labs } = useApp();
  const { t } = useI18n();
  const lab = labs.find(l => l.id === 'lab-viz')!;
  const preset = lab.exercises[0];
  const [labels, setLabels] = useState((preset.labels || []).join(', '));
  const [values, setValues] = useState((preset.values || []).join(', '));
  const [vizError, setVizError] = useState('');
  const [data, setData] = useState<{ label: string; value: number }[]>(
    (preset.labels || []).map((l, i) => ({ label: l, value: (preset.values || [])[i] || 0 }))
  );

  const render = () => {
    const ls = labels.split(',').map(s => s.trim()).filter(Boolean);
    const vs = values.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    if (ls.length === 0) {
      setVizError(t('Please enter at least one label, comma-separated.', 'कृपया कम से कम एक लेबल दर्ज करें, अल्प-विराम से अलग किया हुआ।'));
      setData([]);
      return;
    }
    if (ls.length !== vs.length) {
      setVizError(`${t('Label count (', 'लेबल की संख्या (')}${ls.length}) ${t('and numeric value count (', 'और संख्यात्मक मानों की संख्या (')}${vs.length})${t(' must match. Enter valid numbers, comma-separated.', ' समान होनी चाहिए। मान्य संख्याएँ दर्ज करें, अल्प-विराम से अलग की हुई।')}`);
      setData([]);
      return;
    }
    setVizError('');
    setData(ls.map((l, i) => ({ label: l, value: vs[i] })));
  };

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">{t('📈 Data Visualization Builder', '📈 डेटा विज़ुअलाइज़ेशन बिल्डर')}</h3>
          <p className="text-xs text-navy-400 mt-1">{t('Labels and numeric values must be equal length; invalid input shows an error instead of silently dropping data.', 'लेबल और संख्यात्मक मान समान लंबाई के होने चाहिए; अमान्य इनपुट पर डेटा चुपचाप हटाए बजाय त्रुटि दर्शाई जाती है।')}</p>
        </div>
        <Badge variant="success">{t('Live render', 'तत्काल प्रदर्शन')}</Badge>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-navy-600">{t('Labels (comma separated)', 'लेबल (अल्प-विराम से अलग)')}</label>
          <input value={labels} onChange={e => setLabels(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" placeholder="Alwar, Mysuru, Nashik" />
          <label className="block text-xs font-medium text-navy-600">{t('Values (comma separated)', 'मान (अल्प-विराम से अलग)')}</label>
          <input value={values} onChange={e => setValues(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" placeholder="70.7, 72.6, 80.9" />
          <Button onClick={render}><BarChart3 size={14} className="mr-1" /> {t('Render Chart', 'चार्ट प्रदर्शित करें')}</Button>
          {vizError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-600">✖ {vizError}</div>
          )}
          <div className="bg-navy-50 rounded-lg p-3 text-[11px] text-navy-500">
            💡 {t('Try literacy rates (%) by district, or monthly CPI values, or household survey counts by state.', 'जिला-वार साक्षरता दर (%), मासिक CPI मान, या राज्यवार घरेलू सर्वेक्षण गिनती आज़माएँ।')}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Bar dataKey="value" fill="#f97316" radius={[6, 6, 0, 0]}>
              {data.map((_d, i) => <Cell key={i} fill={['#f97316', '#0d1320', '#f59e0b', '#3b82f6'][i % 4]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function MLLab() {
  const { labs } = useApp();
  const { t } = useI18n();
  const lab = labs.find(l => l.id === 'lab-ml')!;
  const ex = lab.exercises[0];
  const [xRaw, setXRaw] = useState((ex.x || []).join(', '));
  const [yRaw, setYRaw] = useState((ex.y || []).join(', '));
  const [mlError, setMlError] = useState('');
  const [fit, setFit] = useState<{ slope: number; intercept: number; r2: number; predict: (x: number) => number } | null>(null);

  const run = () => {
    const xs = xRaw.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    const ys = yRaw.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    if (xs.length < 2) {
      setMlError(t('Enter at least 2 numeric X values (comma-separated).', 'कम से कम 2 संख्यात्मक X मान दर्ज करें (अल्प-विराम से अलग)।'));
      setFit(null);
      return;
    }
    if (ys.length !== xs.length) {
      setMlError(`${t('X has', 'X में')} ${xs.length} ${t('values but Y has', 'मान हैं, जबकि Y में')} ${ys.length}. ${t('They must be equal length to fit a model.', 'मॉडल फ़िट करने हेतु दोनों की लंबाई समान होनी चाहिए।')}`);
      setFit(null);
      return;
    }
    setMlError('');
    const result = fitLine(xs, ys);
    setFit({ ...result, predict: result.predict });
  };

  const xs = xRaw.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
  const ys = yRaw.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
  const chartData = fit && xs.length === ys.length
    ? xs.map((x, i) => ({ x, actual: ys[i], predicted: Number(fit.predict(x).toFixed(2)) }))
    : [];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">{t('🤖 Linear Regression — the math behind forecast', '🤖 लीनियर रिग्रेशन — पूर्वानुमान का गणित')}</h3>
          <p className="text-xs text-navy-400 mt-1">{t('Fit a line to X/Y data points. Insufficient or mismatched data shows an error.', 'X/Y आँकड़ बिंदुओं पर एक रेखा फ़िट करें। अपर्याप्त या अमेल डेटा पर त्रुटि दर्शाई जाती है।')}</p>
        </div>
        <Badge variant="success">{t('Supervised learning', 'पर्यवेक्षित अधिगम')}</Badge>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-navy-600">{t('X values (e.g. hours studied)', 'X मान (जैसे अध्ययन घंटे)')}</label>
          <input value={xRaw} onChange={e => setXRaw(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" />
          <label className="block text-xs font-medium text-navy-600">{t('Y values (e.g. quiz score)', 'Y मान (जैसे क्विज़ अंक)')}</label>
          <input value={yRaw} onChange={e => setYRaw(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" />
          <Button onClick={run}><Brain size={14} className="mr-1" /> {t('Fit Model', 'मॉडल फ़िट करें')}</Button>
          {mlError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-600">✖ {mlError}</div>
          )}
          {fit && (
            <div className="bg-navy-50 rounded-lg p-4 space-y-1 text-sm">
              <p>{t('Slope:', 'ढाल:')} <b>{fit.slope.toFixed(3)}</b> {t('(points gained per hour)', '(प्रति घंटा अर्जित अंक)')}</p>
              <p>{t('Intercept:', 'अन्तःखण्ड:')} <b>{fit.intercept.toFixed(2)}</b></p>
              <p>R² = <b>{fit.r2.toFixed(3)}</b> {fit.r2 > 0.9 ? t('— excellent fit', '— उत्कृष्ट फ़िट') : ''}</p>
              <p>{t('Predicted × 8h:', '8 घंटे हेतु अनुमानित अंक:')} <b>{fit.predict(8).toFixed(1)}</b></p>
            </div>
          )}
          <p className="text-[11px] text-navy-400">{ex.explain}</p>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="x" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line type="monotone" dataKey="actual" name={t('Actual', 'वास्तविक')} stroke="#0d1320" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="predicted" name={t('Predicted', 'अनुमानित')} stroke="#f97316" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function GISLab() {
  const { labs } = useApp();
  const { t } = useI18n();
  const lab = labs.find(l => l.id === 'lab-gis')!;
  const ex = lab.exercises[0];
  const points = (ex.points || []) as [string, number][];
  const max = Math.max(...points.map(p => p[1]));

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-navy-800">{t('🗺️ Thematic Map — GIS for Official Statistics', '🗺️ थीमैटिक मानचित्र — आधिकारिक सांख्यिकी हेतु GIS')}</h3>
        <Badge variant="success">{t('Choropleth mode', 'कोरोप्लेथ मोड')}</Badge>
      </div>
      <div className="bg-navy-50 rounded-2xl p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {points.map(([district, tr]) => {
            const intensity = Math.round((tr / max) * 100);
            const color = intensity > 85 ? '#f97316' : intensity > 75 ? '#f59e0b' : intensity > 60 ? '#fbbf24' : '#fde68a';
            return (
              <div key={district} className="bg-white rounded-xl p-4 border border-navy-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-white`} style={{ background: color }}>
                    {tr.toFixed(0)}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-navy-800">{district}</p>
                    <p className="text-[11px] text-navy-400">{t('Literacy', 'साक्षरता')} {tr}%</p>
                  </div>
                </div>
                <MapPin size={16} className="text-navy-300" />
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-2 mt-4 text-[10px] text-navy-500">
          <span className="w-3 h-3 rounded-sm" style={{ background: '#fde68a' }} /> {t('Low', 'निम्न')}
          <span className="w-3 h-3 rounded-sm" style={{ background: '#fbbf24' }} /> {t('Medium', 'मध्यम')}
          <span className="w-3 h-3 rounded-sm" style={{ background: '#f59e0b' }} /> {t('High', 'उच्च')}
          <span className="w-3 h-3 rounded-sm" style={{ background: '#f97316' }} /> {t('Highest', 'सर्वाधिक')}
          <span className="ml-auto">{t('Legend — same data ranked by GIS colour intensity', 'संकेत-सूची — वही डेटा GIS रंग तीव्रता के अनुसार क्रमबद्ध')}</span>
        </div>
      </div>
      <p className="text-[11px] text-navy-400 mt-3 flex items-center gap-1"><FlaskConical size={12} /> {t('GIS layers combine administrative boundaries with statistical attributes to reveal spatial patterns in official data.', 'GIS परतें प्रशासनिक सीमाओं को सांख्यिकीय विशेषताओं के साथ मिलाकर आधिकारिक डेटा में स्थानीय पैटर्न को उजागर करती हैं।')}</p>
    </Card>
  );
}