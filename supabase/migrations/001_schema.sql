-- SakshamAI — 001_schema.sql
-- Target: Supabase PostgreSQL (Supavisor session pooler, port 5432)
--
-- Replaces backend/sakshamai.db (SQLite). Applied automatically at backend
-- startup by database.py::init_db(), or paste into the Supabase SQL editor.
--
-- DESIGN NOTES / DEVIATIONS FROM THE ORIGINAL SPEC
-- -----------------------------------------------
-- 1. The table is `users`, not `learners`. It holds an admin as well as
--    learners, so `users` is the accurate name, and renaming it would churn
--    100+ call sites plus the public API (`/api/users/{id}`) for no gain.
--    The existing `role` column ('learner' | 'admin') already carries the
--    admin flag, so a separate `is_admin` boolean would be redundant.
--
-- 2. Text primary keys, not uuid. Every request is server-side and the
--    frontend contract already uses ids like 'learner-1' / 'course-1'.
--    uuid would force a mapping layer across the whole API surface and buy
--    nothing, because the access-control boundary is FastAPI, not the database
--    (see 002_rls.sql for why RLS is not the enforcement mechanism today).
--
-- 3. `competencies` is kept as a real lookup table rather than inlining
--    `competency text`. The whole app keys on slugs ('survey-design'):
--    288 role_requirements rows and every competencyId in the frontend
--    contract depend on them. Free-text names would break all of it.
--
-- 4. `taken_at` and `date` stay `text`, deliberately. They are already
--    'YYYY-MM-DDTHH:MM:SSZ' / 'YYYY-MM-DD' strings on the wire, and the
--    frontend compares them directly. Converting to timestamptz would make
--    psycopg return datetime objects and FastAPI would emit '+00:00' instead
--    of 'Z', silently changing the contract. `quizzes.created_at` is the only
--    real timestamp, and it is used for ordering only, never serialized.
--
-- 5. `labs.exercises` stays `text`, deliberately, so that routers/labs.py
--    needs no change at all. A CHECK constraint casts it to jsonb to
--    guarantee it is still well-formed JSON. The cost is that this one column
--    gets no JSON operators or indexing; nothing queries it that way.
--
-- 6. `learner_directory` is a VIEW that replaces the old `org_learners`
--    table. org_learners held nine fictional officials that shared no rows
--    with `users`, which is why the admin dashboard reported hardcoded
--    numbers. The view derives the same column shape from real learners.
--
-- The `auth` schema is intentionally NOT referenced here so this file also
-- runs on a plain PostgreSQL instance (CI, local dev) with no Supabase.

BEGIN;

