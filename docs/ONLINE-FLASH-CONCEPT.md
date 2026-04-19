# Online Flash Concept (Neutrino + Yocto/OE Deploy)

Date: 2026-04-12
Status: design + implementation in progress

Related: [SERVICE-KEY.md](SERVICE-KEY.md),
[FLASH-NEUTRINO-INTEGRATION-CONCEPT.md](FLASH-NEUTRINO-INTEGRATION-CONCEPT.md),
[IMAGE-PORTAL-SERVICE-CONCEPT.md](IMAGE-PORTAL-SERVICE-CONCEPT.md)

## Scope

Define a robust online-flash workflow for Neutrino that:

- uses `/usr/bin/flash` as the single runtime flash API,
- keeps legacy update paths available for older boxes,
- matches current Yocto/OE deploy artifacts and naming,
- delivers clear, fail-safe UX on real devices.

This document focuses on online flash only (feed discovery, update selection,
download/integrity, runtime execution, and UX behavior).

## Current Gaps (Observed)

1. Online metadata is incomplete in runtime:
- `/etc/image-version` currently has `image_update_url=` empty on tested images.

2. Filename mismatch risk:
- runtime metadata defaults `image_file_name=..._usb.zip`,
- current deploy artifacts for multiboot machines are `..._multi.zip`.

3. Legacy online marker file is not consistently present:
- current deploy output in tested build has no `imageversion` marker file.

Result: online flash cannot be considered deterministic yet.

Implementation update (2026-03-10, bootstrap):

- `meta-tuxbox/classes/tuxbox-version.bbclass` now contains feed metadata
  generation for deploy artifacts (`manifest.json`, `imageversion`, `*.sha256`)
  and updated runtime metadata keys (`image_manifest_file`,
  `image_discovery_api_url`, `channel`).
- Verification on a fresh image build and real hardware runtime is still
  pending.

## Target Feed Layout

### URL Pattern

Recommended canonical machine feed root:

`<feed_base>/<distro_version>/<imagedir>/`

Example:

`https://feed.tuxbox-neutrino.org/4.0.32/hd60/`

Rationale:

- `imagedir` is already present in `/etc/image-version`,
- avoids machine alias ambiguity,
- aligns with Yocto deploy folder semantics.

### Files Per Machine Feed

Required:

- `manifest.json`
- `<image-file>.zip`
- `<image-file>.zip.sha256`
- `imageversion` (legacy marker, plain text)

Optional:

- `manifest.json.sig`
- `changelog.txt`

### Deploy Mapping (Yocto/OE)

Source artifacts from:

`build/tmp-<machine>/deploy/images/<machine>/`

For multiboot targets, online image payload must point to
`*_multi.zip` by default.

## Manifest Contract

### Format

- UTF-8 JSON
- versioned schema via `schema_version`

### Required Fields

- `schema_version` (int)
- `channel` (`release|beta|nightly`)
- `distro` (string)
- `distro_version` (string)
- `machine` (string)
- `imagedir` (string)
- `image_name` (string)
- `image_version` (string)
- `build_date` (YYYYMMDDHHMMSS)
- `flash_backend` (`script|ofgwrite`)
- `files` (array, at least one file object)

Each `files[]` item:

- `name` (string)
- `size` (int bytes)
- `sha256` (hex string)

### Recommended Optional Fields

- `describe`
- `git_hash`
- `min_flash_pr` (minimum installed flash runtime revision)
- `rollback.safe_version_min`
- `rollback.requires_wipe`
- `changelog_url`
- `signature` (if inline signature model is used)

### Integrity Model

Phase 1:

- mandatory SHA256 sidecar and manifest hash field validation.

Phase 2:

- signed manifest (`manifest.json.sig`) using a shipped public key.

## Runtime Metadata Contract (`/etc/image-version`)

Keep existing keys stable and add only.

Required online keys:

- `image_update_url`
- `image_update_info_file` (legacy default: `imageversion`)
- `image_file_name` (legacy fallback for old clients)

New key for modern clients:

