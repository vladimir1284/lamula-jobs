# Acceso y cuotas

Sin registro público y sin cuentas (D8). El prospecto pide acceso por correo, nosotros
emitimos un token a mano, y **el nivel del token decide cuánto cómputo recibe**. Quien pide más
—más volúmenes, más trabajos, más tiempo de conservación— recibe un token de nivel superior si
la petición lo justifica.

## Flujo

1. La página pública explica el demo y muestra un formulario corto: correo, organización, qué
   quiere ver. Protegido con Turnstile.
2. Llega el correo. Lo valoramos.
3. Emitimos el token: `jobs-admin issue --email <correo> --tier <nivel> --note "<contexto>"`.
   El token se muestra **una sola vez**; en la base queda solo su `sha256`.
4. Se lo mandamos por correo con el enlace del demo. El cliente lo pega una vez y el navegador
   lo guarda.

No hay contraseña, no hay recuperación: si lo pierde, emitimos otro y revocamos el viejo.

## Niveles

Valores de partida, ajustables sin migración porque viven en una tabla:

| Nivel | Volúmenes por job | Jobs totales | Jobs activos | Retención | Prioridad en cola |
|---|---|---|---|---|---|
| `demo` | 12 | 2 | 1 | 7 días | normal |
| `extendido` | 24 | 5 | 1 | 14 días | normal |
| `evaluacion` | 48 | 10 | 2 | 30 días | alta |
| `interno` | sin tope | sin tope | 2 | 90 días | alta |

`interno` es el nuestro, para demostraciones en vivo y depuración. Nunca se emite a terceros.

El tope real de volúmenes por job lo pone también el reloj: a tiempo real son unos 5 min por
volumen, así que 48 volúmenes son unas cuatro horas de nodo. La prioridad alta adelanta en la
cola; no acelera el job.

## Dos tokens distintos, a propósito

| Token | Qué abre | Vida |
|---|---|---|
| **De acceso** | Crear jobs. Lleva el nivel y las cuotas. | Hasta revocarlo o caducar |
| **De resultado** | Ver **un** job en el viewer demo. Aleatorio, no adivinable. | La del job |

Así el prospecto puede enseñarle el resultado a su jefe sin regalarle la capacidad de lanzar
trabajos con su cuota.

## Tablas

```
access_tokens(id, email, org, token_sha256, tier, issued_at, expires_at, revoked_at, note)
tiers(name, max_volumes, max_jobs_total, max_jobs_active, retention_days, priority)
jobs(id, token_id, state, source, site_id, vol_from, vol_to, n_volumes,
     result_token_sha256, created_at, claimed_by, claimed_at, attempts,
     started_at, finished_at, error, expires_at)
job_inputs(job_id, seq, staging_key, source_key, bytes)
```

Estados del job: `queued → claimed → ingesting → ready` y, en paralelo, `failed` o `expired`.
`ready` se puede visitar antes de tiempo: el enlace funciona durante `ingesting` y la línea de
tiempo se va llenando (D6).

## Lo que esto no protege

Un prospecto con token válido puede quemar su cuota entera el primer día. Es aceptable: la
cuota **es** el límite de gasto. Lo que no puede es quemar la de otro ni la del nodo, porque la
concurrencia global la fija el número de réplicas del runner, no los tokens.