-- ------------------------------------------------------------------ reference
CREATE TABLE IF NOT EXISTS competencies (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_requirements (
    role          TEXT NOT NULL,
    competency_id TEXT NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
    level         INTEGER NOT NULL,
    PRIMARY KEY (role, competency_id)
);

CREATE TABLE IF NOT EXISTS courses (
    id             TEXT PRIMARY KEY,
    course_code    TEXT,
    title          TEXT NOT NULL,
    provider       TEXT NOT NULL,
    description    TEXT,
    skills_covered JSONB NOT NULL DEFAULT '[]'::jsonb,
    difficulty     TEXT,
    duration       TEXT,
    language       TEXT,
    rating         DOUBLE PRECISION DEFAULT 0,
    thumbnail      TEXT,
    category       TEXT,
    modules        JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS labs (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    category     TEXT,
    description TEXT,
    icon        TEXT,
    exercises   TEXT,
    CONSTRAINT labs_exercises_is_json_array
        CHECK (exercises IS NULL OR jsonb_typeof(exercises::jsonb) = 'array')
);

-- ------------------------------------------------------------------ identity
CREATE TABLE IF NOT EXISTS users (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    employee_id        TEXT,
    designation        TEXT,
    department         TEXT,
    role               TEXT NOT NULL DEFAULT 'learner',
    -- The role the learner is upskilling towards ("Data Analyst"), as opposed
    -- to `designation`, which is the job they currently hold. Named
    -- `target_role` rather than `current_role` because CURRENT_ROLE is a
    -- reserved word in PostgreSQL and the latter will not parse unquoted.
    target_role        TEXT,
    education          TEXT,
    experience         INTEGER DEFAULT 0,
    career_goal        TEXT,
    previous_training  TEXT,
    preferred_language TEXT DEFAULT 'English',
    profile_completed  BOOLEAN DEFAULT FALSE,
    -- Directory/organisational status shown on the admin dashboard. Derived
    -- from the seed rather than computed, because "is this officer currently
    -- active" is a real HR fact the app has no other source for.
    status             TEXT NOT NULL DEFAULT 'Active',
    -- Supabase Auth link. Deliberately has NO foreign key to auth.users:
    -- the recommended Supabase pattern is to avoid FKs into auth, and a
    -- plain uuid also keeps this file runnable outside Supabase.
    auth_id            UUID,
    -- Login identity. Synthetic `@sakshamai.demo` addresses for the seeded
    -- demo accounts, so the demo never collides with a real inbox and no
    -- mail is ever delivered to them. Unique because Supabase Auth keys
    -- accounts by email and the link back to a learner row is made on it.
    email              TEXT UNIQUE
);

-- ------------------------------------------------------------------ learning
CREATE TABLE IF NOT EXISTS competency_scores (
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    competency_id    TEXT NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
    level            INTEGER NOT NULL,
    source           TEXT DEFAULT 'default',
    accuracy         DOUBLE PRECISION,
    self_rated_level INTEGER,
    tested_at        TEXT,
    PRIMARY KEY (user_id, competency_id)
);

CREATE TABLE IF NOT EXISTS assessment_questions (
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    test_id         TEXT NOT NULL,
    taken_at        TEXT NOT NULL,
    position        INTEGER NOT NULL,
    question_id     TEXT NOT NULL,
    competency_id   TEXT NOT NULL,
    competency_name TEXT,
    prompt          TEXT NOT NULL,
    options         JSONB NOT NULL DEFAULT '[]'::jsonb,
    correct_index   INTEGER NOT NULL,
    chosen_index    INTEGER,
    difficulty      INTEGER NOT NULL DEFAULT 1,
    explanation     TEXT,
    PRIMARY KEY (user_id, test_id, position)
);

CREATE TABLE IF NOT EXISTS course_enrollments (
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id   TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    progress    INTEGER DEFAULT 0,
    enrolled_at TEXT DEFAULT (CURRENT_DATE::text),
    PRIMARY KEY (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS module_progress (
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id    TEXT NOT NULL,
    module_title TEXT,
    completed_at TEXT DEFAULT (CURRENT_DATE::text),
    PRIMARY KEY (user_id, course_id, module_title)
);

CREATE TABLE IF NOT EXISTS quizzes (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT,
    date            TEXT DEFAULT (CURRENT_DATE::text),
    score           INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    -- Internal ordering key. The old query sorted by SQLite's implicit
    -- `rowid`, which has no PostgreSQL equivalent; created_at replaces it.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id              TEXT PRIMARY KEY,
    quiz_id         TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question        TEXT,
    options         JSONB NOT NULL DEFAULT '[]'::jsonb,
    correct_answer  INTEGER NOT NULL,
    user_answer     INTEGER,
    explanation     TEXT,
    difficulty      TEXT,
    source_excerpt  TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id      TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    message TEXT,
    type    TEXT DEFAULT 'info',
    date    TEXT,
    is_read BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS activities (
    id      TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    action  TEXT,
    detail  TEXT,
    date    TEXT,
    icon    TEXT
);

-- ------------------------------------------------------------------ new tables
-- Audit trail for automated competency-level changes. Populated by the
-- course-completion handler in routers/courses.py, so a learner's level
-- moving 2 -> 3 because they finished a course is distinguishable from a
-- level earned by passing the competency test.
CREATE TABLE IF NOT EXISTS score_update_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    competency_id TEXT NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
    previous_level INTEGER,
    new_level      INTEGER,
    source         TEXT NOT NULL DEFAULT 'course',
    reference_id   TEXT,
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Advisor chat history. Previously chat lived only in React state, so a page
-- refresh lost the whole conversation.
CREATE TABLE IF NOT EXISTS advisor_messages (
    id         BIGSERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed bookkeeping: lets init_db() skip re-seeding on every boot.
CREATE TABLE IF NOT EXISTS seed_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ------------------------------------------------------------------ view
-- Replaces the old `org_learners` table. Same column shape, but every value
-- is computed from real learner rows, so the admin dashboard reports the same
-- thing the rest of the app sees.
CREATE OR REPLACE VIEW learner_directory AS
SELECT
    u.name,
    u.department,
    u.target_role AS job_role,
    COALESCE(ROUND(AVG(cs.level)::numeric, 1), 0)::double precision AS competency,
    COALESCE((
        SELECT COUNT(*)
        FROM role_requirements rr
        LEFT JOIN competency_scores cs2
               ON cs2.competency_id = rr.competency_id
              AND cs2.user_id = u.id
        WHERE rr.role = u.target_role
          AND COALESCE(cs2.level, 0) < rr.level
    ), 0)::bigint AS gaps,
    COALESCE((
        SELECT COUNT(*)
        FROM course_enrollments ce
        WHERE ce.user_id = u.id AND ce.progress >= 100
    ), 0)::bigint AS completed,
    u.status
FROM users u
LEFT JOIN competency_scores cs ON cs.user_id = u.id
WHERE u.role = 'learner'
GROUP BY u.id, u.name, u.department, u.target_role, u.status;

-- Hours of study a completed module represents, read from the course's own
-- modules jsonb. Durations are authored as '2h', '1.5h', '30m', '45m', so the
-- unit has to be honoured rather than parsed as a bare number. This is what
-- makes the admin dashboard's learning-hours figure real instead of a literal.
CREATE OR REPLACE FUNCTION module_duration_hours(p_course_id TEXT, p_module_title TEXT)
RETURNS DOUBLE PRECISION
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((
        SELECT CASE
            WHEN m ->> 'duration' LIKE '%h%'
                THEN (regexp_replace(m ->> 'duration', '[^0-9.]', '', 'g'))::double precision
            WHEN m ->> 'duration' LIKE '%m%'
                THEN (regexp_replace(m ->> 'duration', '[^0-9.]', '', 'g'))::double precision / 60
            ELSE 0
        END
        FROM courses c, jsonb_array_elements(c.modules) m
        WHERE c.id = p_course_id
          AND m ->> 'title' = p_module_title
        LIMIT 1
    ), 0);
$$;

-- ------------------------------------------------------------------ indexes
CREATE INDEX IF NOT EXISTS idx_competency_scores_user      ON competency_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_user   ON assessment_questions(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_user            ON course_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_module_progress_user        ON module_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_user_created        ON quizzes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz         ON quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user          ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_activities_user            ON activities(user_id);
CREATE INDEX IF NOT EXISTS idx_score_update_log_user       ON score_update_log(user_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_advisor_messages_user       ON advisor_messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_users_auth_id               ON users(auth_id);
CREATE INDEX IF NOT EXISTS idx_courses_gin                 ON courses USING GIN (skills_covered);

COMMIT;
