# Refactor Plan — Voicollo LMS + client packages

Goal: turn the Log Management System into a production-grade, versioned
product that deploys from **one Docker image + one `.env` file**, with
client packages that behave like well-maintained libraries.

Non-negotiable: authentication stays **GitHub OAuth, single allowed user**
(`ALLOWED_GITHUB_USERNAME`). No roles, no other login methods.

Issue IDs (B-, L-, F-, D-, C-, Q-) refer to [AUDIT.md](AUDIT.md).
Progress is tracked in [PROGRESS.md](PROGRESS.md). Resume prompts are in
[PROMPTS.md](PROMPTS.md).

---

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Versioning | Single `VERSION` file at repo root → baked into image (`APP_VERSION`), shown in UI and `/api/v1/version`. Git tag `vX.Y.Z` triggers release. SemVer. | One source of truth. |
| New version | **2.0.0** (API path stays `/api/v1`) | Error codes and timestamp format change. |
| Image | One image `ghcr.io/sanjaa46/voicollo-lms:<version>`: Node stage builds SPA, Python stage serves API **and** SPA (same origin). | Removes nginx image, removes build-time API URL (F-04), no CORS needed. |
| Migrations | Same image, `command: migrate`, run by a one-shot compose service. | Still one image; migrations need root DB creds the API must not hold. |
| Time | Store naive **UTC** everywhere; DB session forced to `+00:00`; API returns ISO-8601 with `Z`; UI renders in browser TZ. Migration 0004 fixes legacy `ingested_at` (+8 h). | Fixes L-01. |
| Query cache invalidation | Generation counter (`lms:query:gen`) embedded in cache key; writes `INCR` it. | O(1) instead of SCAN per write (L-12). |
| `both` pagination | `UNION ALL` of `(type, id, ts)` projections, global ORDER BY/LIMIT, then hydrate rows. | Correct paging (L-02). |
| Retention in multi-worker | Redis `SET NX EX` lock around the job. | L-03. |
| Ingest auth | Keep shared HMAC secret (`INGEST_SIGNING_SECRET`) + add replay dedupe. Per-service secrets deferred to a later minor. | Compatible with existing clients. |
| Client packages | Keep package/import names (`lms-logger`, `lms_logger`) so existing installs don't break; bump to **1.0.0**. JS rewritten in TypeScript (dual ESM/CJS via tsup, built on `prepare` so git installs work). | C-01..C-07. |

---

## Phase 1 — Backend refactor & fixes

1. **Project hygiene** — trim `requirements.txt` to direct deps,
   `requirements-dev.txt` for tests; `pyproject.toml` with ruff + pytest
   config; delete spec-reference and DAN-SSO leftover comments/classes
   (Q-01, Q-02).
2. **Config** — `Settings` validation: `JWT_SECRET_KEY` required (≥32 chars)
   (B-01); DB settings from components (`DB_HOST`, `DB_PORT`, `DB_NAME`,
   `DB_APP_PASSWORD`, `DB_RETENTION_PASSWORD`, `DB_ROOT_PASSWORD`) with full
   URL override; `PUBLIC_URL` drives CORS + OAuth redirect default;
   `LOG_LEVEL`, `LOG_FORMAT=text|json`.
3. **Time handling** — `shared/time.py` with `to_utc_naive()`; Python-side
   `ingested_at` default; engine `init_command="SET time_zone='+00:00'"`;
   serializers emit UTC `Z` (L-01).
4. **Auth** — urlencode authorize URL (B-02); access-token revocation on
   logout (B-03); refresh token carries its `jti` (`<jti>.<secret>`), the
   separate `jti` field becomes optional (backward compatible).
5. **Ingest** — savepoint per batch entry, service lookups cached per batch
   (L-05); rate limit counts every entry per service (L-06); Redis signature
   replay guard (B-05); `SERVICE_NOT_REGISTERED` 422 /
   `SERVICE_DISABLED` 403 for ingest, `SERVICE_NOT_FOUND` 404 for the
   registry (L-10); active-service lookup cached in Redis 30 s.
6. **Query** — UNION pagination (L-02); no implicit `end_time` (L-07);
   type-specific filters narrow `both` mode (L-08); new filters `q`
   (message/action/target search), `environment`, `action`, `outcome`.
7. **Cache** — generation-based keys (L-12); error counters wired into the
   exception handler (L-13).
8. **Services** — AND filters, SCAN not KEYS, no manual commits (L-09);
   slug validation, `PATCH /services/{id}` for name/description, reserved
   `lms-system` cannot be disabled (L-11); `last_seen_at` + 24 h counts per
   service in list response.
9. **Export** — dedicated query path without fake Redis (L-04); streaming
   CSV; `limit` ≤ 10 000.
10. **Stats** — `GET /api/v1/stats/overview?hours=24`: totals, per-level
    counts, per-outcome counts, time histogram, top services (L-16).
11. **Retention** — distributed lock (L-03), proper session for self-log
    (L-15), `POST /api/v1/retention/run` (manual trigger, authenticated).
12. **Health** — `/health` returns status only in production (B-04);
    `/api/v1/version` (public: version, build commit, build date).
13. **Migration 0004** — legacy timezone fix (`LMS_LEGACY_TZ_OFFSET_HOURS`,
    default 8, 0 to skip), revoke `schema_migrations` grant (L-17), lms_app
    UPDATE on services kept.
14. **Tests** — pytest + aiosqlite + fakeredis: auth, ingest (single, batch,
    signature, replay, rate limit), query (UNION paging, filters), services,
    export, stats, retention. Target: all green in CI.

## Phase 2 — Frontend redesign

