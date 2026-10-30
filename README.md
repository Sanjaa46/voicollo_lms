# Voicollo LMS

Centralised log management for Voicollo services: application and audit log
ingestion, search, retention and a web console. It ships as one versioned
Docker image.

```
producers ──HMAC-signed──▶  /api/v1/logs/*  ┐
(lms-logger JS / Python)                    │   voicollo-lms image
                                            ├─  FastAPI  ── MariaDB (logs, services)
browser ──GitHub sign-in──▶  /  (React SPA) │     │
                             /api/v1/*      ┘     └──── Redis (cache, sessions, locks)
```

- **Ingestion:** single, batch (≤ 100, partial success) and audit endpoints.
  Requests are HMAC-SHA256 signed with replay protection, rate-limited per service.
- **Console:** overview dashboard, log explorer with live tail, service registry,
  system health, and retention controls.
- **Retention:** app logs 90 days, audit logs 365 days (configurable). Audit logs
  are append-only; the API has no update or delete path.
- **Auth:** GitHub OAuth for a single allowed user.

Current version: see [`VERSION`](VERSION) · [CHANGELOG](CHANGELOG.md)

## Deploy

```bash
cd deploy && cp .env.example .env    # fill in
docker compose up -d
```

Full guide, including upgrades, backups and migrating from v1:
**[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## Develop

Requirements: Python 3.12+, Node 22+, Docker.

```bash
make install                 # backend venv + frontend deps
make test lint               # 50+ backend tests, ruff, eslint, tsc
```

Run with hot reload:

```bash
# 1. MariaDB + Redis (fill deploy/.env first; LMS_VERSION=dev)
cd deploy && docker compose -f docker-compose.yml -f docker-compose.build.yml up -d lms-db lms-cache
# 2. API on :8000 (reads backend/.env — DB_HOST=127.0.0.1, REDIS_HOST=127.0.0.1, ...)
cd backend && .venv/bin/python -m app.cli migrate && .venv/bin/uvicorn app.main:app --reload
# 3. Console on :5173, proxies /api to :8000
cd frontend && npm run dev
```

Set `PUBLIC_URL=http://localhost:5173` while using the Vite dev server, so the
OAuth callback returns to it. Interactive API docs are at `/api/docs` when
`APP_ENV` is not `production`.

Whole stack from source: `make up` (builds the image locally).

### Layout

```
backend/        FastAPI app (app/), Alembic migrations, pytest suite
frontend/       React 19 + Vite + Tailwind 4 console
docker/         container entrypoint
deploy/         production compose file + .env template
scripts/        build-image.sh, release.sh
docs/           deployment guide, refactor plan/progress
```

## Release

```bash
scripts/release.sh 2.1.0               # bumps VERSION + CHANGELOG, commits, tags
git push origin HEAD && git push origin v2.1.0
```

Pushing the tag runs `.github/workflows/release.yml`, which builds a
multi-arch image, pushes `ghcr.io/sanjaa46/voicollo-lms:2.1.0` (plus `2.1` and
`latest`) and publishes a GitHub release.

## Client packages

- Node.js: [`voicollo_log_client_js`](https://github.com/Sanjaa46/voicollo_log_client_js)
- Python: [`voicollo_log_client_py`](https://github.com/Sanjaa46/voicollo_log_client_py)
