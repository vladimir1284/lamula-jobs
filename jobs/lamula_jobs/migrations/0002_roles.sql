-- Roles de servicio. NOLOGIN a propósito: la contraseña es del despliegue (`ALTER ROLE ... LOGIN PASSWORD`).
--
-- jobs_api   : dueño de los schemas de job; crea y borra schemas y roles; todo en `control`.
-- jobs_runner: solo lo que necesita para tomar un job y contar su progreso. No crea schemas, no ve
--              tokens de acceso y no puede cambiar la cuota ni la caducidad de nadie.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jobs_api') THEN
        CREATE ROLE jobs_api NOLOGIN CREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jobs_runner') THEN
        CREATE ROLE jobs_runner NOLOGIN;
    END IF;
    EXECUTE format('GRANT CREATE, CONNECT ON DATABASE %I TO jobs_api', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO jobs_runner', current_database());
END $$;

GRANT pg_signal_backend TO jobs_api;  -- cerrar las conexiones de un rol de job antes de borrarlo

GRANT USAGE ON SCHEMA control TO jobs_api, jobs_runner;
GRANT ALL ON ALL TABLES IN SCHEMA control TO jobs_api;

GRANT SELECT ON control.jobs, control.job_inputs TO jobs_runner;
GRANT UPDATE (state, claimed_by, claimed_at, heartbeat_at, attempts, error, started_at, finished_at) ON control.jobs TO jobs_runner;
