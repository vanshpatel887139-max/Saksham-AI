import { useState } from 'react';
import { Play, RotateCcw, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Button } from './ui/UIComponents';
import { apiRunPython } from '../services/api';
import { interpretPython } from '../services/pythonEngine';
import { runSQL, Row } from '../services/sqlEngine';
import { PythonRunResult } from '../types';

interface CodeRunnerProps {
  initialCode: string;
  presets?: { title: string; code: string }[];
  engine?: 'python' | 'sql';
}

const PY_DEFAULT = "ages = [28, 34, 29, 41, 36]\ntotal = 0\nfor a in ages:\n    total += a\nprint('Count:', len(ages))\nprint('Sum:', total)\nprint('Mean age:', round(total / len(ages), 2))";

export default function CodeRunner({ initialCode, presets, engine = 'python' }: CodeRunnerProps) {
  const [code, setCode] = useState(initialCode || (engine === 'sql' ? 'SELECT name, literacy FROM districts WHERE literacy > 75 ORDER BY literacy DESC' : PY_DEFAULT));
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ output?: string; error?: string; ok: boolean; durationMs?: number } | null>(null);
  const [sql, setSql] = useState<{ rows: Row[]; columns: string[]; ok: boolean; message?: string } | null>(null);

  const run = async () => {
    if (!code.trim()) {
      setResult({ ok: false, error: 'Please enter some code to run.', output: '' });
      setSql(null);
      return;
    }
    setRunning(true);
    setResult(null);
    try {
      if (engine === 'python') {
        let r: PythonRunResult;
        try {
          r = await apiRunPython(code);
        } catch {
          const mock = interpretPython(code);
          r = { ok: mock.ok, output: mock.output, error: mock.ok ? '' : undefined };
        }
        setResult({ output: r.output, error: r.error, ok: r.ok, durationMs: r.durationMs });
      } else {
        const r = runSQL(code);
        setSql(r);
        setResult(r.ok ? { ok: true, output: `${r.rows.length} row(s) returned` } : { ok: false, error: `SQL Error: ${r.message}` });
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-xl border border-navy-100 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-navy-800">
        <p className="text-xs font-medium text-navy-200">{engine === 'python' ? '🐍 Python Runner' : '🗃️ SQL Runner'}</p>
        {result?.ok && (
          <span className="inline-flex items-center gap-1 text-[10px] text-green-300 font-medium">
            <CheckCircle2 size={11} /> Executed OK{result.durationMs ? ` · ${result.durationMs} ms` : ''}
          </span>
        )}
        {result && !result.ok && (
          <span className="inline-flex items-center gap-1 text-[10px] text-red-300 font-medium"><XCircle size={11} /> Failed</span>
        )}
      </div>

      {presets && presets.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2">
          {presets.map(p => (
            <button key={p.title} onClick={() => setCode(p.code)}
              className="px-2.5 py-1 bg-navy-50 text-navy-700 rounded-lg text-[11px] hover:bg-navy-100 cursor-pointer">
              {p.title}
            </button>
          ))}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-3 p-3">
        <div>
          <textarea value={code} onChange={e => setCode(e.target.value)} spellCheck={false}
            className="w-full h-56 bg-navy-900 text-green-300 font-mono text-xs p-4 rounded-lg outline-none resize-none" />
          <div className="flex items-center gap-2 mt-2">
            <Button size="sm" onClick={run} disabled={running}>
              {running ? <><Loader2 size={14} className="mr-1 animate-spin" /> Running…</> : <><Play size={14} className="mr-1" /> Run</>}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setCode(initialCode || ''); setResult(null); setSql(null); }}>
              <RotateCcw size={13} className="mr-1" /> Clear
            </Button>
          </div>
        </div>

        <div>
          {engine === 'sql' && sql?.ok && sql.columns.length > 0 ? (
            <div className="h-56 overflow-auto rounded-lg border border-navy-100">
              <div className="bg-navy-50 text-[10px] text-navy-500 px-3 py-1.5 font-medium uppercase tracking-wide">
                {sql.columns.join('  ·  ')}
              </div>
              {sql.rows.map((r, i) => (
                <div key={i} className="px-3 py-1 border-t border-navy-50 font-mono text-[11px] text-navy-600">
                  {sql.columns.map(c => String(r[c] ?? '')).join('  |  ')}
                </div>
              ))}
            </div>
          ) : (
            <div className={`h-56 w-full rounded-lg font-mono text-xs p-4 overflow-auto whitespace-pre-wrap border ${
              result && !result.ok ? 'bg-red-50 border-red-200 text-red-600' : 'bg-navy-950 border-navy-800 text-green-300'
            }`}>
              {result?.error ? `✖ ${result.error}` : (result?.output || 'Output will appear here…')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}