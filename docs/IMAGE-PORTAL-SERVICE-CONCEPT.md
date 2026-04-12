# Image Portal Service Concept (Landing Page + Download API)

Date: 2026-04-12
Status: design + bootstrap implementation started

Related: [ONLINE-FLASH-CONCEPT.md](ONLINE-FLASH-CONCEPT.md),
[ONLINE-FLASH-UPDATE-KEY.md](ONLINE-FLASH-UPDATE-KEY.md)

## Goal

Provide a first-class image portal service for manual downloads and machine-safe
API access, replacing ad-hoc feed scripts with:

- better UX for humans (landing page),
- strict machine/API contracts for clients,
- hard security defaults.

The service is independent from STB runtime and should live in its own git repo,
with dedicated packaging/deployment integration.

## NI Reference and Delta

Reference analyzed:

- `ni-buildsystem/support/online-update/update.php`
- `ni-buildsystem/support/online-update/get-image.php`
- `ni-buildsystem/support/online-update/get-kernel.php`

Observed NI pattern:

- query-string based routing,
- filesystem globbing,
- model mapping directly in PHP condition chains,
- plain text update list composition.

Target delta:

- no direct filesystem globbing from request parameters,
- no implicit model mapping in code branches,
- signed/validated feed metadata as source of truth,
- typed API + compatibility adapter endpoint(s).

## Service Boundaries

### In Scope

- public landing page for manual image download,
- read-only API for update clients and tooling,
- legacy adapter for old update-query consumers,
- secure artifact links + checksum visibility.

### Out of Scope

- flashing logic on STB (handled by `/usr/bin/flash` stack),
- feed publishing business logic in Neutrino runtime,
- package feed (opkg) browsing.

## Repository Plan

Canonical repository:

- `git@github.com:tuxbox-neutrino/image-portal-service.git`

Suggested structure:

```text
image-portal-service/
  api/                    # backend (PHP 8.3, strict types)
  web/                    # static frontend (cards/tables/search)
  schemas/
    manifest.schema.json
    catalog.schema.json
  deploy/
    nginx.conf
    caddy/Caddyfile
    systemd/
    docker/
      Dockerfile
      docker-compose.yml
      .env.example
  tools/
    catalog-build         # reads publish dir, builds catalog
  tests/
    api/
    security/
    snapshots/
```

## Data Model

### Source of Truth

Input is generated from published feed artifacts per machine:

- `manifest.json`
- `*.zip`
- `*.sha256`
- optional `changelog.txt`

Portal builds immutable catalog entries from manifests only.

Important:

- Portal catalog is a derived index. Source of truth remains the published
  machine feed artifacts (`manifest.json` + payload + checksums).

### Retention policy

The portal MUST retain historical builds per `channel` + `imagedir` —
not just the latest. Rationale:

