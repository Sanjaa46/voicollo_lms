# Prompts

Copy-paste these into Claude Code. They assume the three repos are attached
to the session and the branch is `claude/busy-fermat-k5t7zn`.

---

## 1. Starting prompt (fresh session, nothing done yet)

```text
You are working on my Log Management System and its two client packages:
- Sanjaa46/voicollo_lms (FastAPI backend + React frontend)
- Sanjaa46/voicollo_log_client_js
- Sanjaa46/voicollo_log_client_py
Colour reference (read only): Sanjaa46/ChatBridge apps/web/src/app/globals.css

Work on branch claude/busy-fermat-k5t7zn in every repo.

Read voicollo_lms/docs/PLAN.md, docs/AUDIT.md and docs/PROGRESS.md first and
follow the plan phase by phase:
  Phase 1 backend refactor + fixes, Phase 2 frontend redesign (use the
  frontend-design skill, ChatBridge colours), Phase 3 single versioned Docker
  image + compose deployment, Phase 4 client packages.
Rules:
- GitHub OAuth single-user login must stay exactly as the auth model.
- After each numbered step: run tests, update docs/PROGRESS.md, commit with a
  clear message, push.
- Do not open pull requests unless I ask.
```

## 2. Continue prompt (after a usage limit / new session)

```text
Continue the LMS refactor. Read voicollo_lms/docs/PROGRESS.md (and the
"Session notes" at the bottom), then docs/PLAN.md for the details of the next
unchecked item. Check `git log --oneline -15` and `git status` in all three
repos (branch claude/busy-fermat-k5t7zn) to see what was already committed;
if there are uncommitted changes, inspect them and finish or commit them
first. Then continue from the first item not marked [x]. Keep updating
PROGRESS.md, committing and pushing after every step.
```

## 3. Short "keep going" prompt (same session, Claude stopped mid-way)

```text
Keep going with the next unchecked item in docs/PROGRESS.md. Don't redo
finished items. Commit and push when each item is done.
```

## 4. Phase-specific prompts (if you want to run one phase only)

**Backend only**
```text
Do Phase 1 of voicollo_lms/docs/PLAN.md (backend refactor). Fix every
backend item in docs/AUDIT.md (B-*, L-*, Q-*). Keep GitHub single-user auth.
Make the pytest suite pass. Update PROGRESS.md, commit, push.
```

**Frontend only**
```text
Do Phase 2 of voicollo_lms/docs/PLAN.md. Use the frontend-design skill.
Colours and fonts must match Sanjaa46/ChatBridge apps/web/src/app/globals.css.
The API is same-origin at /api/v1. `npm run build` and `npm run lint` must
pass. Update PROGRESS.md, commit, push.
```

**Deployment only**
```text
Do Phase 3 of voicollo_lms/docs/PLAN.md: one Docker image (frontend + backend)
tagged from the VERSION file, deploy/docker-compose.yml + deploy/.env.example,
release script, GitHub Actions release to GHCR, docs/DEPLOYMENT.md.
```

**Client packages only**
```text
Do Phase 4 of voicollo_lms/docs/PLAN.md for voicollo_log_client_js and
voicollo_log_client_py. Field rules must match the LMS backend schemas in
voicollo_lms/backend/app/schemas/log_schemas.py. Version 1.0.0, CHANGELOG,
tests, CI. Commit and push each repo.
```

## 5. Release prompt (after everything is merged)

```text
Release voicollo_lms version X.Y.Z: run scripts/release.sh X.Y.Z on a branch,
push it and open a PR. After I merge it, confirm the Release workflow pushed
ghcr.io/sanjaa46/voicollo-lms:X.Y.Z and created the vX.Y.Z tag.
```

## 6. Review prompt

```text
/code-review high  — review the diff of claude/busy-fermat-k5t7zn against main
in voicollo_lms, focusing on auth, timezone handling, and the UNION query.
```
</content>
</invoke>
