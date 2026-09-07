import { useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Badge, Button } from '../components/ui/UIComponents';
import CodeRunner from '../components/CodeRunner';
import { useApp } from '../store/AppContext';
import { BarChart3, Brain, MapPin, FlaskConical } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, LineChart, Line, Tooltip, Cell } from 'recharts';

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
  const { animate, staggerStyle } = useStagger();
  const [activeLab, setActiveLab] = useState(labs[0]?.id ?? 'lab-python');

  return (
    <div>
      <Header title="Virtual Labs" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(0, animate)}>
          <p className="text-sm text-navy-500 max-w-2xl">
            Hands-on sandboxes for Official Statistics — practice Python, write SQL on real district data,
            build visualizations, fit regression models and explore GIS alongside your learning modules.
          </p>
          <Badge variant="info">Interactive</Badge>
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
  const lab = labs.find(l => l.id === 'lab-python')!;
  const presets = lab.exercises.map(e => ({ title: e.title, code: e.code })).filter(e => e.title !== undefined) as { title: string; code: string }[];
  const pythonPresets = [
    ...presets,
    { title: 'Error demo', code: PY_ERROR_DEMO },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">🐍 Interactive Python Sandbox</h3>
          <p className="text-xs text-navy-400 mt-1">Real CPython execution — syntax errors and tracebacks (NameError, TypeError, ZeroDivisionError…) are shown for any error.</p>
        </div>
        <Badge variant="success">Real CPython</Badge>
      </div>
      <CodeRunner initialCode={presets[0]?.code ?? ''} presets={pythonPresets} engine="python" />
    </Card>
  );
}

function SQLLab() {
  const sqlPresets = [
    { title: 'High literacy', code: 'SELECT name, literacy FROM districts WHERE literacy > 75 ORDER BY literacy DESC' },
    { title: 'By population', code: 'SELECT name, population FROM districts ORDER BY population DESC' },
    { title: 'Count samples', code: 'SELECT COUNT(*) FROM samples' },
    { title: 'Avg literacy', code: 'SELECT AVG(literacy) FROM districts' },
    { title: 'Kerala rows', code: "SELECT name, state FROM districts WHERE state = 'Kerala'" },
    { title: 'All samples', code: 'SELECT * FROM samples' },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-navy-800">🗃️ SQL on Official Census Data</h3>
          <p className="text-xs text-navy-400 mt-1">SELECT / WHERE / ORDER BY / aggregates on district census + survey data. Invalid queries report an error.</p>
        </div>
        <Badge variant="success">Real query engine</Badge>
      </div>
      <CodeRunner initialCode={sqlPresets[0].code} presets={sqlPresets} engine="sql" />
    </Card>
  );
}

function VizLab() {
  const { labs } = useApp();
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
      setVizError('Please enter at least one label, comma-separated.');
      setData([]);
      return;
    }
    if (ls.length !== vs.length) {
      setVizError(`Label count (${ls.length}) and numeric value count (${vs.length}) must match. Enter valid numbers, comma-separated.`);
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
          <h3 className="text-sm font-semibold text-navy-800">📈 Data Visualization Builder</h3>
          <p className="text-xs text-navy-400 mt-1">Labels and numeric values must be equal length; invalid input shows an error instead of silently dropping data.</p>
        </div>
        <Badge variant="success">Live render</Badge>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-navy-600">Labels (comma separated)</label>
          <input value={labels} onChange={e => setLabels(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" placeholder="Alwar, Mysuru, Nashik" />
          <label className="block text-xs font-medium text-navy-600">Values (comma separated)</label>
          <input value={values} onChange={e => setValues(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" placeholder="70.7, 72.6, 80.9" />
          <Button onClick={render}><BarChart3 size={14} className="mr-1" /> Render Chart</Button>
          {vizError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-600">✖ {vizError}</div>
          )}
          <div className="bg-navy-50 rounded-lg p-3 text-[11px] text-navy-500">
            💡 Try literacy rates (%) by district, or monthly CPI values, or household survey counts by state.
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
      setMlError('Enter at least 2 numeric X values (comma-separated).');
      setFit(null);
      return;
    }
    if (ys.length !== xs.length) {
      setMlError(`X has ${xs.length} values but Y has ${ys.length}. They must be equal length to fit a model.`);
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
          <h3 className="text-sm font-semibold text-navy-800">🤖 Linear Regression — the math behind forecast</h3>
          <p className="text-xs text-navy-400 mt-1">Fit a line to X/Y data points. Insufficient or mismatched data shows an error.</p>
        </div>
        <Badge variant="success">Supervised learning</Badge>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-navy-600">X values (e.g. hours studied)</label>
          <input value={xRaw} onChange={e => setXRaw(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" />
          <label className="block text-xs font-medium text-navy-600">Y values (e.g. quiz score)</label>
          <input value={yRaw} onChange={e => setYRaw(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm" />
          <Button onClick={run}><Brain size={14} className="mr-1" /> Fit Model</Button>
          {mlError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-600">✖ {mlError}</div>
          )}
          {fit && (
            <div className="bg-navy-50 rounded-lg p-4 space-y-1 text-sm">
              <p>Slope: <b>{fit.slope.toFixed(3)}</b> (points gained per hour)</p>
              <p>Intercept: <b>{fit.intercept.toFixed(2)}</b></p>
              <p>R² = <b>{fit.r2.toFixed(3)}</b> {fit.r2 > 0.9 ? '— excellent fit' : ''}</p>
              <p>Predicted × 8h: <b>{fit.predict(8).toFixed(1)}</b></p>
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
            <Line type="monotone" dataKey="actual" name="Actual" stroke="#0d1320" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="predicted" name="Predicted" stroke="#f97316" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function GISLab() {
  const { labs } = useApp();
  const lab = labs.find(l => l.id === 'lab-gis')!;
  const ex = lab.exercises[0];
  const points = (ex.points || []) as [string, number][];
  const max = Math.max(...points.map(p => p[1]));

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-navy-800">🗺️ Thematic Map — GIS for Official Statistics</h3>
        <Badge variant="success">Choropleth mode</Badge>
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
                    <p className="text-[11px] text-navy-400">Literacy {tr}%</p>
                  </div>
                </div>
                <MapPin size={16} className="text-navy-300" />
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-2 mt-4 text-[10px] text-navy-500">
          <span className="w-3 h-3 rounded-sm" style={{ background: '#fde68a' }} /> Low
          <span className="w-3 h-3 rounded-sm" style={{ background: '#fbbf24' }} /> Medium
          <span className="w-3 h-3 rounded-sm" style={{ background: '#f59e0b' }} /> High
          <span className="w-3 h-3 rounded-sm" style={{ background: '#f97316' }} /> Highest
          <span className="ml-auto">Legend — same data ranked by GIS colour intensity</span>
        </div>
      </div>
      <p className="text-[11px] text-navy-400 mt-3 flex items-center gap-1"><FlaskConical size={12} /> GIS layers combine administrative boundaries with statistical attributes to reveal spatial patterns in official data.</p>
    </Card>
  );
}