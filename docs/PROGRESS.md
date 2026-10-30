# Progress

Legend: `[x]` done · `[~]` in progress · `[ ]` todo · `[-]` deferred (reason given)

Branch in all repos: `claude/busy-fermat-k5t7zn`

## Phase 0 — Planning
- [x] AUDIT.md, PLAN.md, PROGRESS.md, PROMPTS.md

## Phase 1 — Backend
- [ ] 1.1 Project hygiene (requirements split, pyproject, comment cleanup)
- [ ] 1.2 Config (required JWT secret, component env, PUBLIC_URL, logging)
- [ ] 1.3 UTC time handling
- [ ] 1.4 Auth hardening (URL encoding, revocation, refresh token format)
- [ ] 1.5 Ingest (savepoints, rate limit, replay dedupe, error codes)
- [ ] 1.6 Query (UNION pagination, filters)
- [ ] 1.7 Cache generation counter + error metrics
- [ ] 1.8 Services registry fixes + PATCH + activity
- [ ] 1.9 Export rewrite
- [ ] 1.10 Stats overview endpoint
- [ ] 1.11 Retention lock + manual run
- [ ] 1.12 Health / version endpoints
- [ ] 1.13 Migration 0004
- [ ] 1.14 Test suite

## Phase 2 — Frontend
- [ ] 2.1 Design tokens + fonts
- [ ] 2.2 API/auth layer fixes
- [ ] 2.3 App shell
- [ ] 2.4 Pages
- [ ] 2.5 Lint + build clean

## Phase 3 — Deployment
- [ ] 3.1 Root Dockerfile
- [ ] 3.2 Entrypoint + SPA serving
- [ ] 3.3 deploy/ compose + .env.example
- [ ] 3.4 Dev compose
- [ ] 3.5 VERSION, CHANGELOG, release script, Makefile
- [ ] 3.6 GitHub Actions CI + release
- [ ] 3.7 DEPLOYMENT.md + README
- [ ] 3.8 Remove obsolete deployment files

## Phase 4 — Client packages
- [ ] 4.1 Python package
- [ ] 4.2 JS package

---

## Session notes
(Newest first. Write what was in flight when a session ended.)

- 2026-10-30 — Audit and plan written. Next: Phase 1.1.
</content>
</invoke>