- Online Flash exposes a "Browse older builds" flow that directly
  calls `GET /api/v1/catalog?channel=...&imagedir=...`
  (see [ONLINE-FLASH-CONCEPT.md](ONLINE-FLASH-CONCEPT.md#historical-builds-browse--flash-older-images)),
- users must be able to roll back to a known-good build when a new
  release regresses on their hardware,
- `git_hash`/`describe` traceability is only useful if the build it
  points to is still downloadable.

Rules:

- No implicit pruning by the catalog builder. Artifacts that are
  present under the published feed must appear in `catalog.json`.
- Operator-initiated pruning (to free disk space) is a deploy-host
  operation and must be explicit: delete artifacts + rerun
  `make portal-catalog`.
- `GET /api/v1/catalog` returns all retained builds, sorted
  newest-first, without a hidden default limit. Pagination is via an
  explicit `?limit=<n>&offset=<n>` query pair.
- `GET /api/v1/images/{imagedir}/latest` remains the convenience
  endpoint for "give me the newest".

### Catalog Object (normalized)

Minimum fields:

- `channel` (`release|beta|nightly`)
- `distro_version`
- `imagedir`
- `machine`
- `build_date`
- `image_version`
- `image_name`
- `flash_backend`
- `files[]` (pass-through from manifest; at least one entry with
  `name/size/sha256`)

Optional:

- `describe`
- `git_hash`
- `rollback` object
- `notes/changelog_url`
- `download_url` (derived convenience field for primary file only)

## API Design

### Versioning

- REST prefix: `/api/v1`

### Endpoints

- `GET /api/v1/catalog?channel=nightly&imagedir=hd60`
- `GET /api/v1/machines`
- `GET /api/v1/images/{imagedir}/latest?channel=nightly`
- `GET /api/v1/images/{imagedir}/{build_date}`
- `GET /api/v1/download/{imagedir}/{build_date}/{filename}`
  - returns 302 redirect to static artifact location

### Legacy Compatibility Endpoint

Provide adapter endpoint:

- `GET /legacy/update.php?...`

Behavior:

- parse legacy parameters,
- map to catalog query,
- return text format compatible with old consumers.

No direct filesystem access in this path.

## Frontend UX

### Core UX

- machine cards with latest stable/nightly badges,
- clear channel switch (`Release`, `Beta`, `Nightly`),
- searchable/filterable table,
- one-click copy for checksum,
- "How to verify checksum" helper section,
- changelog/commit links when available.

### Download UX

Per image detail page:

- filename + size + sha256,
- build date + version + backend,
- optional rollback note,
- direct download button,
- alternate mirror links (if configured).

### Accessibility/Performance

- keyboard navigable,
- semantic HTML landmarks,
- no hard dependency on JS for critical actions,
- mobile-first layout.

## Security Model

### Update Key (Phase 1 access gate)

Every catalog and download endpoint is gated by a shared Update Key,
sent as HTTP header `X-Tuxbox-Update-Key`. Full contract in
[ONLINE-FLASH-UPDATE-KEY.md](ONLINE-FLASH-UPDATE-KEY.md).

Portal behavior:

- **Missing header** -> `401 Unauthorized`,
  body `{ "error": "missing_update_key" }`.
- **Invalid key** -> `403 Forbidden`,
  body `{ "error": "invalid_update_key" }`.
- Valid key -> normal response.

Implementation requirements:

- Key allowlist configured via environment variable
  `IMAGE_PORTAL_UPDATE_KEYS` (comma-separated to allow rotation).
- Constant-time comparison.
- Failed attempts rate-limited per source IP.
- Failed attempts logged with correlation ID, IP, endpoint,
  timestamp — but never the attempted key value.
- Phase 2 reserves two more headers (`X-Tuxbox-Box-Id`,
  `X-Tuxbox-Box-Proof`); Phase 1 ignores them if present (graceful
  upgrade path).

### Security Requirements

- strict input allowlist (`channel`, `imagedir`, `build_date`, `filename`),
- no user-controlled path joins,
- no shell execution from request handlers,
- read-only service account,
- immutable artifact storage for released builds.

### Transport and Headers

- HTTPS only,
- HSTS,
- CSP (`default-src 'self'` + explicit exceptions),
- `X-Content-Type-Options: nosniff`,
- `Referrer-Policy: no-referrer`.

### Abuse Protection

- rate limiting per IP and endpoint class,
- simple bot defense for bulk scraping abuse,
- download endpoint audit log with correlation ID.

### Supply Chain Integrity

Phase 1:

- verify checksum file matches manifest before publication.

Phase 2:

- signature verification (`manifest.json.sig`) at catalog build/import time.

## Deployment and Packaging

### Runtime Packaging (Recipe)

Add dedicated recipe in a separate service layer/repository
(`meta-tuxbox-services`), not in default STB image layers:

- `recipes-support/image-portal/image-portal-service_git.bb`

Recipe responsibilities:

- install backend code to `/usr/share/image-portal/api`,
- install frontend assets to `/usr/share/image-portal/web`,
- install webserver vhost template (`nginx` or `caddy`),
- install systemd service for catalog refresh worker (timer-based).

Notes:

- this is a server-side package; never part of default STB runtime images.
- keep it opt-in for dedicated server builds/deploy hosts only.

### Deployment Model

Recommended production deployment:

- container or VM with reverse proxy (`nginx`/`caddy`) + PHP-FPM,
- read-only bind mount for published artifacts,
- catalog cache on local fast storage.

### Docker (Phase 1 monolithic container)

Goal: operator runs `docker compose up -d` and gets a working portal.

Image contents (single container):

- nginx + php-fpm + catalog refresh worker (systemd-less, supervisor
  or a small entrypoint script),
- runtime PHP code under `/usr/share/image-portal/api`,
- static landing page assets under `/usr/share/image-portal/web`,
- no artifact data inside the image (always bind-mounted).

Dockerfile constraints:

- base image: a slim Debian or Alpine PHP 8.3 + nginx combination,
- no build tooling retained in the final layer,
- non-root runtime user matching the `image-portal` system user,
- multi-arch build via `docker buildx`:
  - `linux/amd64`,
  - `linux/arm64`,
  - `linux/arm/v7` (Raspberry Pi),
- release tags pushed to GHCR under
  `ghcr.io/tuxbox-neutrino/image-portal-service`.

Runtime configuration via `docker-compose.yml` + `.env`:

```yaml
services:
  portal:
    image: ghcr.io/tuxbox-neutrino/image-portal-service:latest
    ports:
      - "${PORTAL_PORT:-8080}:80"
    environment:
      IMAGE_PORTAL_UPDATE_KEYS: "${UPDATE_KEYS}"
      IMAGE_PORTAL_ARTIFACT_DIR: "/srv/artifacts"
      IMAGE_PORTAL_CATALOG_REFRESH_INTERVAL: "${CATALOG_REFRESH_INTERVAL:-300}"
      IMAGE_PORTAL_ALLOWED_CHANNELS: "release,beta,nightly"
    volumes:
      - "${ARTIFACT_DIR}:/srv/artifacts:ro"
      - portal_catalog:/var/cache/image-portal
    restart: unless-stopped
volumes:
  portal_catalog:
```

`.env.example` ships with safe defaults and clearly placeholder values
for `UPDATE_KEYS` and `ARTIFACT_DIR`.

### Split-container deployment (Phase 2)

Phase 2 splits nginx / php-fpm / catalog refresh worker into separate
containers for easier scaling and clean single-responsibility. Phase 1
deliberately does not ship this to keep the first public release
trivial to deploy.

### Buildsystem Integration

Add helper in builder repo (script/make target):

- `make portal-catalog`
  - scans published machine directories,
  - validates manifests/checksums,
  - emits normalized `catalog.json`.

- `make portal-sync`
  - syncs `catalog.json` + static assets to portal host.

## Integration with Existing Concepts

This portal complements:

- `docs/ONLINE-FLASH-CONCEPT.md`
- `docs/FLASH-NEUTRINO-INTEGRATION-CONCEPT.md`

Usage relationship:

- Neutrino online flash consumes static feed by default and may optionally use
  the portal API via `image_discovery_api_url`.
- Humans use landing page for manual download.
- Legacy clients use compatibility adapter endpoint temporarily.

## Rollout Plan

### Phase A

- implement portal read-only API + static landing page,
- ingest existing feed artifacts,
- enable legacy adapter endpoint.

### Phase B

- switch online-flash discovery to manifest-first API URLs,
- keep legacy endpoint active for compatibility window.

### Phase C

- enforce signed manifests in ingest pipeline,
- deprecate legacy endpoint and legacy marker path with announced sunset date.

## Go/No-Go Criteria

1. API never serves artifacts not present in validated catalog.
2. Legacy endpoint matches expected old client format for pilot machines.
3. Downloaded file checksum on portal page always matches published SHA256.
4. Security checks pass:
- path traversal tests,
- invalid parameter fuzz tests,
- rate limit behavior.
5. Manual UX validation on desktop + mobile completed.

## Immediate Next Steps

1. Freeze manifest/canonical catalog schema.
2. Add signature verification in catalog build/import (`manifest.json.sig`).
3. Add compatibility adapter tests using NI-style query fixtures.
4. Pin recipe `SRCREV` from `AUTOREV` once first integration test passes.

## Bootstrap Implementation Status (2026-03-10)

Implemented baseline:

- Repository scaffold:
  - manifest-first API endpoints:
    - `/api/v1/catalog.php`
    - `/api/v1/latest.php`
    - `/api/v1/download.php`
  - legacy adapter:
    - `/legacy/update.php`
    - `/legacy/get-image.php`
    - `/legacy/get-kernel.php` (explicitly deprecated response)
  - catalog generation tool:
    - `tools/build-catalog.php`

- Packaging scaffold in `meta-tuxbox`:
  - `recipes-support/image-portal/image-portal-service_git.bb`
  - installs runtime under `/usr/share/image-portal`
  - adds catalog refresh helper + systemd timer
  - adds nginx vhost template
- host-side helper workflow in builder:
  - `scripts/portal-catalog.sh`
  - `make portal-catalog`
  - `make portal-sync`

Open follow-up work:

1. Implement Update Key validation on all API endpoints
   (see [ONLINE-FLASH-UPDATE-KEY.md](ONLINE-FLASH-UPDATE-KEY.md)).
2. Add multi-arch Docker build (`linux/amd64`, `linux/arm64`,
   `linux/arm/v7`) with docker-compose reference deployment.
3. Complete production key-management rollout for manifest signature
   verification (catalog builder support is implemented, deployment policy TBD).
4. Add API contract tests and legacy fixture tests.
5. Add production deployment docs (`nginx/php-fpm/caddy` variants).
6. Add optional frontend catalog/detail pages beyond the minimal landing page.
