/**
 * Mini SQL engine over the official-statistics dataset.
 *
 * Shared by the Virtual Labs SQL sandbox and SQL course modules.
 * Supports SELECT with WHERE, ORDER BY and SUM/AVG/COUNT aggregates.
 *
 * THE TABLES BELOW ARE A FALLBACK, NOT THE DATA.
 * The real dataset is World Bank Open Data for India, fetched from
 * /api/stats and installed by setDatasetTables() at runtime. The literals here
 * only exist so the lab still renders and runs on a first paint, offline, or
 * when the API is down — they are a handful of hand-typed rows, not statistics,
 * and the UI labels them as such. Anything presented to a user as a data point
 * should come from the API.
 *
 * The previous fallback shipped six invented districts and credited three of
 * their survey rounds to "NSSTA". NSSTA is the National Statistical Systems
 * Training Academy and has never run a household survey, so the lab was
 * attributing fabricated numbers to a real government body. That is removed
 * rather than reworded.
 */

export type Row = Record<string, string | number>;

/** Mutable so setDatasetTables() can install the real dataset before use. */
export const DB: Record<string, Row[]> = {
  // Placeholder rows. Empty-shaped, clearly-labelled stand-ins for the real
  // indicator/observation tables below; overwritten on a successful fetch.
  indicators: [
    { code: 'SP.DYN.LE00.IN', name: 'Life expectancy at birth (years)', category: 'Health', unit: 'years' },
  ],
  observations: [
    { indicator_code: 'SP.DYN.LE00.IN', year: 1960, value: 45.61 },
    { indicator_code: 'SP.DYN.LE00.IN', year: 2024, value: 72.235 },
  ],
};

/**
 * Install real rows fetched from the API, replacing the fallback tables.
 *
 * Only the table names given are replaced, so a partial response (indicators
 * loaded, observations still pending) cannot leave the lab with no data at all.
 */
export function setDatasetTables(tables: Record<string, Row[]>) {
  for (const [name, rows] of Object.entries(tables)) {
    if (Array.isArray(rows) && rows.length > 0) DB[name] = rows;
  }
}

export interface RunSQLResult {
  rows: Row[];
  columns: string[];
  ok: boolean;
  message?: string;
}

