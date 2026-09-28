# Official Statistics Dataset

SakshamAI ships a real, citable dataset so the labs teach on genuine numbers
rather than invented rows. This document records what the data actually is,
where it came from, and what would be wrong about claiming otherwise.

## What the data is

**World Bank Open Data for India (ISO3 `IND`), 16 indicators, 766 observations,
1960-2025**, across seven categories.

| Category | Indicators | Examples |
|---|---|---|
| Economy | 4 | GDP, GDP per capita, GDP growth, manufacturing share of GDP |
| Health | 4 | Life expectancy, fertility, under-5 mortality, health expenditure |
| Education | 3 | Adult literacy (total/female), secondary enrolment |
| Labour | 2 | Unemployment, female labour-force participation |
| Demography | 1 | Population |
| Digital | 1 | Individuals using the internet |
| Agriculture | 1 | Food production index |

Source: <https://data.worldbank.org/country/india> — published under
**CC BY 4.0**.

## What the data is *not*

This matters more than the table above, so it is stated plainly:

- **It is not "Indian government data".** The World Bank republishes figures
  that originate with the national statistical system and adds its own
  estimates. The GDP figures come from "Country official statistics, National
  Statistical Organizations and/or Central Banks"; life expectancy comes from
  UN World Population Prospects; literacy from UNESCO; labour from ILO;
  health from WHO. Every indicator carries a `provenance` column with the
  originating body precisely so a reader is not told the wrong thing about
  where a number came from.
- **It is not NSS survey microdata.** There is no unit-level data here. If the
  app needs household-level NSS records, that requires registering at
  `microdata.gov.in` and is a different exercise.
- **It is not from `nssta.gov.in`.** That domain is the National Statistical
  Systems Training Academy. It runs training programmes and publishes no
  datasets. The lab seed previously credited survey rounds to "NSSTA", which
  attributed invented numbers to a real government body; migration
  `005_lab_dataset_provenance.sql` removes that.

### Why not the authentic Indian sources

| Source | Status | Reason |
|---|---|---|
| `microdata.gov.in` | Gated | Registration and approval required for NSS unit-level data |
| `data.gov.in` | Gated | The catalog API requires an `Authorization` key; direct file downloads return HTTP 403 without one |
| MoSPI reports | PDF only | Published as PDFs, not machine-readable |
| World Bank API | **Used** | No key, no registration, real citable statistics |

If a data.gov.in API key becomes available, the loader in
`scripts/load_worldbank.py` is the right place to add a second source; the two
tables and the `/api/stats` contract do not need to change.

## Licence obligations

CC BY 4.0 requires attribution. This is enforced in the data layer, not left to
a README:

- Every response from `/api/stats` stamps `source`, `source_url`, `license` and
  `provenance` onto every indicator. A caller cannot render a number without
  also having the means to say where it is from.
- The SQL lab renders a visible source line above the runner.
- `docs/` and any public presentation must carry the credit line:
  *"Source: World Bank Open Data (CC BY 4.0)"* plus the per-series provenance.

## Loading and refreshing

```bash
# Requires migration 004 to be applied; the backend applies migrations on start.
backend/.venv/bin/python scripts/load_worldbank.py --dry-run   # fetch, report, write nothing
backend/.venv/bin/python scripts/load_worldbank.py             # load / refresh
```

The loader is idempotent — both tables are upserted on their natural keys, so
re-running after a World Bank release updates values in place and leaves row
counts stable. It prints a per-indicator summary and exits non-zero if any
indicator fails to fetch.

Three plausible-looking codes were rejected during development because the World
Bank returns `Invalid value` for India on them, which would have produced an
empty indicator that looked successfully loaded:

| Rejected code | Actual code used |
|---|---|
| `SP.LIT.TOTL.IN` (literacy) | `SE.ADT.LITR.ZS` |
| `SP.TOTL.TFRT.IN` (fertility) | `SP.DYN.TFRT.IN` |
| `SL.ISV.IFRM.ZS` (informal employment) | none — no India series exists |

## The trend assertions

The loader ends with `verify_trends()`, which reads back from the database and
asserts that series move in the direction the real world requires (life
expectancy up, child mortality down, literacy up, population up, and so on).
Nine series are asserted; the load exits non-zero if any fails.

This exists because of a bug that shipped a plausible-looking but wrong table.
The loader sorted `years` ascending while zipping against the API's
newest-first `value` list, so every year was paired with a different year's
number. The result was fully populated, internally consistent, and
individually plausible — but life expectancy *fell* from 72 to 45, child
mortality *rose*, and the population *shrank*. No count, constraint or type
check would have caught it. Only a directional assertion did, so it now runs on
every load rather than as a one-off manual check.

## API

All routes require a signed-in user (`current_identity`). The dataset is public
reference data, but an unsigned visitor should not be able to enumerate it, and
the tables are the lab's teaching material.

| Route | Returns |
|---|---|
| `GET /api/stats/indicators?category=` | Catalogue, with year span and observation count per indicator |
| `GET /api/stats/categories` | Indicator and observation counts per category |
| `GET /api/stats/series/{code}?start_year=&end_year=` | One indicator's observations, oldest first |
| `GET /api/stats/compare?codes=a,b,c&base_year=` | Several series rebased to 100 at a common year |

`compare` picks the **latest year present in every requested series** when
`base_year` is omitted, so a sparse series is never silently anchored to a year
its neighbours have not reached. Years a series lacks come back as `null` with
`indexed: null` rather than being dropped or interpolated, so a chart shows the
gap instead of drawing a line across it.

## Schema

`supabase/migrations/004_worldbank_indicators.sql`

- `stat_indicators` — keyed by World Bank indicator code. Carries the
  attribution metadata described above.
- `stat_observations` — `(indicator_code, year)` primary key, `value NOT NULL`.

The `NOT NULL` constraint is load-bearing. The loader skips nulls so that "no
observation published for this year" can never be stored as a `0`, which the SQL
lab would then present as a measured zero.

Both tables have RLS enabled with the same `authenticated`-read policy as the
catalogue tables, and `anon` is deliberately excluded. As with the rest of the
schema, the backend connects as the table owner and bypasses RLS; these
policies are the safety net for the day a frontend is handed the anon key.

## How the labs use it

- **SQL Lab** — fetches three real series and installs them into the client-side
  sandbox via `setDatasetTables()`, so `SELECT` / `WHERE` / `ORDER BY` /
  aggregates run against real rows. The sandbox is a mini in-browser SQL engine
  (`src/services/sqlEngine.ts`); it does **not** execute SQL against the live
  database, since that would mean letting a browser run arbitrary queries
  against a real Postgres.
- **Python Lab** — exercises reference the same series.
- **Viz / GIS Labs** — still use their own literal sample arrays and are
  labelled in the UI as illustrative sample values, not official statistics.
  They are not wired to the API.

The `sqlEngine.ts` fallback tables are placeholders, shown only on first paint
or when the API is unreachable, and the lab shows a warning when it is running
on them. Statistics code must not silently substitute invented data.

## A note on the SQL engine

`WHERE` clauses that the engine cannot parse now **raise an error**. They used
to be silently ignored, so `WHERE indicator_code = 'SP.DYN.LE00.IN'` returned
every indicator's rows and the learner saw plausible output and concluded the
filter worked. On a teaching tool, quietly returning wrong data is worse than
refusing, so unparseable clauses are rejected with a message naming the
supported syntax. String equality (`column = 'text'`) and `AND`-joined
conditions are supported, which is what makes filtering by indicator code work.
