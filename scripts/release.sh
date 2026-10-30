#!/usr/bin/env bash
# Cut a release:  scripts/release.sh 2.1.0
#   1. checks the version is SemVer and newer than ./VERSION
#   2. writes VERSION + frontend/package.json version
#   3. turns "## [Unreleased]" in CHANGELOG.md into "## [2.1.0] - <date>"
#   4. commits "chore(release): v2.1.0" and creates annotated tag v2.1.0
# Pushing the tag triggers .github/workflows/release.yml, which builds and
# publishes ghcr.io/sanjaa46/voicollo-lms:2.1.0.
set -euo pipefail
cd "$(dirname "$0")/.."

NEW="${1:-}"
if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  echo "usage: scripts/release.sh <MAJOR.MINOR.PATCH[-prerelease]>" >&2
  exit 2
fi
CURRENT="$(tr -d '[:space:]' < VERSION)"
if [ "$(printf '%s\n%s\n' "$CURRENT" "$NEW" | sort -V | tail -1)" != "$NEW" ] || [ "$CURRENT" = "$NEW" ]; then
  echo "error: $NEW is not newer than current $CURRENT" >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "error: commit or stash your changes first" >&2
  exit 1
fi
if git rev-parse "v$NEW" >/dev/null 2>&1; then
  echo "error: tag v$NEW already exists" >&2
  exit 1
fi
if ! grep -q '^## \[Unreleased\]' CHANGELOG.md; then
  echo "error: CHANGELOG.md has no '## [Unreleased]' section" >&2
  exit 1
fi

TODAY="$(date -u +%Y-%m-%d)"
echo "$NEW" > VERSION
(cd frontend && npm version "$NEW" --no-git-tag-version --allow-same-version >/dev/null)
python3 - "$NEW" "$TODAY" <<'PY'
import re, sys
new, today = sys.argv[1], sys.argv[2]
text = open("CHANGELOG.md", encoding="utf-8").read()
text = text.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{new}] - {today}", 1)
open("CHANGELOG.md", "w", encoding="utf-8").write(text)
PY

git add VERSION CHANGELOG.md frontend/package.json frontend/package-lock.json
git commit -m "chore(release): v$NEW"
git tag -a "v$NEW" -m "Voicollo LMS v$NEW"

echo
echo "Release v$NEW prepared. Publish it with:"
echo "  git push origin HEAD && git push origin v$NEW"