export function runSQL(query: string): RunSQLResult {
  try {
    const up = query.toUpperCase();
    if (!up.includes('SELECT')) throw new Error('Only SELECT statements are supported');
    const fromMatch = query.match(/FROM\s+(\w+)/i);
    if (!fromMatch || !DB[fromMatch[1]]) throw new Error(`Unknown table: ${fromMatch?.[1] ?? ''}`);
    const table = DB[fromMatch[1]];
    const selectRaw = query.slice(query.toUpperCase().indexOf('SELECT') + 6, query.toUpperCase().indexOf('FROM'));
    const columns = selectRaw.split(',').map(c => c.trim());

  let rows = [...table];

  // ---- WHERE -------------------------------------------------------------
  // A WHERE clause the engine cannot parse must RAISE, never be ignored.
  //
  // This previously matched one narrow shape (a single numeric comparison) and
  // silently skipped the filter for anything else. On a SQL teaching tool that
  // is the worst available failure: `WHERE indicator_code = 'SP.DYN.LE00.IN'`
  // returned every indicator's rows, the learner saw plausible data, and
  // concluded the filter worked. Returning wrong data quietly is worse than
  // refusing, so an unrecognised clause is an error naming what was supported.
  const whereIdx = up.indexOf(' WHERE ');
  if (whereIdx !== -1) {
    const end = up.indexOf(' ORDER BY ', whereIdx);
    const whereClause = query.slice(whereIdx + 7, end !== -1 ? end : query.length).trim();

    // Each condition is `col op literal`, joined by AND. Literals are numbers
    // or single-quoted strings; string equality is what makes the statistics
    // tables usable, since selecting one indicator means matching its code.
    const condition = /^\s*(\w+)\s*(>=|<=|<>|!=|=|>|<)\s*('(?:[^']|'')*'|-?\d+(?:\.\d+)?)\s*$/;
    const predicates: { col: string; op: string; value: string | number }[] = [];

    for (const part of whereClause.split(/\s+AND\s+/i)) {
      const m = part.match(condition);
      if (!m) {
        throw new Error(
          `Cannot parse WHERE condition: "${part.trim()}". ` +
          `Supported: column > / < / >= / <= / = / <> number, or column = 'text', joined with AND.`,
        );
      }
      const raw = m[3];
      const value = raw.startsWith("'") ? raw.slice(1, -1).replace(/''/g, "'") : Number(raw);
      predicates.push({ col: m[1], op: m[2], value });
    }

    for (const p of predicates) {
      if (!(p.col in table[0])) {
        throw new Error(
          `Unknown column "${p.col}" in table ${fromMatch[1]}. Available: ${Object.keys(table[0]).join(', ')}`,
        );
      }
    }

    rows = rows.filter(r => predicates.every(p => {
      const raw = r[p.col];
      if (p.op === '=') return raw === p.value;
      if (p.op === '<>' || p.op === '!=') return raw !== p.value;
      if (typeof raw !== 'number' || typeof p.value !== 'number') {
        throw new Error(`Operator ${p.op} needs numbers; "${p.col}" is not numeric`);
      }
      if (p.op === '>') return raw > p.value;
      if (p.op === '<') return raw < p.value;
      if (p.op === '>=') return raw >= p.value;
      return raw <= p.value;
    }));
  }

  const orderIdx = up.indexOf(' ORDER BY ');
  if (orderIdx !== -1) {
    const end = up.indexOf(' LIMIT ', orderIdx);
    const orderRaw = query.slice(orderIdx + 10, end !== -1 ? end : query.length).trim();
    const om = orderRaw.match(/^(\w+)\s*(ASC|DESC)?$/i);
    if (!om) {
      throw new Error(`Cannot parse ORDER BY: "${orderRaw}". Supported: column [ASC|DESC].`);
    }
    const col = om[1];
    if (!(col in table[0])) {
      throw new Error(
        `Unknown column "${col}" in table ${fromMatch[1]}. Available: ${Object.keys(table[0]).join(', ')}`,
      );
    }
    const sign = (om[2] || 'ASC').toUpperCase() === 'DESC' ? -1 : 1;
    // Type-aware: the statistics tables mix numbers (year, value) with strings
    // (code, name). Subtracting two strings yields NaN, which silently leaves
    // the sort order unchanged instead of erroring.
    const sample = table.find(r => r[col] != null)?.[col];
    rows = rows.sort((a, b) => {
      const av = a[col];
      const bv = b[col];
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sign;
      return String(av ?? '').localeCompare(String(bv ?? '')) * sign;
    });
    void sample;
  }

    const agg = columns.some(c => /SUM\(|AVG\(|COUNT\(/i.test(c));
    if (agg) {
      const aggCol = columns[0];
      const colMatch = aggCol.match(/(SUM|AVG|COUNT)\(\s*(\w+|\*)\s*\)/i);
      if (colMatch) {
        const fn = colMatch[1].toUpperCase();
        const target = colMatch[2];
        const vals = target === '*' ? rows.map(() => 1) : rows.map(r => r[target] as number);
        let value = 0;
        if (fn === 'SUM') value = vals.reduce((a, b) => a + b, 0);
        else if (fn === 'AVG') value = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
        else value = vals.length;
        const label = aggCol.replace(/\s+/g, '');
        return { rows: [{ [label]: Number(value.toFixed(2)) }], columns: [label], ok: true };
      }
    }

    const selectAny = columns.includes('*');
    return {
      rows: rows.map(r => {
        if (selectAny) return r;
        const o: Row = {};
        columns.forEach(c => { if (c in r) o[c] = r[c]; });
        return o;
      }),
      columns: selectAny ? Object.keys(table[0]) : columns,
      ok: true,
    };
  } catch (e) {
    return { rows: [], columns: [], ok: false, message: (e as Error).message };
  }
}