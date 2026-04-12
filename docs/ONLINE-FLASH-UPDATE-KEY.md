# Online Flash Update Key

Date: 2026-04-12
Status: design

Deutsch: [de/ONLINE-FLASH-UPDATE-KEY.md](de/ONLINE-FLASH-UPDATE-KEY.md)

## Purpose

The Online Flash feature exposes an HTTP-reachable image portal service
(`tuxbox-neutrino/image-portal-service`). Because that service can be hosted
on the public internet, every catalog and download endpoint must be gated
by a shared **Update Key** that travels:

1. from the build system into the image (compile-time default baked into
   Neutrino + `image_update_key=` seeded into `/etc/image-version`),
2. from the image into Neutrino settings (user-editable, masked input),
3. from Neutrino into the `flash-online-check` helper as an explicit
   `--key <value>` argument on every invocation,
4. from the helper into every portal HTTP request as HTTP header
   `X-Tuxbox-Update-Key`,
5. into the portal validation layer.

**Ownership rule (single source of truth):** Neutrino is the sole owner
of the *effective* key at runtime. The helper `flash-online-check` is a
dumb transport: it never consults Neutrino settings, `/etc/image-version`,
or any compile-time default on its own. It uses whatever key the caller
hands in via `--key` (or, for headless callers without a Neutrino
settings context, via the `TUXBOX_UPDATE_KEY` environment variable).
This keeps the resolution logic in exactly one place and avoids the
drift that a multi-layer fallback chain would create between Neutrino,
the helper, and APIv4/WebIF daemons.

The key is *not* a cryptographic authentication primitive. It is a shared
read-token that keeps public endpoints unindexable and blocks casual
scraper traffic while Phase 1 runs without per-box identity.

Per-box key binding (serial-based) is an explicit Phase 2 extension and is
designed-in, not retrofitted.

## Non-Goals

- not a replacement for HTTPS transport security,
- not a replacement for signed manifests (tracked separately in
  `docs/ONLINE-FLASH-CONCEPT.md` Phase E and
  `docs/IMAGE-PORTAL-SERVICE-CONCEPT.md` "Supply Chain Integrity"),
- not used by the legacy `CFlashUpdate` path.

## Mechanism Overview (Phase 1)

```
local.conf (optional override)
    |
    v
tuxbox.conf  TUXBOX_ONLINE_UPDATE_KEY ?= "<distro-wide placeholder>"
    |
    v
neutrino.inc  ONLINE_UPDATE_KEY ?= "${TUXBOX_ONLINE_UPDATE_KEY}"
              configure: --with-online-update-key="${ONLINE_UPDATE_KEY}"
    |
    v
Neutrino build: compile-time default constant
    |
    v
Runtime: Neutrino settings file can override compile-time default
    |
    v
Neutrino resolves effective key (settings > compile-time default)
    |
    v
Neutrino invokes  flash-online-check --key <effective> ...
    (helper is a dumb transport, never reads settings itself)
    |
    v
HTTP request: X-Tuxbox-Update-Key: <key>
    |
    v
image-portal-service validates header, serves catalog/download
```

The same pattern is used today for `TMDB_DEV_KEY`, `OMDB_API_KEY` and
similar keys (see `meta-neutrino/recipes-neutrino/neutrino/neutrino.inc`),
so this is an additive key — no new mechanism, no ni-pick breakage.

## Build-Side Contract

### Variable placement

- **Distro default**: `meta-tuxbox/conf/distro/tuxbox.conf`

  ```bitbake
  # Shared read-token for the image portal service.  Keeps public
  # endpoints unindexable.  Can be overridden per-site in local.conf.
  TUXBOX_ONLINE_UPDATE_KEY ?= "XXXXXXXXXXXXXXXX"
  ```

  The placeholder value is a *build default*, not a secret. Any deployment
  that exposes the portal on the public internet MUST override it in
  `local.conf` (or a site-specific conf) with a non-placeholder value.

- **Neutrino consumer**: `meta-neutrino/recipes-neutrino/neutrino/neutrino.inc`

  ```bitbake
  ONLINE_UPDATE_KEY ?= "${TUXBOX_ONLINE_UPDATE_KEY}"

  EXTRA_OECONF += " \
      --with-online-update-key=\"${ONLINE_UPDATE_KEY}\" \
  "
  ```

  `ONLINE_UPDATE_KEY` indirection keeps parity with the existing key
  variables (`TMDB_DEV_KEY`, `OMDB_API_KEY`, ...) so Neutrino recipe
  changes stay local to `neutrino.inc`.

