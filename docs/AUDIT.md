# Code Audit — Voicollo LMS (pre-refactor baseline)

Audit date: 2026-10-30. Baseline commit: `f569cc9`.
Severity: **P0** = data loss / security / broken in production, **P1** = wrong
behaviour users will hit, **P2** = quality / maintainability.

Every item has an ID so `PROGRESS.md` and commits can reference it.

## Backend — security & auth

| ID | Sev | Where | Problem |
|----|-----|-------|---------|
| B-01 | P0 | `core/config.py` | `jwt_secret_key` defaults to a random value **per process**. Uvicorn runs `--workers 2`, so a token signed by worker A fails on worker B (random 401s), and every restart logs the user out. Must be required. |
| B-02 | P1 | `core/auth.py` | GitHub authorize URL is built with `"&".join(f"{k}={v}")` — no URL-encoding of `redirect_uri`/`scope`. |
| B-03 | P1 | `api/v1/auth.py` | Logout deletes the refresh token, but the access token stays valid until expiry. Add a short-lived revocation entry keyed by `jti`. |
| B-04 | P1 | `api/v1/admin.py` | `/health` is unauthenticated and returns raw DB/Redis exception text (`detail`), leaking hostnames/users in production. |
| B-05 | P2 | `core/dependencies.py` | HMAC-signed ingest requests can be replayed inside the 30 s window (duplicate logs). Add signature nonce dedupe in Redis. |
| B-06 | P2 | `main.py` | `X-Request-ID` accepted from clients without length/charset limits (log injection). |

## Backend — business logic

| ID | Sev | Where | Problem |
|----|-----|-------|---------|
| L-01 | P0 | `log_service.py`, `models/*` | **Timezone corruption.** `created_at.replace(tzinfo=None)` drops the offset without converting to UTC (a `+08:00` timestamp is stored 8 h wrong). `ingested_at` uses DB `CURRENT_TIMESTAMP`, which is evaluated in the DB container's TZ (`Asia/Ulaanbaatar`) but then serialised as UTC → every `ingested_at` is shifted by +8 h. |
| L-02 | P0 | `log_service.query_logs` | `log_type=both` pagination is wrong: each table gets `offset=(page-1)*page_size` but only `page_size/2` rows, so pages skip and duplicate rows; ordering across tables is not global. Needs a UNION-based query. |
| L-03 | P0 | `jobs/scheduler.py` | APScheduler starts in **every** Uvicorn worker → retention job runs twice concurrently. Needs a distributed lock. |
| L-04 | P1 | `log_service.export_logs` | Production code imports `unittest.mock.AsyncMock` as a fake Redis. |
| L-05 | P1 | `log_service.write_app_log_batch` | No savepoints: one DB error poisons the session, later entries fail and the final commit raises 500 after reporting partial success. Service lookup repeated per entry. |
| L-06 | P1 | `api/v1/ingest.py` | Batch rate-limit counts 1 request for the first entry's service only; a 100-entry batch from mixed services bypasses limits. |
| L-07 | P1 | `log_service.query_logs` | `end_time` silently defaults to *now*, hiding logs from producers with clock skew. |
| L-08 | P1 | `log_service.query_logs` | App-only filters (`level`, `trace_id`) are ignored for audit rows in `both` mode, so "level=ERROR" still returns every audit row. Same for `actor_id` vs app rows. |
| L-09 | P1 | `add_srvc_service.query_services` | Filters combined with `OR` instead of `AND`; uses blocking `KEYS` for cache invalidation; manual `commit()` inside a request-scoped session that also commits. |
| L-10 | P1 | `exceptions.ServiceNotRegisteredError` | Used for both "ingest from unknown service" and "service not found in registry" → messages like `Service 'Service x not exists.' is not registered`. Different status semantics needed (422 vs 404). |
| L-11 | P1 | `services` | Reserved `lms-system` service can be disabled → retention self-log silently fails. No update endpoint for name/description. No slug validation on service id. |
| L-12 | P1 | `cache_service` | Every single app-log write runs a full `SCAN lms:query:*` + delete. At volume this dominates ingest latency. Replace with a generation counter. Audit writes never invalidate (stale for 60 s). |
| L-13 | P2 | `cache_service` | `increment_error_counter` is never called → `/metrics.error_total` is always empty. |
| L-14 | P2 | `api/v1/query.py` | Leftover `logger.info(level)`; datetime parsing duplicated in two routers; `import` inside functions. |
| L-15 | P2 | `jobs/retention.py` | Self-log uses `async for session in get_db()` (generator hack). |
| L-16 | P2 | — | No dashboard statistics endpoint (counts per level, timeline, per-service activity). |
| L-17 | P2 | `alembic/0002` | `lms_app` is granted write on `schema_migrations` (not needed). |

