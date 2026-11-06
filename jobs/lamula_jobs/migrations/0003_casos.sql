-- D19: casos preparados. Se procesan una vez, no caducan y sus datos viven en otra base y otro bucket.
--
-- `destino = 'casos'` marca el job: el worker publica en la base y el bucket de casos, y no se le crea
-- schema ni roles (la base de casos es un schema `public` normal, con roles fijos). `caso` es el nombre
-- del caso preparado; solo puede haber uno vivo por nombre.
ALTER TABLE control.jobs ADD COLUMN destino TEXT NOT NULL DEFAULT 'demo' CHECK (destino IN ('demo', 'casos'));
ALTER TABLE control.jobs ADD COLUMN caso TEXT;
ALTER TABLE control.jobs ALTER COLUMN expires_at DROP NOT NULL;
ALTER TABLE control.jobs ADD CONSTRAINT jobs_caso_coherente CHECK ((destino = 'casos') = (caso IS NOT NULL));
ALTER TABLE control.jobs ADD CONSTRAINT jobs_caducidad_coherente CHECK ((destino = 'casos') = (expires_at IS NULL));
CREATE UNIQUE INDEX jobs_un_caso_vivo ON control.jobs (caso) WHERE caso IS NOT NULL AND state NOT IN ('failed', 'cancelled');
INSERT INTO control.tiers (name, max_volumes, max_jobs_total, max_jobs_active, retention_days, priority, max_bytes)
    VALUES ('casos', NULL, NULL, 5, 0, 0, NULL) ON CONFLICT (name) DO NOTHING;
