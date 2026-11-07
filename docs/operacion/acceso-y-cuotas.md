# Acceso y cuotas

Sin registro público y sin cuentas (D8). El prospecto pide acceso por correo, nosotros
emitimos un token a mano, y **el nivel del token decide cuánto cómputo recibe**. Quien pide más
—más volúmenes, más trabajos, más tiempo de conservación— recibe un token de nivel superior si
la petición lo justifica.

## Flujo

1. La página pública explica el demo y muestra un formulario corto: correo, organización, qué
   quiere ver. Protegido con Turnstile.
2. Llega un correo al dueño con la solicitud y un enlace de revisión (D20): aprobar con nivel, o rechazar.
3. Al aprobar se emite el token (también posible a mano: `jobs-admin approve <id> --tier <nivel>`). El token
   se muestra **una sola vez**; en la base queda solo su `sha256`.
4. Se envía solo al solicitante por correo, con el enlace del demo. El cliente lo pega una vez y el navegador
   lo guarda.

No hay contraseña, no hay recuperación: si lo pierde, emitimos otro y revocamos el viejo.

## Formulario de solicitud (aprobado el 2026-11-07)

Aprobado tal cual por el dueño del producto. La aprobación de cada solicitud se hace por correo (D20). Criterio con el que está
escrito: pedir lo mínimo para decidir un nivel de token, y que el prospecto tarde menos de un
minuto. Cada campo de más es una solicitud menos.

| Campo | Tipo | Obligatorio | Por qué está |
|---|---|---|---|
| Correo | texto | sí | Es por donde va el token. Sin cuentas, es el único identificador. |
| Organización | texto | sí | Decide el nivel: no es lo mismo una universidad que una aerolínea. |
| Cargo o función | texto corto | no | Afina el nivel sin obligar a nada. |
| Qué quiere ver | selección múltiple | sí | `un huracán conocido` / `un día concreto de un radar` / `mis propias observaciones` / `otra cosa` |
| Radar o zona de interés | texto corto | no | Si dice un radar que no es de EEUU, la respuesta es otra conversación. |
| Comentario | área de texto | no | Donde explican el caso de verdad. |

Más el Turnstile, y una casilla de aceptación del aviso de uso.

Texto de la página, en borrador:

> **Pruebe la cadena completa, con datos de radar reales.**
>
> Elija una tormenta del archivo público de los Estados Unidos. Procesamos sus observaciones
> crudas con el mismo software que corre en un radar operativo, y le mandamos un enlace para
> ver los productos resultantes en nuestro visor.
>
> No hay registro: escríbanos qué quiere ver y le enviamos un enlace de acceso.
>
> *El tiempo de cómputo es real —una tormenta de hora y media tarda hora y media en
> procesarse—, así que los accesos se conceden a mano y con un límite. Los productos
> generados son para evaluación: no son productos oficiales de ningún servicio
> meteorológico.*

Esa última frase no es cortesía legal, es la regla de etiquetado de salida de
[Pendientes](../alcance/pendientes.md) y tiene que estar también en el visor.

Correo de respuesta, en borrador:

> Aquí tiene su acceso al demo de LAMULA: `<enlace>`
>
> El código es `<token>` y se pega una sola vez; el navegador lo recuerda. **Guárdelo**: no
> podemos recuperarlo, aunque sí emitirle otro.
>
> Su nivel de acceso permite `<N>` volúmenes por trabajo y `<M>` trabajos. Cada trabajo tarda
> aproximadamente lo mismo que duró la tormenta que elija, y no hace falta esperar a que
> termine: el enlace del resultado funciona desde el primer minuto y la línea de tiempo se va
> llenando sola.
>
> Si necesita más, responda a este correo y lo hablamos.

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

!!! note "Falta un tope en bytes"
    Un volumen de huracán ocupa de 12 a 25 MB y uno de día tranquilo 5,9 MB
    ([Catálogo verificado](../referencia/catalogo-verificado.md)), así que esta tabla, que solo
    cuenta volúmenes, deja que un `demo` mueva entre 70 MB y 300 MB de staging y un
    `evaluacion` hasta 1,2 GB. Propuesta pendiente de aprobar: `max_bytes` en `tiers`,
    validado al crear el job, que es cuando `jobs-api` ya conoce el tamaño de cada clave.

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