- `image_manifest_file` (default: `manifest.json`)
- `image_discovery_api_url` (optional portal/API endpoint)
- `image_service_key` (build-time default for portal access; runtime override
  via Neutrino settings. See [SERVICE-KEY.md](SERVICE-KEY.md).)

Important:

- For multiboot machines, set `image_file_name` to `*_multi.zip` in build-time
  metadata generation.
- Do not rely on `*_usb.zip` default where deploy does not produce it.

## Runtime API Contract (UI -> Flash Stack)

### Main Execution

`/usr/bin/flash <slot> <mode> [<arg>] [force]`

Where `<mode>` is:

- `online` (remote discovery + remote payload),
- `local` (requires absolute image directory as `<arg>`),
- `restore`.

Selector semantics:

- `online` without `<arg>` means "flash the latest build".
- `online <build_date>` means "flash the retained catalog entry with
  this canonical selector". The format is `YYYYMMDDHHMMSS` and is the
  **same canonical string** used by the manifest `build_date` field
  and the `build_date=` key in `/etc/image-version` — one format
  across portal, helper, runtime, and image metadata, no conversions.
- `local <absolute-image-dir>` means a caller-managed local image path.

Examples:

- `flash 3 online`
- `flash 3 online 20260403190212`
- `flash 3 online force`
- `flash 3 online 20260403190212 force`
- `flash 2 local /media/hdd/images/hd60`
- `flash 4 restore`

### Pre-Check API (new helper)

Introduce:

```
flash-online-check [--json] [--key <value>]                 # latest vs current
flash-online-check --catalog [--json] [--channel <ch>]      # full list
          [--limit <n>] [--key <value>]
flash-online-check --build <build_date> [--json]            # specific build
          [--channel <ch>] [--key <value>]
```

Responsibilities:

- load `/etc/image-version`,
- consume the Service Key as `--key <value>` CLI argument (or, as a
  headless fallback, from environment `TUXBOX_SERVICE_KEY`). The helper
  is a dumb transport: it never reads Neutrino settings, never reads
  `image_service_key=` from `/etc/image-version`, and has no
  compile-time default. Neutrino (the sole key owner) resolves the
  effective key and always passes it in via `--key`. See
  [SERVICE-KEY.md](SERVICE-KEY.md),
- send the key as HTTP header `X-Tuxbox-Service-Key` on every request
  (omitted entirely when key is empty — keyless/LAN mode),
- fetch/validate `manifest.json` (fallback to legacy `imageversion` marker),
- compare local vs remote version/build (default mode),
- return the full available build list (`--catalog`),
- return a specific historical build manifest (`--build`),
- return clear machine-readable result.

Discovery source priority:

1. `image_discovery_api_url` (if present),
2. `image_update_url` + `image_manifest_file`,
3. legacy `image_update_info_file` marker (`imageversion`).

Output:

- human mode: concise status text,
- `--json`: structured result for Neutrino UI.
- `--catalog --json`: array of build entries newest-first, each entry
  containing the canonical manifest fields
  (`build_date`, `image_version`, `image_name`, `describe`, `git_hash`,
  `flash_backend`, `files[]` with `name`/`size`/`sha256`,
  optional `changelog_url`, optional `rollback` object).