Use the `frontend-design` skill. Palette and type come from ChatBridge
(`apps/web/src/app/globals.css`):

- Surfaces `#0a0a0c / #111114 / #17171b`, borders `#29292f`, text
  `#ededf0 / #9a9aa5 / #8a8a94`; light theme `#f7f5f1` paper.
- Primary **amber `#ff8a1e`**, teal `#2dd4bf`, rose `#fb5c72`, info
  `#5b9dfb`, warning `#f5a524`.
- Fonts: Unbounded (display), IBM Plex Sans (UI), IBM Plex Mono (data) —
  self-hosted via `@fontsource` (works offline / behind tunnel).
- Radii 6/10/14/20, grain overlay, `rise-in` motion, reduced-motion respected.

Steps:
1. Tailwind v4 `@theme` tokens, dark default + light theme toggle.
2. API layer: relative `/api/v1`, single-flight refresh without deadlock
   (F-01), keep refresh token on reload (F-02), drop hard-coded username
   (F-03), typed responses matching backend (F-05).
3. App shell: sidebar (Overview, Logs, Services, System), top bar with
   version + user + logout, command-style search.
4. Pages:
   - **Login / Callback** — branded, single "Continue with GitHub".
   - **Overview** — KPI tiles, level histogram, error-rate, top services,
     recent errors.
   - **Logs explorer** — URL-synced filters, time presets (15m/1h/24h/7d/
     custom), level chips, search, live auto-refresh, dense mono table,
     side drawer detail with JSON viewer and "filter by trace" links,
     export JSON/CSV.
   - **Log detail** (deep link).
   - **Services** — list with status + last seen + 24 h volume,
     register / edit / enable / disable, integration snippet (JS & Python).
   - **System** — health, metrics, retention last run + manual run.
5. `npm run lint` and `npm run build` clean.

## Phase 3 — One-image deployment & version control

1. Root `Dockerfile` (multi-stage: `node:22-alpine` → `python:3.12-slim`),
   build args `VERSION`, `GIT_SHA`, `BUILD_DATE`; OCI labels; non-root;
   `HEALTHCHECK`.
2. `docker/entrypoint.sh` with commands `serve` (default), `migrate`,
   `shell`; FastAPI serves `/` SPA with history fallback and long-cache
   `/assets`.
3. `deploy/docker-compose.yml` (lms-db, lms-cache, lms-migrate, lms-app,
   optional `cloudflared` via `profiles: [tunnel]`), pinned images, only
   `LMS_VERSION` + `.env` needed. `deploy/.env.example` documented.
4. `docker-compose.dev.yml` for local development (build from source).
5. `VERSION`, `CHANGELOG.md` (Keep a Changelog), `scripts/release.sh`
   (bump, changelog section, tag), `Makefile` (dev, test, build, release).
6. `.github/workflows/ci.yml` (backend tests, frontend lint/build) and
   `release.yml` (on tag `v*`: build & push `:X.Y.Z`, `:X.Y`, `:latest` to
   GHCR).
7. `docs/DEPLOYMENT.md` (first install, upgrade, rollback, backup) and
   rewritten `README.md`.
8. Remove `backend/docker-compose.yml`, `backend/Dockerfile`,
   `frontend/Dockerfile`, `frontend/nginx.conf`, old root compose.

## Phase 4 — Client packages

Shared contract (both languages):
- Client options: `baseUrl`, `secret`, `sourceService`, `environment`
  (defaults applied to every entry), `timeout`, `maxRetries`.
- Signature recomputed **per attempt** (C-02). Retries with exponential
  backoff + jitter on network errors, 5xx and 429 (honouring `Retry-After`)
  (C-03).
- Field rules match the server exactly (C-04/C-05).
- Errors: `LMSError` → `LMSAuthError` (401), `LMSPermissionError` (403),
  `LMSNotFoundError` (404), `LMSValidationError` (422),
  `LMSRateLimitError` (429, `retryAfter`), `LMSServerError` (5xx),
  `LMSConnectionError`.
- Convenience: `debug/info/warn/error/fatal(message, context)` and
  `audit({...})`.
- Optional **buffered** mode: queue + background flush via batch endpoint,
  `flush()`, `close()` drains; `onError` hook — logging never throws into
  the host app in buffered mode.
- `User-Agent: lms-logger-<lang>/<version>`; exported `VERSION`.
- Repo hygiene: README with examples, CHANGELOG, LICENSE, CI (test matrix),
  release workflow on tag (build artifacts attached; npm/PyPI publish when
  tokens are configured).

**Python** (`lms_logger`): `LMSClient` + `AsyncLMSClient`, pydantic models,
`LMSHandler` (stdlib `logging.Handler`), `py.typed`, version via
`importlib.metadata`, pytest + respx tests.

**JS** (`lms-logger`): TypeScript source, tsup dual build (`dist/index.js`,
`dist/index.cjs`, `dist/index.d.ts`), `prepare` builds on git install,
Node ≥18 native `fetch`, vitest tests.

---

## Definition of done
- `pytest` green, `ruff` clean (backend); `npm run lint && npm run build`
  (frontend); client test suites green.
- `docker build` produces one image that serves UI + API; compose up with
  only `deploy/.env` + `LMS_VERSION`.
- Every AUDIT item is fixed or explicitly deferred in PROGRESS.md.
</content>
</invoke>
<invoke name="Bash">
<parameter name="command">cd /home/user/voicollo_lms && git add docs && git commit -q -m "docs: add refactor plan, audit, progress tracker and resume prompts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01F8d3A81KNMMV3bMBsLT6wa" && git push -u origin claude/busy-fermat-k5t7zn 2>&1 | tail -1