### Image metadata

`meta-tuxbox/classes/tuxbox-version.bbclass` additionally writes the
build-time default key into `/etc/image-version` as `image_update_key`.

Rationale: the key in `/etc/image-version` is a **seed value** used on
first boot to initialize the Neutrino setting if no user value is
present yet, and as a recovery reference when inspecting an image
manually. It is **not** a live fallback for runtime callers — at
runtime, Neutrino alone resolves the effective key and hands it to
the helper.

`/etc/image-version` is chosen because it is already the canonical
runtime metadata file and has a defined contract
(`docs/IMAGE_VERSION_CONTRACT.md`).

### `local.conf` example

```bitbake
# Site-specific portal token.  Do NOT commit this to a public layer.
TUXBOX_ONLINE_UPDATE_KEY = "s3cret-site-token-goes-here"
```

## Neutrino UX Contract

### Setting placement

A single menu entry:

```
Service Menu
  +-- Software Update
        +-- Online Flash Settings   (new container)
              +-- Update Server URL     (pre-filled from image_update_url)
              +-- Online Update Key     (pre-filled from compile-time default)
              +-- Channel                (release | beta | nightly)
              +-- Discovery API (opt.)  (image_discovery_api_url override)
```

The existing legacy `update_url` setting is **not** duplicated. If the
CFlashManager runtime capabilities are present, the legacy
`CFlashUpdate` menu entry is hidden (see "Legacy Coexistence"), and
the settings move into the `CFlashManager` container above. If the new
runtime is absent, the legacy setting surface remains untouched.

### Input rules

- Empty "Online Update Key" field means: use compile-time default.
- Non-empty value is persisted in Neutrino settings and overrides the
  compile-time default on every request.
- The menu entry is a password-style input (masked) so casual
  shoulder-surfing does not leak the token.
- A small hint text explains: "Shared token for the image portal.
  Leave empty to use the factory default."

### Storage

Store under an `online_update.*` namespace in the Neutrino config file,
parallel to the existing `tmdb_*`, `omdb_*` groups:

- `online_update_server_url`
- `online_update_key`
- `online_update_channel`
- `online_update_discovery_api_url`

Default population is **per setting**, not one shared fallback chain:

- `online_update_key`:
  1. Neutrino setting value (if non-empty),
  2. compile-time default (`--with-online-update-key`).
  `/etc/image-version` `image_update_key=` is only a first-boot seed /
  recovery reference and is never consulted as a live runtime fallback.
- `online_update_server_url`:
  1. Neutrino setting value (if non-empty),
  2. `/etc/image-version` `image_update_url=`.
- `online_update_channel`:
  1. Neutrino setting value (if non-empty),
  2. `/etc/image-version` `channel=`,
  3. UI default `release` if neither is populated.
- `online_update_discovery_api_url`:
  1. Neutrino setting value (if non-empty),
  2. `/etc/image-version` `image_discovery_api_url=`.

### Legacy coexistence

Rule: when the new flash runtime is available
(`/usr/bin/flash`, `/etc/tuxbox/flash-machine-profile.conf`,
`/etc/tuxbox/flash-backend.conf`), **hide** the legacy `CFlashUpdate`
menu entry — do not just disable it. This avoids confusing the user
with two visually similar flash flows.

Shared settings (update server, update key, channel) remain visible in
one place. The UI must not duplicate them between legacy and new
containers — users should never be forced to configure the same thing
twice.

On older hardware where the new runtime is missing, the legacy menu
stays unchanged, the new container is never instantiated, and the
key/server settings are not exposed.

## Runtime Transport Contract

### HTTP header

All requests from `flash-online-check` (and any APIv4/WebIF caller) to
the portal send the key as a HTTP header:

```
GET /api/v1/images/hd60/latest?channel=release HTTP/1.1
Host: portal.example.org
X-Tuxbox-Update-Key: <effective-key>
User-Agent: tuxbox-flash-online-check/<version>
```

**Never in a query string.** Query strings appear in server access
logs, intermediate proxies, and browser history; header values do not
(in well-configured stacks).

### Key resolution order

Effective key resolution happens exactly once, in Neutrino, before
invoking the helper:

1. Neutrino setting `online_update.online_update_key` (if non-empty),
2. compile-time default constant (baked in via
   `--with-online-update-key`).

Neutrino then calls:

```
flash-online-check --key <effective> [--catalog|--build <d>|...] [--json]
```

`flash-online-check` itself has a strict two-entry precedence:

1. `--key <value>` CLI argument (authoritative when present),
2. `TUXBOX_UPDATE_KEY` environment variable (headless fallback for
   callers that do not pass `--key`, e.g. APIv4/WebIF daemon
   inheritance or manual shell invocation).

The helper deliberately does **not** consult `/etc/image-version`,
the Neutrino settings file, or any compile-time default. This keeps
the helper stateless, testable from the shell, and free of runtime
coupling to the Neutrino settings layout.

If neither `--key` nor `TUXBOX_UPDATE_KEY` is set, the helper exits
with code `3` (preflight failure, reason "missing key").

## Portal Validation Contract

The image portal service enforces the key on every catalog/download
endpoint:

- **Missing header**: HTTP `401 Unauthorized` with body
  `{ "error": "missing_update_key" }`.
- **Invalid key**: HTTP `403 Forbidden` with body
  `{ "error": "invalid_update_key" }`.
- **Valid key**: normal response.

The key is compared against a server-side allowlist (configured via
environment variable `IMAGE_PORTAL_UPDATE_KEYS`, comma-separated to
allow rotation), using a constant-time comparison.

### Rate limiting and logging

- Failed-key attempts are rate-limited per source IP.
- Failed-key attempts are logged with correlation ID, source IP,
  endpoint, and timestamp — but **never** the attempted key value.

### Phase 2 extension hook

The header transport is explicitly designed to carry a second header
for per-box identity in Phase 2:

```
X-Tuxbox-Update-Key: <shared key>
X-Tuxbox-Box-Id: <per-box serial>
X-Tuxbox-Box-Proof: <signed timestamp>
```

Phase 1 ignores the latter two headers if present, so a Phase 2 client
can safely send them against a Phase 1 portal (graceful upgrade path).

## Exit Code Mapping

Contract with `docs/ONLINE-FLASH-CONCEPT.md` "Exit Codes (Stable)":

| HTTP | Helper exit | Neutrino locale |
|------|-------------|-----------------|
| 200  | `0`         | success         |
| 401  | `3`         | `LOCALE_FLASHMANAGER_ERROR_PREFLIGHT` (reason: missing key) |
| 403  | `3`         | `LOCALE_FLASHMANAGER_ERROR_PREFLIGHT` (reason: invalid key) |
| 404  | `2`         | `LOCALE_FLASHMANAGER_ERROR_INPUT`     |
| 429  | `3`         | `LOCALE_FLASHMANAGER_ERROR_PREFLIGHT` (reason: rate limited) |
| 5xx  | `1`         | `LOCALE_FLASHMANAGER_ERROR_GENERIC`   |

The rationale for folding 401/403 into preflight (exit 3) instead of
coining a new exit code is that the user-visible action is the same:
"check your Update Key / Update Server setting and try again".

## Security Notes

### Phase 1 threat model

- **Protected against**: search engine indexing, mass scraping, casual
  leechers, accidental public exposure of artifact directories.
- **Not protected against**: key leak (any leaked key grants full
  read access until rotated), replay attacks, traffic analysis.

### Key rotation

Phase 1 supports rotation via the comma-separated
`IMAGE_PORTAL_UPDATE_KEYS` allowlist. Operators can add a new key, wait
until deployed images carry it, then drop the old key. No client-side
coordination required.

### Phase 2 threat model (future)

Phase 2 adds per-box identity so a leaked shared key alone does not
grant access. The signed-timestamp proof in `X-Tuxbox-Box-Proof` is
the intended mechanism; exact signature format is out of scope for
this document.

## Open Items

- Exact Neutrino settings key names (to be finalized during
  implementation; UX review pass before freezing).
- Configure-time autotools fragment for `--with-online-update-key`
  (new entry in Neutrino `configure.ac` mirroring the existing
  `--with-tmdb-api-key` block).
- Menu container class choice (re-use existing `CMenuForwarder` idiom
  from CFlashManager Phase 1).
- Test vectors for portal validation (invalid key, missing header,
  rate-limit window, rotation window).

## References

- [docs/ONLINE-FLASH-CONCEPT.md](ONLINE-FLASH-CONCEPT.md)
- [docs/FLASH-NEUTRINO-INTEGRATION-CONCEPT.md](FLASH-NEUTRINO-INTEGRATION-CONCEPT.md)
- [docs/IMAGE-PORTAL-SERVICE-CONCEPT.md](IMAGE-PORTAL-SERVICE-CONCEPT.md)
- [docs/IMAGE_VERSION_CONTRACT.md](IMAGE_VERSION_CONTRACT.md)
