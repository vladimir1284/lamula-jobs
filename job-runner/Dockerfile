# Imagen del runner (F1): el ORPG de producción más el pipeline y el CLI, solo en capas encima.
# No modifica el build del ORPG y NO se comparte fuera de nuestra infraestructura
# (docs/referencia/licencia.md).
#
#   docker build -f job-runner/Dockerfile \
#     --build-context pipeline=../nexrad-l3-pipeline -t job-runner:f1 .
#   docker run -d --name job --hostname orpg-job --stop-timeout 30 -v "$PWD/f0-run:/data" job-runner:f1
#
# `--hostname orpg-job` es obligatorio: tcp.conf (enlace 1 de nbtcp) lleva ese nombre y el
# runner usa el hostname del contenedor como último argumento de nbtcp.
ARG BASE=orpg-prod:b24
FROM ${BASE}

USER root
# La base trae Python 3.6; el runner usa 3.7+ y el pipeline pide >=3.12 (lo trae uv).
RUN dnf -y install python3.11 python3.11-pip && dnf clean all \
 && python3.11 -m pip install --no-cache-dir uv

ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_PROJECT_ENVIRONMENT=/opt/pipeline/.venv UV_LINK_MODE=copy UV_PYTHON=3.12
COPY --from=pipeline pyproject.toml uv.lock README.md /opt/pipeline/
COPY --from=pipeline ingest /opt/pipeline/ingest
COPY --from=pipeline db /opt/pipeline/db
RUN cd /opt/pipeline && uv sync --frozen --no-dev \
 && printf '#!/bin/sh\nexec /opt/pipeline/.venv/bin/l3proc "$@"\n' > /usr/local/bin/l3proc \
 && printf '#!/bin/sh\nexec python3.11 -I -m runner "$@"\n' > /usr/local/bin/runner \
 && chmod 755 /usr/local/bin/l3proc /usr/local/bin/runner \
 && chmod -R a+rX /opt/pipeline /opt/python

COPY runner /usr/lib/python3.11/site-packages/runner
RUN chmod -R a+rX /usr/lib/python3.11/site-packages/runner

# Configuración de nbtcp y RPS list (F0): enlace 1 cm_tcp, tcp.conf con orpg-job, LR 1536000 (D11)
COPY --chown=orpg:orpg job-runner/cfg/comms_link.conf job-runner/cfg/tcp.conf job-runner/cfg/rps_lamula.list /home/orpg/cfg/

USER orpg
