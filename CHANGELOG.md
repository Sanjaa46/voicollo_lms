# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/) — the API path (`/api/v1`) only
changes on a breaking API redesign; the product version is in `VERSION`.

## [Unreleased]

### Changed
- Releases are automatic: merging a `VERSION` bump into `main` publishes the
  image and creates the `vX.Y.Z` tag and GitHub release. `scripts/release.sh`
  no longer creates tags.

## [2.0.0] - 2026-10-30

First versioned release. Deployed as a single image
`ghcr.io/sanjaa46/voicollo-lms:2.0.0` plus `deploy/docker-compose.yml`.

### Breaking
- One container serves the web console **and** the API on the same origin.
  `VITE_API_BASE_URL`, `FRONTEND_URL` and the nginx container are gone; set
  `PUBLIC_URL` instead (`FRONTEND_URL` is still read as a fallback).
- The GitHub OAuth callback is `<PUBLIC_URL>/auth/callback` — update the
  callback URL in your GitHub OAuth app if it pointed elsewhere.
- `JWT_SECRET_KEY` (≥ 32 chars) and `INGEST_SIGNING_SECRET` (≥ 16) are required.
- All timestamps in API responses are UTC (`…Z`). The console renders them in
  the browser's time zone.
- Error codes: ingest from an unknown service → `422 SERVICE_NOT_REGISTERED`,
  from a disabled service → `403 SERVICE_DISABLED`; registry lookups →
  `404 SERVICE_NOT_FOUND`; replayed signed requests → `409 DUPLICATE_REQUEST`;
  sign-in by another GitHub user → `403 AUTH_USER_NOT_ALLOWED`.
- Service enable/disable is idempotent and available as `POST`
  (the old `PATCH` routes still work).

### Added
- Redesigned console (ChatBridge design language): overview dashboard with
  volume chart, logs explorer with live tail, detail drawer, search, time
  ranges and export; service registry with activity and integration snippets;
  system page with health, metrics and manual retention run.
- Endpoints: `GET /stats/overview`, `GET /system/status`, `GET /version`,
  `GET /retention`, `POST /retention/run`, `PATCH /services/{id}`.
- Query filters: `q` (search), `environment`, `action`, `outcome`, multiple
  `source_service`; comma-separated or repeated list parameters.
- `ALLOWED_GITHUB_USER_ID` (optional) pins sign-in to a numeric GitHub id.
- `python -m app.cli migrate|check-config`; DB user passwords re-synced from
  `.env` on every deploy.
- Versioning: `VERSION` file, `scripts/release.sh`, release workflow publishing
  multi-arch images to GHCR, CI for backend, frontend and image build.

### Fixed
- Multi-worker deployments randomly rejected valid sessions (per-process JWT
  secret) and ran the retention job once per worker.
- `ingested_at` was stored 8 h off and producer offsets were dropped;
  milliseconds were truncated. Migration 0004 repairs existing rows.
- `log_type=both` pagination skipped and duplicated rows.
- One invalid entry rejected an entire batch; a DB error mid-batch returned 500
  after partial success. Batches are now rate-limited per entry.
- Audit `environment` was accepted but never stored.
- Level filters no longer return every audit row; `end_time` no longer
  defaults to "now" (hid logs from producers with clock skew).
- Logout now revokes the access token; refresh tokens are hashed at rest and
  rotated atomically; the console no longer deadlocks or signs out on reload.
- Service list filters used OR instead of AND; `lms-system` can no longer be
  disabled; `/health` no longer leaks connection errors in production.

## [1.0.0] - 2025-06-11

Initial unversioned deployment (separate API and nginx containers).
