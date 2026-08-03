-- Turso / libSQL schema for the job-agent datastore.
-- Replaces the Google Sheet. job_id (SHA-256 of norm_company|norm_title|
-- norm_location) is the primary key, so re-scrapes upsert idempotently and
-- user-owned columns are never clobbered.

CREATE TABLE IF NOT EXISTS jobs (
    job_id             TEXT PRIMARY KEY,
    -- identity (immutable after creation)
    job_title          TEXT NOT NULL,
    company            TEXT NOT NULL,
    location           TEXT,
    -- system-writable (the daily agent may overwrite these)
    job_url            TEXT,
    source             TEXT,
    date_posted        TEXT,
    date_found         TEXT,
    relevance_score    INTEGER,
    role_type          TEXT,
    confidence         REAL,
    semantic_scored    INTEGER DEFAULT 0,
    archived           INTEGER DEFAULT 0,
    last_updated       TEXT,
    -- freeze switch (agent never overwrites a locked row)
    locked             INTEGER DEFAULT 0,
    -- user-owned (only the dashboard / email scan writes these)
    applied            INTEGER DEFAULT 0,
    date_applied       TEXT,
    application_status TEXT DEFAULT 'not_applied',
    priority           TEXT,
    notes              TEXT,
    -- latest actionable link surfaced from an application email
    action_type        TEXT,      -- 'assessment' | 'interview' | NULL
    action_url         TEXT,
    -- AI enrichment (populated lazily by the dashboard on first view)
    description        TEXT,
    summary            TEXT,      -- brief role summary
    company_summary    TEXT,
    skills             TEXT,      -- JSON array of skill strings
    enriched_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(application_status);
CREATE INDEX IF NOT EXISTS idx_jobs_applied ON jobs(applied);
CREATE INDEX IF NOT EXISTS idx_jobs_score   ON jobs(relevance_score);

-- Append-only history of status changes (rendered as the job's timeline).
CREATE TABLE IF NOT EXISTS status_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id           TEXT NOT NULL REFERENCES jobs(job_id),
    old_status       TEXT,
    new_status       TEXT,
    source           TEXT,        -- 'email' | 'manual' | 'system'
    email_id         TEXT,        -- Gmail message id (nullable)
    email_thread_url TEXT,
    confidence       REAL,
    reasoning        TEXT,
    action_type      TEXT,
    action_url       TEXT,
    needs_review     INTEGER DEFAULT 0,
    created_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_status_events_job ON status_events(job_id);
CREATE INDEX IF NOT EXISTS idx_status_events_review ON status_events(needs_review);

-- Dedupe/audit: which Gmail messages we've already classified.
CREATE TABLE IF NOT EXISTS email_matches (
    email_id          TEXT PRIMARY KEY,
    job_id            TEXT,
    classified_status TEXT,
    confidence        REAL,
    processed_at      TEXT
);

-- Search settings (migrated from the Settings tab; dashboard-editable).
-- Values are stored as strings and re-normalized by settings_reader.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Resume text for semantic scoring (single row, id = 1).
CREATE TABLE IF NOT EXISTS resume (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    content TEXT
);
