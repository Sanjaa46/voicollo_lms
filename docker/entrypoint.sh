#!/bin/sh
# Voicollo LMS container entrypoint.
#   serve          start the web server (API + SPA). RUN_MIGRATIONS=true migrates first.
#   migrate        apply database migrations and sync DB user passwords, then exit
#   check-config   validate environment variables and exit
#   version        print the image version
# Anything else is executed as-is (e.g. `sh`).
set -eu

command="${1:-serve}"
[ "$#" -gt 0 ] && shift

case "$command" in
  serve)
    if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
      python -m app.cli migrate
    fi
    python -m app.cli check-config >/dev/null
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-2}" \
      --proxy-headers \
      --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
      --no-access-log \
      "$@"
    ;;
  migrate)      exec python -m app.cli migrate ;;
  check-config) exec python -m app.cli check-config ;;
  version)      echo "${LMS_BUILD_VERSION:-unknown} (${LMS_BUILD_SHA:-unknown})" ;;
  *)            exec "$command" "$@" ;;
esac
