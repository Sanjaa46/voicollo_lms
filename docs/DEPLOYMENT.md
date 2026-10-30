# Deployment

The LMS ships as **one Docker image** — `ghcr.io/sanjaa46/voicollo-lms:<version>` —
that contains the web console, the API and the database migrations. A server
needs only two files from this repository:

```
deploy/docker-compose.yml
deploy/.env            (from deploy/.env.example)
```

They are also attached to every GitHub release.

## 1. First installation

**Prerequisites:** Docker Engine 24+ with the Compose plugin.

1. **Create a GitHub OAuth app** (github.com → Settings → Developer settings →
   OAuth Apps → New):
   - Homepage URL: your `PUBLIC_URL`, e.g. `https://lms.example.com`
   - Authorization callback URL: `https://lms.example.com/auth/callback`

2. **Prepare the folder:**

   ```bash
   mkdir -p /opt/voicollo-lms && cd /opt/voicollo-lms
   curl -fsSLO https://raw.githubusercontent.com/Sanjaa46/voicollo_lms/v2.0.0/deploy/docker-compose.yml
   curl -fsSL  https://raw.githubusercontent.com/Sanjaa46/voicollo_lms/v2.0.0/deploy/.env.example -o .env
   ```

3. **Fill in `.env`.** Every `REQUIRED` value must be set. Generate each secret
   separately:

   ```bash
   openssl rand -hex 32
   ```

4. **Validate and start:**

   ```bash
   docker compose run --rm lms-app check-config
   docker compose up -d
   docker compose ps          # lms-app should become "healthy"
   ```

   `lms-migrate` runs once per `up`. It creates the schema and the
   least-privilege DB users `lms_app` / `lms_retention`, then exits.

5. Open `PUBLIC_URL` and sign in with the GitHub account in
   `ALLOWED_GITHUB_USERNAME`.

6. **Register your services** (Services → Register service). Then configure each
   producer with `LMS_URL`, `LMS_INGEST_SECRET` (= `INGEST_SIGNING_SECRET`) and
   its service id. The Services page shows ready-to-paste snippets.

### Exposing it

- **Reverse proxy (nginx/Caddy/Traefik):** keep `LMS_BIND_ADDRESS=127.0.0.1` and
  proxy to `127.0.0.1:${LMS_HTTP_PORT}`. The app trusts `X-Forwarded-*` headers.
- **Cloudflare Tunnel:** set `CLOUDFLARE_TUNNEL_TOKEN`, point the tunnel's public
  hostname at `http://lms-app:8000`, and run
  `docker compose --profile tunnel up -d`.

## 2. Upgrading

```bash
cd /opt/voicollo-lms
./backup.sh                          # see §4 — always back up first
sed -i 's/^LMS_VERSION=.*/LMS_VERSION=2.1.0/' .env
docker compose pull
docker compose up -d                 # runs migrations, then restarts the app
```

Read the release notes / `CHANGELOG.md` first. Anything under **Breaking** may
need a `.env` change. Running `docker compose run --rm lms-app check-config`
after editing `.env` catches mistakes before the restart.

### Rollback

Migrations only move forward, so a rollback means restoring the backup taken
before the upgrade:

```bash
sed -i 's/^LMS_VERSION=.*/LMS_VERSION=<previous>/' .env
docker compose down
# restore the database (§4), then:
docker compose up -d
```

Patch releases (x.y.**Z**) never contain migrations and can be rolled back by
changing `LMS_VERSION` alone.

## 3. Migrating from v1 (separate api + nginx containers)

1. Back up the v1 database:
   `docker exec lms-db mariadb-dump -uroot -p"$DB_ROOT_PASSWORD" --single-transaction lms > lms-v1.sql`
2. Stop v1 **without** deleting volumes: `docker compose down` (no `-v`) in the
   old project folder.
3. Find the old volume name: `docker volume ls | grep db_data`. It is usually
   `voicollo_lms_lms_db_data`. Put it in the new `.env`:
   `LMS_DB_VOLUME=voicollo_lms_lms_db_data`.
