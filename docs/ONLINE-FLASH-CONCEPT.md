# Online Flash Concept (Neutrino + Yocto/OE Deploy)

Date: 2026-03-10
Status: design + implementation in progress

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

Examples:

- `flash 3 online`
- `flash 3 online force`
- `flash 2 local /media/hdd/images/hd60`
- `flash 4 restore`

### Pre-Check API (new helper)

Introduce:

`/usr/bin/flash-online-check [--json]`

Responsibilities:

- load `/etc/image-version`,
- fetch/validate `manifest.json` (fallback to legacy `imageversion` marker),
- compare local vs remote version/build,
- return clear machine-readable result.

Discovery source priority:

1. `image_discovery_api_url` (if present),
2. `image_update_url` + `image_manifest_file`,
3. legacy `image_update_info_file` marker (`imageversion`).

Output:

- human mode: concise status text,
- `--json`: structured result for Neutrino UI.

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

## Neutrino UX Flow (Best UX Requirements)

### Screen Flow

1. Open "Online Flash" menu.
2. Capability check:
- if runtime requirements missing, hide/disable new online flow and show
  legacy path only.
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

### UX Safety Rules

- no implicit flash start,
- always confirm before write,
- active-slot flow requires an extra confirmation gate,
- error dialogs must include short cause and next action.

## Migration Plan (No Breakage)

### Phase A: Additive Feed Modernization

- generate and publish `manifest.json` and `*.sha256`,
- keep legacy `imageversion` file in feed,
- keep existing update runtime behavior unchanged.

### Phase B: Runtime Helper + UI Integration

- add `flash-online-check`,
- add new Neutrino online-flash manager (runtime-gated),
- do not modify legacy `CFlashUpdate` behavior.

### Phase C: Plugin Alignment

- migrate Lua online flow to `flash-online-check` + `/usr/bin/flash`,
- remove plugin-local feed parsing and md5 heuristics.

### Phase D: Hardening

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

Then implement runtime/UI changes.
