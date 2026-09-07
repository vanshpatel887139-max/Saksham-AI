/**
 * Mini SQL engine over the sample official-statistics dataset.
 *
 * Shared by the Virtual Labs SQL sandbox and SQL course modules.
 * Supports SELECT with WHERE, ORDER BY and SUM/AVG/COUNT aggregates.
 */

export type Row = Record<string, string | number>;

export const DB: Record<string, Row[]> = {
  districts: [
    { id: 1, name: 'Alwar', state: 'Rajasthan', population: 3674179, literacy: 70.7 },
    { id: 2, name: 'Mysuru', state: 'Karnataka', population: 3054822, literacy: 72.6 },
    { id: 3, name: 'Nashik', state: 'Maharashtra', population: 6109052, literacy: 80.9 },
    { id: 4, name: 'Ludhiana', state: 'Punjab', population: 3498739, literacy: 82.2 },
    { id: 5, name: 'Varanasi', state: 'Uttar Pradesh', population: 3676841, literacy: 70.3 },
    { id: 6, name: 'Thrissur', state: 'Kerala', population: 3121200, literacy: 95.1 },
  ],
  samples: [
    { district_id: 1, households_surveyed: 420, dept: 'NSSO' },
    { district_id: 2, households_surveyed: 515, dept: 'Census' },
    { district_id: 3, households_surveyed: 310, dept: 'NSSTA' },
    { district_id: 4, households_surveyed: 600, dept: 'NSSO' },
    { district_id: 5, households_surveyed: 275, dept: 'Census' },
    { district_id: 6, households_surveyed: 505, dept: 'NSSTA' },
  ],
};

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

    const whereIdx = up.indexOf('WHERE');
    let whereClause = '';
    if (whereIdx !== -1) {
      const end = up.indexOf('ORDER BY');
      whereClause = query.slice(whereIdx + 5, end !== -1 ? end : query.length).trim();
      const m = whereClause.match(/^\s*(\w+)\s*(>=|<=|=|>|<)\s*([\d.]+)\s*$/);
      if (m) {
        const [_, col, op, num] = m;
        const val = parseFloat(num);
        rows = rows.filter(r => {
          const v = r[col] as number;
          if (op === '>') return v > val;
          if (op === '<') return v < val;
          if (op === '>=') return v >= val;
          if (op === '<=') return v <= val;
          if (op === '=') return v === val || String(r[col]) === num;
          return true;
        });
      }
    }

    const orderIdx = up.indexOf('ORDER BY');
    if (orderIdx !== -1) {
      const orderRaw = query.slice(orderIdx + 8).trim();
      const om = orderRaw.match(/^(\w+)\s*(ASC|DESC)?$/i);
      if (om) {
        const col = om[1];
        const desc = (om[2] || 'ASC').toUpperCase() === 'DESC';
        rows = rows.sort((a, b) => desc ? (b[col] as number) - (a[col] as number) : (a[col] as number) - (b[col] as number));
      }
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