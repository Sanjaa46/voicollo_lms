# Progress

Legend: `[x]` done · `[~]` in progress · `[ ]` todo · `[-]` deferred (reason given)

Branch in all repos: `claude/busy-fermat-k5t7zn`

## Phase 0 — Planning
- [x] AUDIT.md, PLAN.md, PROGRESS.md, PROMPTS.md

## Phase 1 — Backend
- [x] 1.1 Project hygiene (requirements split, pyproject, comment cleanup)
- [x] 1.2 Config (required JWT secret, component env, PUBLIC_URL, logging)
- [x] 1.3 UTC time handling
- [x] 1.4 Auth hardening (URL encoding, revocation, refresh token format)
- [x] 1.5 Ingest (savepoints, rate limit, replay dedupe, error codes)
- [x] 1.6 Query (UNION pagination, filters)
- [x] 1.7 Cache generation counter + error metrics
- [x] 1.8 Services registry fixes + PATCH + activity
- [x] 1.9 Export rewrite
- [x] 1.10 Stats overview endpoint
- [x] 1.11 Retention lock + manual run
- [x] 1.12 Health / version endpoints
- [x] 1.13 Migration 0004
- [x] 1.14 Test suite

## Phase 2 — Frontend
- [x] 2.1 Design tokens + fonts
- [x] 2.2 API/auth layer fixes
- [x] 2.3 App shell
- [x] 2.4 Pages
- [x] 2.5 Lint + build clean

## Phase 3 — Deployment
- [x] 3.1 Root Dockerfile
- [x] 3.2 Entrypoint + SPA serving
- [x] 3.3 deploy/ compose + .env.example
- [x] 3.4 Dev compose
- [x] 3.5 VERSION, CHANGELOG, release script, Makefile
- [x] 3.6 GitHub Actions CI + release
- [x] 3.7 DEPLOYMENT.md + README
- [x] 3.8 Remove obsolete deployment files

## Phase 4 — Client packages
- [x] 4.1 Python package (lms-logger 1.0.0 — 23 tests, mypy strict, verified against live LMS)
- [x] 4.2 JS package (lms-logger 1.0.0 — 19 tests, ESM+CJS, git install verified, live LMS)

---

## Session notes
(Newest first. Write what was in flight when a session ended.)

- 2026-10-30 — Phase 4 done. Both client packages at 1.0.0 with CI + release
  workflows; both exercised end to end against the running v2 backend
  (direct, audit, batch, buffered, 403/422 mapping).
  **All work is committed locally in the three repos; `git push` returns
  HTTP 403 (the Claude GitHub App has no write access to Sanjaa46/*).**
  Remaining after access is fixed:
    1. push `claude/busy-fermat-k5t7zn` in all three repos, open PRs
    2. after merging: `scripts/release.sh` is NOT needed for 2.0.0 (VERSION is
       already 2.0.0) — just `git tag -a v2.0.0 -m "v2.0.0" && git push origin v2.0.0`
       in voicollo_lms; tag `v1.0.0` in both client repos
    3. deploy per docs/DEPLOYMENT.md §3 (v1 → v2 migration)

- 2026-10-30 — Phase 3 done. Root Dockerfile builds one 338 MB image
  (SPA + API + migrations, non-root, healthcheck). deploy/docker-compose.yml
  verified from scratch: migrate → healthy app, SPA + API on one origin,
  signed ingest, idempotent re-deploy. release.sh dry-run verified.
  Next: Phase 4 (client packages).

- 2026-10-30 — Phase 2 done. New React UI (Overview, Logs explorer with drawer,
  log detail, Services with integration snippets, System) on ChatBridge tokens;
  chart palette validated with the dataviz checker (dark + light). Verified with
  Playwright screenshots against the real backend (no console errors).
  Fixed F-01..F-07. Next: Phase 3 (single image).

- 2026-10-30 — Phase 1 done. 50 backend tests green; migrations 0001→0004 and
  0004 downgrade verified on MariaDB 10.6; uvicorn (2 workers) smoke-tested
  against MariaDB + Redis (UNION paging, stats, export, retention, ms precision,
  legacy +8 h fix). Extra bugs found and fixed: L-18, L-19, L-20.
  **Pushing is blocked (HTTP 403 — GitHub app has no access); commits are local.**
  Next: Phase 2 (frontend).
- 2026-10-30 — Audit and plan written.
</content>
</invoke>