4. Map the old variables to the new `.env`:

   | v1 | v2 |
   |---|---|
   | `FRONTEND_URL`, `VITE_API_BASE_URL` | `PUBLIC_URL` (one origin for UI + API) |
   | `LMS_APP_DB_PASSWORD` | `DB_APP_PASSWORD` |
   | `LMS_RETENTION_DB_PASSWORD` | `DB_RETENTION_PASSWORD` |
   | `DB_ROOT_PASSWORD` | unchanged |
   | `DATABASE_URL`, `RETENTION_DATABASE_URL`, `ROOT_DATABASE_URL`, `REDIS_URL` | remove — built from the passwords above |
   | `APP_VERSION` | remove — use `LMS_VERSION` |
   | `TZ` | `SCHEDULER_TIMEZONE` |

5. In the GitHub OAuth app, set the callback URL to `<PUBLIC_URL>/auth/callback`.
6. `docker compose up -d`. Migration `0004`:
   - converts timestamps to millisecond precision,
   - adds `audit_logs.environment`,
   - shifts v1's `ingested_at` values from UTC+8 to UTC. Set
     `LMS_LEGACY_TZ_OFFSET_HOURS=0` beforehand if your v1 database ran in UTC.

## 4. Backups

Example `backup.sh` (run from cron daily):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /opt/voicollo-lms
set -a; . ./.env; set +a
mkdir -p backups
docker compose exec -T lms-db mariadb-dump -uroot -p"$DB_ROOT_PASSWORD" \
  --single-transaction --routines lms | gzip > "backups/lms-$(date +%F-%H%M).sql.gz"
find backups -name 'lms-*.sql.gz' -mtime +14 -delete
```

Restore:

```bash
gunzip -c backups/lms-YYYY-MM-DD-HHMM.sql.gz | \
  docker compose exec -T lms-db mariadb -uroot -p"$DB_ROOT_PASSWORD" lms
```

Redis holds only caches, sessions and counters. Losing it signs you out and
nothing else.

## 5. Operations

| Task | Command |
|---|---|
| Follow app logs | `docker compose logs -f lms-app` |
| Show version | `docker compose exec lms-app lms version` |
| Validate config | `docker compose run --rm lms-app check-config` |
| Re-run migrations | `docker compose run --rm lms-migrate` |
| Run retention now | System page → Run now (or `POST /api/v1/retention/run`) |
| Rotate DB passwords | change in `.env`, then `docker compose up -d` (migrate re-syncs users) |
| Rotate `INGEST_SIGNING_SECRET` | update `.env` and every producer; requests signed with the old secret get 401 |
| Rotate `JWT_SECRET_KEY` | signs the console out; nothing else |

### Troubleshooting

- **`lms-app` restarts with "Configuration invalid"** — run `check-config`; it
  lists every missing or invalid variable.
- **Sign-in says "not authorized"** — the GitHub login does not match
  `ALLOWED_GITHUB_USERNAME` (or `ALLOWED_GITHUB_USER_ID`).
- **Sign-in fails with `redirect_uri` mismatch** — the OAuth app's callback URL
  must equal `<PUBLIC_URL>/auth/callback`.
- **Producers get `SIGNATURE_EXPIRED`** — their clock is off by more than
  `SIGNATURE_TOLERANCE_SECONDS`; enable NTP.
- **Producers get `SERVICE_NOT_REGISTERED`** — register the service id first.

## 6. Building the image yourself

```bash
scripts/build-image.sh                     # -> voicollo-lms:<VERSION>
LMS_IMAGE=voicollo-lms docker compose ...  # in .env, to run your local build
```

Behind a TLS-intercepting proxy, pass its CA as a build secret (it is never
stored in the image):

```bash
BUILD_ARGS="--secret id=ca_bundle,src=/path/to/ca.crt" scripts/build-image.sh
```
