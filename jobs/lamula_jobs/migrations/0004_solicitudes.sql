-- Solicitudes de acceso (F4, D20): el formulario público las guarda, el dueño las aprueba o rechaza.
-- El enlace del correo de aprobación se guarda solo como sha256, igual que los tokens.
CREATE TABLE control.access_requests (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    org TEXT NOT NULL,
    cargo TEXT,
    interes TEXT[] NOT NULL,
    radar TEXT,
    comentario TEXT,
    ip_sha256 TEXT,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    review_sha256 TEXT NOT NULL UNIQUE,
    review_expires_at TIMESTAMPTZ NOT NULL,
    notified_at TIMESTAMPTZ,                   -- correo al dueño enviado; NULL = hay que mirar `jobs-admin requests`
    token_id TEXT REFERENCES control.access_tokens (id),
    CONSTRAINT solicitud_aprobada_con_token CHECK ((state = 'approved') = (token_id IS NOT NULL))
);
-- una sola pendiente por correo: reenviar el formulario no llena la bandeja
CREATE UNIQUE INDEX access_requests_una_pendiente ON control.access_requests (lower(email)) WHERE state = 'pending';
CREATE INDEX access_requests_ip ON control.access_requests (ip_sha256, created_at);

GRANT ALL ON control.access_requests TO jobs_api;
