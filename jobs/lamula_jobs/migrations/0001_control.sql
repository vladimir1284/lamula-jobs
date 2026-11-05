-- Schema de control del plano demo (F2). Solo vive en la base lamula_demo; nada de esto toca el
-- contrato de datos del pipeline, que se aplica aparte, tal cual, en el schema de cada job (D4).
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE control.tiers (
    name TEXT PRIMARY KEY,
    max_volumes INTEGER,            -- NULL = sin tope
    max_jobs_total INTEGER,
    max_jobs_active INTEGER NOT NULL,
    retention_days INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    max_bytes BIGINT                -- propuesta pendiente de aprobar (docs/operacion/acceso-y-cuotas.md)
);

INSERT INTO control.tiers VALUES
    ('demo',       12,   2,    1,  7, 0, NULL),
    ('extendido',  24,   5,    1, 14, 0, NULL),
    ('evaluacion', 48,  10,    2, 30, 1, NULL),
    ('interno',   NULL, NULL,  2, 90, 1, NULL);

CREATE TABLE control.access_tokens (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    org TEXT,
    token_sha256 TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL REFERENCES control.tiers (name),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    note TEXT
);

CREATE TABLE control.jobs (
    id TEXT PRIMARY KEY,                       -- ulid en minúsculas; schema y rol son job_<id>
    token_id TEXT NOT NULL REFERENCES control.access_tokens (id),
    state TEXT NOT NULL CHECK (state IN ('creating','queued','claimed','ingesting','ready','failed','cancelled','expired')),
    source TEXT NOT NULL DEFAULT 'staging',
    icao TEXT NOT NULL,
    vol_from TIMESTAMPTZ NOT NULL,
    vol_to TIMESTAMPTZ NOT NULL,
    n_volumes INTEGER NOT NULL,
    total_bytes BIGINT NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    result_token_sha256 TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    resources_dropped_at TIMESTAMPTZ           -- schema, rol y objetos ya borrados
);
CREATE INDEX idx_jobs_queue ON control.jobs (priority DESC, created_at) WHERE state = 'queued';
CREATE INDEX idx_jobs_token ON control.jobs (token_id);

CREATE TABLE control.job_inputs (
    job_id TEXT NOT NULL REFERENCES control.jobs (id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    staging_key TEXT NOT NULL,
    source_key TEXT,
    bytes BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (job_id, seq)
);
