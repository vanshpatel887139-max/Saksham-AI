-- SakshamAI — 002_rls.sql
-- Supabase ONLY. Requires the `auth` schema, so it is kept separate from
-- 001_schema.sql, which also runs on plain PostgreSQL.
--
-- =====================================================================
-- READ THIS BEFORE ASSUMING THESE POLICIES ARE ENFORCING ANYTHING
-- =====================================================================
--
-- The backend connects with DATABASE_URL as the Supabase *table owner*
-- (`postgres.<project-ref>`), and PostgreSQL exempts a table's owner from its
-- own RLS policies. So these policies are CORRECT but INACTIVE for the API.
--
-- That is deliberate. Enforcement today lives in FastAPI, in the
-- `require_learner` / `require_admin` / `require_self_or_admin` dependencies
-- in backend/auth_tokens.py. The reason RLS cannot be the boundary is
-- structural, not a shortcut: auth.uid() reads the `sub` claim that Supabase's
-- PostgREST layer injects into the Postgres session. A direct psycopg
-- connection has no such session variable, so auth.uid() is always NULL and
-- every per-user policy would deny all rows. Making RLS live would mean
-- routing all 108 queries through PostgREST, losing multi-statement
-- transactions (see the `_persist_questions` DELETE + 18 INSERTs in
-- routers/assessment.py) and rewriting the SQL as query chains.
--
-- The payoff for keeping them: the moment a frontend is given the anon key
-- and queries Supabase directly, these policies are already correct and
-- nothing leaks. They are the safety net, not the lock.
--
-- The original spec's example policy was:
--     USING (auth.uid()::text = employee_id)
-- which is broken — auth.uid() casts to a value like 'a1b2c3d4-...', which
-- can never equal an employee code such as 'GOV-2021-0847'. It would have
-- silently denied every row. These policies go through users.auth_id
-- instead, which is an actual uuid column.

BEGIN;

-- ------------------------------------------------------------------ helpers
-- SECURITY DEFINER so the policy can read users without recursing through
-- users' own policy. Returns false rather than raising when there is no JWT.
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin', FALSE);
$$;

-- The learner row belonging to the calling JWT, or NULL.
CREATE OR REPLACE FUNCTION public.current_learner_id()
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT u.id FROM users u WHERE u.auth_id = auth.uid();
$$;

-- ------------------------------------------------------------------ reference data
-- Public catalogue: every signed-in user may read it, nobody may write it.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['competencies', 'role_requirements', 'courses', 'labs']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_read', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR SELECT TO authenticated USING (true)', t || '_read', t
        );
    END LOOP;
END $$;

-- ------------------------------------------------------------------ identity
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_self ON users;
CREATE POLICY users_self ON users
    FOR ALL TO authenticated
    USING (auth_id = auth.uid() OR public.is_admin())
    WITH CHECK (auth_id = auth.uid() OR public.is_admin());

-- ------------------------------------------------------------------ learner data
-- Every table keyed by user_id: a row is visible when it belongs to the
-- calling learner, or to any admin.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'competency_scores', 'assessment_questions', 'course_enrollments',
        'module_progress', 'quizzes', 'notifications', 'activities',
        'score_update_log', 'advisor_messages'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_scoped', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO authenticated '
            'USING (user_id = public.current_learner_id() OR public.is_admin()) '
            'WITH CHECK (user_id = public.current_learner_id() OR public.is_admin())',
            t || '_scoped', t
        );
    END LOOP;
END $$;

-- Child of quizzes; reach the owner through the parent row.
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quiz_questions_scoped ON quiz_questions;
CREATE POLICY quiz_questions_scoped ON quiz_questions
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM quizzes q
            WHERE q.id = quiz_questions.quiz_id
              AND (q.user_id = public.current_learner_id() OR public.is_admin())
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM quizzes q
            WHERE q.id = quiz_questions.quiz_id
              AND (q.user_id = public.current_learner_id() OR public.is_admin())
        )
    );

-- ------------------------------------------------------------------ bookkeeping
-- seed_meta holds only the applied-migration list and the seed version. It
-- carries no user data and no credential, but Supabase's default privileges
-- grant `anon` and `authenticated` SELECT on new tables in `public`, so
-- without this line it would be the one relation in the schema readable by an
-- unauthenticated caller.
--
-- RLS is enabled with NO policy on purpose: an empty policy set is what makes
-- the table deny-by-default, so both roles read zero rows. The backend
-- connects as the table owner and therefore bypasses RLS, so the migration
-- runner and /api/health still read `version` normally.
ALTER TABLE IF EXISTS seed_meta ENABLE ROW LEVEL SECURITY;

COMMIT;

-- =====================================================================
-- HOW TO VERIFY (requires the frontend to hold the anon key, i.e. PostgREST)
-- =====================================================================
-- 1. Set an admin app_metadata role on one seeded account:
--      UPDATE auth.users
--         SET raw_app_meta_data = '{"role":"admin"}'
--       WHERE email = 'admin@sakshamai.demo';
-- 2. Sign in as learner A, copy the access token. In the SQL editor run:
--      SET LOCAL role authenticated;
--      SET request.jwt.claims = '{"sub":"<A-auth-uuid>","role":"authenticated"}';
--      SELECT count(*) FROM competency_scores;   -- only A's rows
--    Re-run with B's uuid: A's rows are gone. Swap in admin-1's uuid and the
--    full organisation appears.
-- =====================================================================
