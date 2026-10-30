# syntax=docker/dockerfile:1.7
# =============================================================================
# Voicollo LMS — single image: React SPA + FastAPI API (+ migrations).
#
#   docker build --build-arg VERSION=$(cat VERSION) -t voicollo-lms:$(cat VERSION) .
#
# Behind a TLS-intercepting proxy, pass its CA without baking it into a layer:
#   docker build --secret id=ca_bundle,src=/path/to/ca.crt ...
#
# Commands (see docker/entrypoint.sh): serve (default) | migrate | check-config
# =============================================================================

ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.12-slim

# ---------------------------------------------------------------- 1. frontend
# The SPA is static files, identical for every CPU architecture, so it is built
# once on the build machine's native platform. Without this, a multi-arch build
# runs npm + Vite under QEMU emulation for arm64, which is several times slower.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then export npm_config_cafile=/run/secrets/ca_bundle; fi; \
    npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2. python deps
FROM ${PYTHON_IMAGE} AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then export PIP_CERT=/run/secrets/ca_bundle; fi; \
    python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------- 3. runtime
FROM ${PYTHON_IMAGE} AS runtime

ARG VERSION=0.0.0-dev
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="voicollo-lms" \
      org.opencontainers.image.description="Voicollo Log Management System (API + web console)" \
      org.opencontainers.image.source="https://github.com/Sanjaa46/voicollo_lms" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Proprietary"

RUN groupadd --system --gid 10001 lms \
 && useradd --system --uid 10001 --gid lms --home-dir /app --shell /usr/sbin/nologin lms

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=lms:lms backend/alembic.ini ./alembic.ini
COPY --chown=lms:lms backend/alembic ./alembic
COPY --chown=lms:lms backend/app ./app
COPY --from=web --chown=lms:lms /web/dist ./static
COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/lms

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LMS_BUILD_VERSION="${VERSION}" \
    LMS_BUILD_SHA="${GIT_SHA}" \
    LMS_BUILD_DATE="${BUILD_DATE}" \
    FRONTEND_DIST_DIR=/app/static \
    PORT=8000 \
    WEB_CONCURRENCY=2

USER lms
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=4)" || exit 1

ENTRYPOINT ["lms"]
CMD ["serve"]
