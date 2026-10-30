#!/usr/bin/env bash
# Build the single LMS image, tagged with the version from ./VERSION.
#   scripts/build-image.sh                 -> voicollo-lms:<VERSION> (+ :latest)
#   IMAGE=ghcr.io/sanjaa46/voicollo-lms PUSH=1 scripts/build-image.sh
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-voicollo-lms}"
VERSION="$(tr -d '[:space:]' < VERSION)"
GIT_SHA="$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "warning: working tree has uncommitted changes; image will be tagged ${VERSION} anyway" >&2
  GIT_SHA="${GIT_SHA}-dirty"
fi

docker build ${BUILD_ARGS:-} \
  --build-arg VERSION="$VERSION" \
  --build-arg GIT_SHA="$GIT_SHA" \
  --build-arg BUILD_DATE="$BUILD_DATE" \
  -t "${IMAGE}:${VERSION}" \
  -t "${IMAGE}:latest" \
  .

echo "built ${IMAGE}:${VERSION} (${GIT_SHA})"
if [ "${PUSH:-0}" = "1" ]; then
  docker push "${IMAGE}:${VERSION}"
  docker push "${IMAGE}:latest"
fi
