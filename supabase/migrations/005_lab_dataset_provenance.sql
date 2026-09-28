-- SakshamAI — 005_lab_dataset_provenance.sql
-- Correct lab descriptions that misstate where their data comes from.
--
-- WHY A MIGRATION AND NOT AN EDIT TO 003_seed.sql
-- 003 has already been applied to the live database and every lab row is
-- written with ON CONFLICT DO NOTHING, so editing the seed file would change
-- nothing on any database that has already run it. A new migration is the only
-- thing that actually updates existing rows.
--
-- WHAT WAS WRONG
-- The seeded lab copy described data the app does not have:
--   lab-sql -> "Query a real district-level census dataset ... and JOIN"
--   lab-viz -> "literacy rates by district"
--   lab-gis -> "Visualize district data as a thematic map ... for official
--               statistics"
-- There is no district-level census dataset in this project. What existed was
-- six invented districts in src/services/sqlEngine.ts, and lab-sql's tables
-- additionally credited three survey rounds to "NSSTA" — the National
-- Statistical Systems Training Academy, which runs training and has never
-- fielded a household survey. Presenting invented numbers under a real
-- government body's name is the specific thing this migration removes.
--
-- WHAT REPLACES IT
-- The real dataset is World Bank Open Data for India, loaded by
-- scripts/load_worldbank.py into stat_indicators / stat_observations
-- (004_worldbank_indicators.sql) and served by /api/stats. The SQL lab now
-- fetches those rows at runtime, so its data needs no seed copy at all.
--
-- lab-viz and lab-gis keep their own literal preset arrays — they render
-- client-side charts and are not wired to the API — so their copy is corrected
-- to describe them as illustrative sample data. They must not be described as
-- official statistics, because they are not.
--
-- Attribution wording follows 004: World Bank figures, many originating with
-- the national statistical system, not "Indian government data".

BEGIN;

UPDATE labs
   SET description = 'Query real World Bank data for India with SELECT, WHERE, ORDER BY and aggregates. Live rows fetched from /api/stats.'
 WHERE id = 'lab-sql';

UPDATE labs
   SET description = 'Build a chart with your own numbers. Illustrative sample values, not official statistics — use the SQL lab for citable World Bank data.'
 WHERE id = 'lab-viz';

UPDATE labs
   SET description = 'Visualize district-level points as a thematic map to practise GIS concepts. Illustrative sample values, not official statistics.'
 WHERE id = 'lab-gis';

-- The Python lab never claimed official data, but it is the natural next step
-- after the SQL lab, so say plainly that it runs against the same real series.
UPDATE labs
   SET description = 'Run Python on the same real World Bank series loaded by the SQL lab. Practice filtering, aggregation and simple statistics.'
 WHERE id = 'lab-python';

-- Exercises for lab-viz / lab-gis still hold the old hand-typed district rows
-- in their JSON. The descriptions above now label them as illustrative, which
-- is the part a reader sees. Rewriting the arrays to mirror live data would
-- bake a snapshot of the World Bank series into a seed file and let it drift
-- out of date silently, so it is deliberately not done here.

COMMIT;

-- =====================================================================
-- HOW TO VERIFY
-- =====================================================================
--   SELECT id, description FROM labs ORDER BY id;
-- No description should still mention a census dataset, district literacy, or
-- NSSTA as a data source.
-- =====================================================================
