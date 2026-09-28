-- SakshamAI — 004_worldbank_indicators.sql
-- Official-statistics reference dataset (World Bank Open Data, India / IND).
--
-- WHY THIS IS PUBLIC REFERENCE DATA, NOT USER DATA
-- These two tables hold only published national statistics plus the citation
-- metadata needed to attribute them. There is no user_id, no auth linkage, and
-- no column that can identify a person, so the RLS treatment matches the
-- catalogue tables in 002_rls.sql: any signed-in user may read, nobody may write.
--
-- SOURCE AND LICENCE
-- World Bank Open Data, https://data.worldbank.org/country/india, published
-- under CC BY 4.0. The World Bank republishes figures that originate with the
-- national statistical system, plus its own estimates. Attribution is required
-- by the licence, so `source` / `source_url` / `license` are stored per
-- indicator rather than being left in a README nobody reads. If SakshamAI is
-- ever presented publicly, the UI must render this attribution alongside the
-- numbers — that is a licence obligation, not a nicety.
--
-- WHAT "OFFICIAL" DOES AND DOES NOT MEAN HERE
-- A user who reads this app as "Indian government data" would be misled. This
-- is World Bank data for India: real, citable, and mostly drawn from official
-- sources (NSS, MoSPI, Registrar General, NCRB) but harmonised, revised and
-- partly modelled by the World Bank. The per-indicator `provenance` column
-- records what the World Bank itself says the source is, so a reader can tell
-- an official survey statistic from a World Bank estimate.

BEGIN;

-- ------------------------------------------------------------------ schema
-- Keyed by the World Bank indicator code, which is stable and is what the
-- loader upserts on, so a re-run updates rows in place instead of duplicating.
CREATE TABLE IF NOT EXISTS stat_indicators (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit        TEXT,
    -- What the World Bank lists as the originating source, e.g. "International
    -- Labour Organization" or "UNESCO Institute for Statistics".
    provenance  TEXT,
    source      TEXT NOT NULL DEFAULT 'World Bank Open Data',
    source_url  TEXT NOT NULL,
    license     TEXT NOT NULL DEFAULT 'CC BY 4.0',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per (indicator, year). NULL values are never inserted: the loader
-- skips nulls so "no observation" cannot be misread as a measured zero by the
-- SQL lab, which is the single most important correctness property here.
CREATE TABLE IF NOT EXISTS stat_observations (
    indicator_code TEXT NOT NULL REFERENCES stat_indicators(code) ON DELETE CASCADE,
    year           INT  NOT NULL CHECK (year BETWEEN 1800 AND 2200),
    value          NUMERIC,
    -- Guard against the failure mode the lab must never display: a stored NULL.
    CONSTRAINT stat_observations_value_not_null CHECK (value IS NOT NULL),
    PRIMARY KEY (indicator_code, year)
);

-- The PK indexes (indicator_code, year), which serves the lab's dominant query
-- ("one indicator, all years"). This covers the other direction, used by the
-- cross-indicator comparison endpoint.
CREATE INDEX IF NOT EXISTS idx_stat_observations_year
    ON stat_observations(year);

CREATE INDEX IF NOT EXISTS idx_stat_indicators_category
    ON stat_indicators(category);

-- ------------------------------------------------------------------ RLS
-- Same posture as the `competencies` / `courses` / `labs` catalogue block in
-- 002_rls.sql. `anon` is deliberately NOT included: the tables are readable
-- through the app's own authenticated API, and nothing here should be
-- world-readable via the anon key. The backend connects as the table owner and
-- bypasses RLS regardless; these policies are the safety net that becomes live
-- the moment a frontend is handed the anon key.
-- The schema is written as a literal `public.` prefix rather than being folded
-- into the %I argument on purpose. format('%I', 'public.t') quotes the whole
-- string as a SINGLE identifier, yielding the relation "public.t" — a table
-- literally named that, in the first schema of search_path — which fails with
-- `relation "public.t" does not exist` rather than reporting anything useful.
-- `public.%I` with a bare table name is the correct spelling.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['stat_indicators', 'stat_observations']
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_read', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (true)',
            t || '_read', t
        );
    END LOOP;
END $$;

COMMIT;

-- =====================================================================
-- HOW TO VERIFY
-- =====================================================================
-- 1. Row counts:
--      SELECT count(*) FROM stat_indicators;      -- 16
--      SELECT count(*) FROM stat_observations;    -- ~700, varies by release
-- 2. No stored NULLs, as the CHECK constraint promises:
--      SELECT count(*) FROM stat_observations WHERE value IS NULL;  -- 0
-- 3. Attribution is present for every indicator:
--      SELECT count(*) FROM stat_indicators WHERE license IS NULL;  -- 0
-- 4. Lab-visible sanity check, life expectancy should trend upward:
--      SELECT year, value FROM stat_observations
--       WHERE indicator_code = 'SP.DYN.LE00.IN' AND year IN (1960, 1990, 2024)
--       ORDER BY year;
-- =====================================================================