Portal HTTP responses are mapped to the stable exit codes below. 401
(missing key) and 403 (invalid key) both collapse to exit `3`
(preflight failure) because the user action is the same: check the
Service Key setting. See
[SERVICE-KEY.md](SERVICE-KEY.md#exit-code-mapping).

### Exit Codes (Stable)

- `0` success
- `1` generic failure
- `2` invalid input/no valid image source
- `3` preflight failure
- `4` write failure
- `5` integrity/verification failure
- `6` active-slot policy blocked
- `127` missing backend/runtime binary

Backend precedence rule:

- local runtime configuration (`/etc/tuxbox/flash-backend.conf`,
  `/etc/tuxbox/flash-machine-profile.conf`) always overrides manifest backend
  hints. Manifest `flash_backend` is informational.

### Progress/Status Channel

Current logging path:

- `/var/log/tuxbox/flash-backend-ofgwrite.log`

Recommended additional structured status file:

- `/run/tuxbox/flash/status.json`

Updated by backend phases:

- `discover`, `download`, `verify`, `prepare`, `write_kernel`, `write_rootfs`,
  `finalize`, `done`, `error`.

This status contract is shared with Neutrino flash integration and treated as
stable API once introduced.

### APIv4/WebIF Preparation Contract

Planned APIv4 endpoints should be thin wrappers over existing runtime tools:

- `POST /api/v4/flash/precheck` -> `flash-online-check --json`
- `POST /api/v4/flash/start` -> `/usr/bin/flash <slot> online [<build_date>] [force]`
- `GET /api/v4/flash/status` -> read `/run/tuxbox/flash/status.json`
- `POST /api/v4/opkg/precheck` -> feed/repo reachability + lock checks
- `POST /api/v4/opkg/run` -> controlled opkg action with explicit mode
- `GET /api/v4/opkg/status` -> structured task state/result

Requirement: API layer must not implement backend heuristics itself; it only
validates inputs, starts runtime commands, and maps stable exit/result codes.

## Neutrino UX Flow (Best UX Requirements)

### Screen Flow

1. Open "Online Flash" menu.
2. Capability check:
- if runtime requirements are present (`/usr/bin/flash`,
  `/etc/tuxbox/flash-backend.conf`, `/etc/tuxbox/flash-machine-profile.conf`),
  the new online flow is exposed and the legacy `CFlashUpdate` menu
  entry is **hidden** (not greyed out — see "Legacy Coexistence"),
- if runtime requirements are missing, the new flow is not instantiated
  and the legacy path stays unchanged.
3. Fetch update info (manifest first, fallback legacy marker).
4. Show update card:
- current version/build,
- available version/build,
- changelog summary (if available),
- image size,
- backend info (`script`/`ofgwrite`).
5. Slot selection:
- highlight active slot,
- default to non-active slot.
6. Confirmation dialog:
- explicit warning for active slot,
- backup requirement hint.
7. Live progress view:
- stage text + percentage (where available),
- actionable error message on failure with code + short reason.
8. Success:
- offer reboot now/later,
- show flashed slot and target build.

### Historical Builds (Browse + Flash Older Images)

The portal catalog retains **all** published builds per channel/imagedir
(see [IMAGE-PORTAL-SERVICE-CONCEPT.md](IMAGE-PORTAL-SERVICE-CONCEPT.md)).
The Online Flash UI must expose this as a first-class feature, not only
"latest vs current".

Entry points from the main Update Card:

- "Flash latest" (default, highlights the latest build),
- "Browse older builds..." (opens the history list).

#### History list view

- sorted newest-first,
- default page size configurable (default: 20 entries, loaded via
  `flash-online-check --catalog --limit 20`),
- "Load more" to fetch older entries,
- per row: `build_date`, `image_version`, `describe`, size of primary
  archive, and a short badge for the channel (`release`/`beta`/`nightly`).

#### Build detail view

Selecting a row opens a detail view showing all manifest fields that
have user value:

- `build_date`, `image_version`, `image_name`,
- `describe`, `git_hash` (git identifier for traceability),
- `flash_backend` (informational — runtime still decides via local
  `/etc/tuxbox/flash-backend.conf`),
- primary archive `name`, `size`, `sha256`,
- `changelog_url` (if present — opens in the Neutrino HTTP fetcher
  and displays text inline),
- optional `rollback.safe_version_min`, `rollback.requires_wipe`.

From the detail view, the user can directly proceed to slot selection
and flash. The runtime handoff for that selected retained build is:

`/usr/bin/flash <slot> online <build_date>`

This reuses exactly the same confirmation + flash flow as the "latest"
path while keeping `build_date` as the single stable selector across
UI, helper, runtime, and later APIv4/WebIF callers.

#### Downgrade safety

Flashing an older build than the currently installed one is
**allowed** but flagged:

- if the manifest carries `rollback.safe_version_min` and the currently
  installed version is higher, the confirmation dialog adds an extra
  warning with the text from the manifest,
- if `rollback.requires_wipe` is true, the dialog forces an
  acknowledgment that user data on the target slot will be wiped,
- active-slot downgrade keeps the existing active-slot policy gate
  (backup required, extra confirmation),
- the exitcode contract is unchanged — older builds use the same
  error mapping.

### Legacy Coexistence

- When the new runtime is present, the legacy `CFlashUpdate` menu entry
  is **hidden**, not disabled. Showing two similar-looking flash flows
  in the same menu confuses users.
- Shared settings (update server URL, service key, channel) live in
  exactly one place — the new "Online Flash Settings" container. They
  must not be duplicated between legacy and new menu trees.
- On boxes where the new runtime is missing (old hardware, no profile),
  the legacy menu stays untouched and the new container is never
  instantiated.

### UX Safety Rules

- no implicit flash start,
- always confirm before write,
- active-slot flow requires an extra confirmation gate,
- error dialogs must include short cause and next action.

## Backup and Restore Scope

The Online Flash flow must let the user decide what is preserved
across a flash operation. Two layers exist on the box today and are
combined under a single "Flash Backup & Restore" settings container
in the new UI:

### Layer 1: Settings backup (Neutrino user data)

Driven by the existing `backup.sh` + `tobackup.conf` mechanism
(shipped by `meta-neutrino/recipes-neutrino/neutrino/files/tobackup.conf`).
The file lists absolute paths and directories that should be included
in a tar.gz snapshot.

Current scope (stock): `/etc/auto.*`, `/etc/exports`, `/etc/hostname`,
`/etc/network/interfaces`, `/etc/passwd`, `/etc/resolv.conf`,
`/etc/samba/smb.conf`, `/etc/wpa_supplicant.conf`, `/etc/minidlna.conf`,
`/share/tuxbox/neutrino/flex/flex_user.conf`, `/home/root/`,
`/etc/neutrino/`, `/var/tuxbox/fonts/`, `/var/tuxbox/icons/`,
`/var/tuxbox/locale/`, `/var/tuxbox/themes/`, `/var/tuxbox/webtv/`.

### Layer 2: Active-slot rootfs snapshot

Driven by `flash-backend-ofgwrite.sh:run_active_slot_backup()`, which
is already invoked before every **active-slot** flash (see
`meta-tuxbox/recipes-local/flash-script/files/flash-backend-ofgwrite.sh`).
It calls `backup.sh` against `tobackup.conf` and stores a tar.gz
under `FLASH_ACTIVE_SLOT_BACKUP_DIR`
(default `/var/volatile/flash-backup` — tmpfs, survives pivot_root
but not reboot; pick a path on external/unwiped storage if you need
post-reboot rollback).

Before writing the backup the dispatcher runs a runtime space check
(`check_backup_space`): free KB on the destination filesystem must be
at least `du -sk` of the sources listed in `tobackup.conf` plus
`FLASH_ACTIVE_SLOT_BACKUP_MIN_FREE_KB` (default 51200 = 50 MB). This
avoids silently filling tmpfs (RAM) when the default
`/var/volatile/flash-backup` is used. Override the source config via
`FLASH_ACTIVE_SLOT_BACKUP_SRC_CONF`.

Today this runs unconditionally for active-slot flashes and not at
all for inactive-slot flashes.

### New UI controls

A new "Flash Backup & Restore" container lives inside the Online Flash
Settings menu (Neutrino-side, see
[SERVICE-KEY.md](SERVICE-KEY.md#setting-placement)):

```
Online Flash Settings
  +-- ...existing key/server settings...
  +-- Flash Backup & Restore
        +-- Auto-backup before flash           [on/off, default on]
        +-- Require backup for active slot     [on/off, default on]
        +-- Backup destination                 [path, default as today]
        +-- Keep last N backups                [int, default 3]
        +-- View / edit backup scope           -> scope editor
        +-- Offer restore after flash          [on/off, default on]
```

Rules:

- **Auto-backup before flash** (new): when on, the dispatcher runs a
  settings snapshot before **any** flash, not just active-slot.
  Controlled by the new generic env var `FLASH_BACKUP_BEFORE_ANY_FLASH`.
  Independent of which slot is targeted.
- **Require backup for active slot**: maps 1:1 to the existing
  `FLASH_ACTIVE_SLOT_REQUIRE_BACKUP` env var, exposed as a UI toggle.
  This remains an **active-slot-only** safety gate, distinct from the
  generic auto-backup toggle above. Setting this to off removes a
  safety gate and must carry a clear warning in the UI.
- **Backup destination**: user-visible label; the dispatcher writes
  the backup into the **target slot's rootfs** under
  `<target_rootfs>/var/lib/neutrino-backups/` (see "Restore flow"
  below). The UI field controls only the user-visible copy path for
  optional off-slot mirroring, not the primary location.
- **Keep last N backups**: new retention policy, controlled by
  `FLASH_BACKUP_KEEP_LAST`. The dispatcher prunes older backup files
  in the same destination directory after a successful backup. Legacy
  active-slot snapshots still use `ACTIVE_SLOT_BACKUP_NAME_PREFIX` for
  prefix-based matching in backward-compatible paths.

Environment variable split:

| Variable                         | Scope                | Owner  |
|----------------------------------|----------------------|--------|
| `FLASH_BACKUP_BEFORE_ANY_FLASH`  | any flash target     | new    |
| `FLASH_BACKUP_KEEP_LAST`         | retention, any flash | new    |
| `FLASH_ACTIVE_SLOT_REQUIRE_BACKUP` | active slot only   | legacy |
| `FLASH_ACTIVE_SLOT_BACKUP_DIR`   | active slot only     | legacy |

Rationale for the split: `FLASH_ACTIVE_SLOT_*` are safety gates for
the one case where a flash overwrites the running slot. `FLASH_BACKUP_*`
are generic user-facing controls that apply to every flash, so they
must not be conflated with the active-slot safety variables.
- **View / edit backup scope**: expert view that shows the current
  `tobackup.conf` entries and allows adding/removing paths. v1 keeps
  this as a flat list. Category-based groups (System / Neutrino /
  Themes / WebTV / etc.) are a Phase 2 follow-up.
- **Offer restore after flash**: when on, after a successful reboot
  into the freshly flashed slot, Neutrino prompts once with
  "Restore settings from last pre-flash backup?" and, on confirm,
  restores the slot-local pre-flash archive referenced by the marker
  under `/var/lib/neutrino-backups/`. The optional mirror destination
  remains a secondary copy path, not the primary restore source. This
  is opt-in per prompt, never automatic, so a user can compare before
  restoring.

### Restore flow

**Marker and backup location (decision 2026-04-12):** both the
restore marker and the tar.gz backup are written **into the target
slot's rootfs**, not into the currently running slot. This piggybacks
on ofgwrite's existing write access to the target slot during
extraction — no extra mount gymnastics, no ofgwrite patch, no
double-mount of the shared userdata partition (which ext4
Multi-Mount Protection would block anyway).

Canonical paths inside the freshly extracted target rootfs:

- Marker: `<target_rootfs>/etc/neutrino/flash-restore-pending.conf`
  (JSON: `{ "backup": "/var/lib/neutrino-backups/<file>.tar.gz",
  "slot": <n>, "timestamp": "..." }`)
- Backup: `<target_rootfs>/var/lib/neutrino-backups/pre-flash-<timestamp>.tar.gz`

Injection timing is owned by the flash runtime, but it needs an
explicit internal handoff hook instead of a blind tail-call into
`ofgwrite`:

- `flash-backend-ofgwrite.sh` runs `backup.sh` against the configured
  `tobackup.conf` scope **before** the flash, into a temporary
  staging directory.
- The runtime then delegates to the internal libexec-side handoff
  helper `/usr/libexec/tuxbox/flash-ofgwrite-handoff` (see
  "Internal libexec handoff helper" below for the full spec), not
  to a public `${bindir}` CLI. That helper owns the final
  target-rootfs injection step for marker + staged tarball before the
  flash path irrevocably hands off to `ofgwrite` / reboot.
- Inactive-slot path: the helper writes into the mounted target
  rootfs under `<target_rootfs>/...` before unmounting it.
- Active-slot path: the transient systemd unit launches the same
  helper with `--active-slot` instead of raw `${OFGWRITE_BIN}`, so
  the active-slot chain has a defined place to deposit marker +
  backup for the freshly flashed slot before reboot/pivot.
- Retention (`FLASH_BACKUP_KEEP_LAST`) is applied on the target slot
  itself, inside `<target_rootfs>/var/lib/neutrino-backups/`.

No direct GUI/Lua/API caller sees this helper, and no `ofgwrite_bin`
patch is required for the Phase-1 plan.

On first boot after the flash, the freshly flashed slot is the
running slot, so the marker naturally appears at
`/etc/neutrino/flash-restore-pending.conf` without any cross-slot
coordination. Neutrino checks the marker at startup; if present and
the referenced backup file exists, it shows the restore prompt.

- Confirming runs `restore.sh <backup>` (existing Neutrino-side tool;
  provided via `pkg_postinst_ontarget` in `neutrino.inc`).
- Declining removes the pending marker; it never re-prompts.

This path does not require a shared/host-local partition and makes
no assumption about whether `/var/lib/neutrino-backups/` survives
future flashes: each flash writes its own backup into its own target
slot, so the backup is always co-located with the slot it was taken
against.

### Internal libexec handoff helper

The libexec-side handoff helper is the single choke point every
flash path goes through after `backup.sh` has produced the staged
tarball and before `ofgwrite` touches the target slot. It is **not**
part of the public runtime contract and must never appear in
`${bindir}`.

Spec:

- **Path**: `/usr/libexec/tuxbox/flash-ofgwrite-handoff`
  (supersedes the previous `${bindir}/ofgwrite_caller`; the old
  caller is reclassified as libexec and kept, if at all, only as a
  compatibility symlink inside the same libexec directory).
- **Callers** (exactly two, enforced):
  1. **Inactive-slot flow**:
     `/usr/libexec/tuxbox/flash-backend-ofgwrite.sh` calls the helper
     synchronously after the target rootfs has been populated and is
     still mounted.
  2. **Active-slot flow**: the transient systemd unit that the
     dispatcher stages for the post-pivot phase runs the helper from
     its `ExecStart=` line **instead of** a raw `${OFGWRITE_BIN}`
     exec. The dispatcher writes this unit to
     `/run/systemd/system/flash-ofgwrite-handoff.service` and starts
     it; the unit owns the `pivot_root` and the final `ofgwrite`
     invocation against `/newroot`.
- **CLI signature** (positional, stable):

  ```
  flash-ofgwrite-handoff \
      --target-slot <n> \
      --target-rootfs <path> \
      --staged-backup <tarball> \
      --marker-json <json-file> \
      [--keep-last <n>] \
      [--active-slot --image-dir <dir>]
  ```

- **Responsibilities** (in order):
  1. validate `--target-rootfs` is a live mount of the correct slot,
  2. copy the staged tarball into
     `<target_rootfs>/var/lib/neutrino-backups/pre-flash-<timestamp>.tar.gz`,
  3. write the marker JSON into
     `<target_rootfs>/etc/neutrino/flash-restore-pending.conf`,
  4. apply `FLASH_BACKUP_KEEP_LAST` retention inside
     `<target_rootfs>/var/lib/neutrino-backups/`,
  5. in `--active-slot` mode only: exec `ofgwrite` against
     `<image-dir>` so the active-slot chain ends in one helper
     instead of being split across two systemd `ExecStart=` lines.
- **Exit codes** (map onto the stable contract in "Exit Codes (Stable)"):
  - `0` success,
  - `1` generic failure,
  - `4` write failure (marker or tarball injection failed),
  - `5` integrity/verification failure (staged tarball missing or
    unreadable),
  - `6` active-slot policy re-check blocked the irreversible step,
  - `127` missing `ofgwrite` binary in the active-slot phase.
- **Logging**: appends a line per phase to
  `/var/log/tuxbox/flash-backend-ofgwrite.log` — same file the
  dispatcher writes — so a single `tail -f` covers the entire chain.
- **No public surface**: no `${bindir}` entry, no symlink into
  `/usr/bin`, no man page. UI, Lua, and APIv4 callers go through
  `/usr/bin/flash` exclusively; the dispatcher is the only code that
  knows this helper exists.

### Interaction with the "older build" path

When flashing a historical (older) build, the backup behavior is the
same. If the older manifest carries `rollback.requires_wipe`, the
restore prompt is **suppressed** because the restored settings may be
incompatible with the older image. The UI tells the user that a
backup was still created and how to restore it manually if desired.

### v1 vs Phase 2 scope

**In scope for v1:**

- auto-backup-before-any-flash toggle,
- keep-last-N retention,
- pre/post-flash marker file + restore prompt,
- flat scope editor,
- UI controls for the existing `FLASH_ACTIVE_SLOT_*` env vars.

**Deferred to Phase 2:**

- category-based scope selection (System/Neutrino/Themes/WebTV),
- selective restore (pick subsets from a backup),
- scheduled backups outside flash context,
- remote backup destinations (NFS/SMB/SSHFS).

## Migration Plan (No Breakage)

### Phase A: Additive Feed Modernization

- generate and publish `manifest.json` and `*.sha256`,
- keep legacy `imageversion` file in feed,
- keep existing update runtime behavior unchanged.

### Phase B: Runtime Helper + UI Integration

- finalize Service Key build/runtime plumbing (see
  [SERVICE-KEY.md](SERVICE-KEY.md)),
- add `flash-online-check`,
- add new Neutrino online-flash manager (runtime-gated) and hide the
  legacy `CFlashUpdate` entry when the new runtime is present,
- do not modify legacy `CFlashUpdate` implementation.

### Phase C: Plugin Alignment

- migrate Lua online flow to `flash-online-check` + `/usr/bin/flash`,
- remove plugin-local feed parsing and md5 heuristics.

### Phase D: APIv4/WebIF Alignment

Follow-up phase for APIv4/WebIF; precise endpoint specs are deferred
and out of scope for the STB-side rollout.

- align the WebIF flow to the same runtime contracts and status model,
- add OPKG job model with deterministic precheck + error mapping,
- keep endpoint semantics stable for APIv4 clients,
- WebIF daemon resolves the effective Service Key and passes it to
  `flash-online-check` via `--key` or `TUXBOX_SERVICE_KEY`; the helper
  itself stays stateless (see SERVICE-KEY.md "Runtime Transport
  Contract").

### Phase E: Hardening

- signed manifests,
- stricter rollback guards,
- richer structured progress reporting.
- define sunset date for legacy `imageversion` fallback (after schema-v2 rollout).

## Go/No-Go Criteria

1. Online metadata is populated and valid on produced images:
- `image_update_url` non-empty,
- `image_file_name` matches real deploy artifact type.

2. Machine feed contains required files:
- `manifest.json`, image zip, `.sha256`, `imageversion`.

3. End-to-end online flash on real hardware succeeds on non-active slot:
- download, verify, write, reboot, version check.

4. Active-slot policy behaves as configured:
- blocked by default, controlled override path works.

5. Legacy update path remains functional on machines without new runtime
   capabilities.

## Implementation Notes for This Repo

Prioritize these build-side changes first:

1. Ensure `TUXBOX_IMAGE_UPDATE_URL` is set by distro/machine policy (not empty).
2. Add machine-aware online image filename policy:
- multiboot targets default to `${IMAGE_NAME}_multi.zip`.
3. Add feed marker generation in deploy (`imageversion`) if missing.
4. Generate and publish `manifest.json` + SHA256 in image deploy pipeline.
5. Add `TUXBOX_SERVICE_KEY` distro default in `tuxbox.conf` and
   propagate to `/etc/image-version` + Neutrino compile-time default
   (see [SERVICE-KEY.md](SERVICE-KEY.md)).

Then implement runtime/UI changes.