## Backend — quality

| ID | Sev | Problem |
|----|-----|---------|
| Q-01 | P2 | `requirements.txt` is a `pip freeze` with dev/CLI noise (`fastapi-cloud-cli`, `rich`, `typer`, `pytest` in prod image). |
| Q-02 | P2 | Comments reference external spec documents (`LMS-SDD-002 §3.1`) the repo does not contain; DAN SSO leftovers (`AuthJwksUnavailableError`, `INSUFFICIENT_ROLE`). |
| Q-03 | P2 | Only one test, and it does not run (`asyncio` fixtures, mocks do not match code). |
| Q-04 | P2 | Two compose files (root + backend) that disagree; `.env.example` duplicates the same password 3–4 times in different URLs. |

## Frontend

| ID | Sev | Problem |
|----|-----|---------|
| F-01 | P0 | Refresh flow deadlock: a 401 from `/auth/refresh` itself enters the interceptor while `isRefreshing=true` and waits forever. |
| F-02 | P1 | On page load an expired access token wipes **all** storage including a valid refresh token → forced re-login every 60 min. |
| F-03 | P1 | Callback hard-codes `'Sanjaa46'` while `.env.example` allows `sanjmyat4v`; the backend already enforces the user. |
| F-04 | P1 | `VITE_API_BASE_URL` is baked at build time → one image cannot serve different domains. |
| F-05 | P1 | `servicesAPI.queryServices` typed as `{services}` but backend returns `{data}` (page guesses both). |
| F-06 | P2 | Inline `style={{}}` + `onMouseEnter` colour hacks everywhere; light/dark mixed inconsistently; no design tokens. |
| F-07 | P2 | No time-range filter, no search, filters not in URL, no auto-refresh. |

## Deployment

| ID | Sev | Problem |
|----|-----|---------|
| D-01 | P1 | Two images (api + nginx) built from source on the server; nothing tagged; no version source of truth. |
| D-02 | P1 | `cloudflared:latest` and `redis:7-alpine` unpinned. |
| D-03 | P2 | Migrations need a separate container definition with duplicated env. |

## Client packages

| ID | Sev | Pkg | Problem |
|----|-----|-----|---------|
| C-01 | P0 | JS | `exports.require` points to `./src/index.cjs`, which does not exist → `require('lms-logger')` crashes. |
| C-02 | P1 | both | Signature computed **once** before the retry loop; retries after 30 s are rejected as expired. |
| C-03 | P1 | both | 5xx responses are not retried; 429 `Retry-After` ignored. |
| C-04 | P1 | both | Required/optional fields disagree with the server (`trace_id`, `ip_address` required in client; `actor_id` optional in client but required on server). |
| C-05 | P1 | JS | `outcome` validated with `requireString(…, OutcomeType)` (enum ignored). |
| C-06 | P1 | PY | `AsyncLMSClient`, `LMSConnectionError`, `ActorType`, `OutcomeType` not exported. `model_dump()` not in JSON mode. |
| C-07 | P2 | both | No buffering/background flush; a logging failure throws into the host app; `source_service`/`environment` repeated on every call; no version constant, no CHANGELOG, no CI, no release tags. |
</content>
</invoke>
