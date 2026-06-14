# /etc/image-version Contract

Deutsch: [de/IMAGE_VERSION_CONTRACT.md](de/IMAGE_VERSION_CONTRACT.md)

This document defines the metadata contract written by
`meta-tuxbox/classes/tuxbox-version.bbclass`.

The file is generated as:

- `/etc/image-version`
- `/.version` symlink target is controlled by class toggle:
  - default: `/etc/image-version`
  - optional: `/etc/os-release`

## Purpose

- `flash-script` reads update/flash settings from `/etc/image-version`.
- STB Lua plugins (`stb-flash`, `stb-startup`, `stb-backup`, `stb-restore`,
  `stb-move`) read image identity/version metadata from this file.
- Neutrino integration paths are being aligned to use this file as primary
  flash/update metadata source.
- User-visible image versioning is image-scoped: `DISTRO_VERSION` remains the
  Yocto/OE base version, while `image_version` and the legacy
  `/etc/image-version` key `imageversion` use
  `${TUXBOX_IMAGE_VERSION}` (`<base>.<meta-tuxbox commit count>`), for example
  `4.0.35.486`.

## Required keys

- `version`: build/version stamp used by compatibility code paths.
- `imageversion`: full image version string used by legacy plugin logic;
  it matches `image_version`.
- `imagedescription`: human-readable image description.
- `imagename`: legacy image name key.
- `machine`: machine identifier.
- `imagedir`: machine image directory identifier.
- `image_update_url`: update feed base URL. In builder-generated local
  configs this is derived from `conf/local-image-server.inc`, which defaults
  to `http://<host-ip>:33334/feed/<channel>/<imagedir>` when
  `LOCAL_IMAGE_SERVER=1`.
- `image_update_admin_webif_url`: optional administration UI URL for the
  update server. This is for operators and diagnostics, not for manifest or
  archive downloads. The image build does not generate this key yet; it is
  set manually or by local tooling such as `make image-server-url`.
  Build-side generation is planned with the WORK-135 admin-WebIF review.
- `image_update_info_file`: update info filename (default `imageversion`).
- `image_manifest_file`: online manifest filename (default `manifest.json`).
- `image_discovery_api_url`: optional API endpoint for discovery.
- `image_service_key`: build-time **seed** for the portal Service Key.
  Used on first boot to initialize the Neutrino setting if no user
  value is present, and as a recovery reference when inspecting an
  image manually. It is **not** a live runtime fallback — runtime
  callers never read this key from `/etc/image-version`. Neutrino
  alone resolves the effective key and passes it to the helper via
  `--key`. Builder-generated local configs do not write a real key by
  default; the distro placeholder remains in the image and Neutrino treats
  that placeholder as unset for local/private URL fallback. See
  [SERVICE-KEY.md](SERVICE-KEY.md).
- `image_file_name`: update image archive filename.
- `channel`: release channel (`release|beta|nightly`).
- `flash_backend`: flash backend capability (`script` or `ofgwrite`).
- `builddate`: compatibility build date value.
- `creator`: image creator/vendor string.

## Canonical metadata keys

- `distro`
- `distro_name`
- `distro_version`
- `distro_codename`
- `machine`
- `box_model`
- `imagedir`
- `version`
- `imagedescription`
- `image_name`
- `image_version`
- `image_base_version`
- `image_patch_version`
- `image_patch_source`
- `meta_tuxbox_git_hash` (optional)
- `meta_tuxbox_describe` (optional)
- `meta_tuxbox_dirty`
- `image_file_name`
- `flash_backend`
- `image_update_url`
- `image_update_admin_webif_url` (optional, not build-generated yet)
- `image_update_info_file`
- `image_manifest_file`
- `image_discovery_api_url`
- `image_service_key`
- `build_date` (canonical format: `YYYYMMDDHHMMSS`, shared with
  manifest `build_date` and the runtime selector
  `/usr/bin/flash <slot> online <build_date>`)
- `creator`
- `channel`
- `git_hash` (optional)
- `describe` (optional)

## Compatibility keys

These are intentionally duplicated for legacy scripts/plugins:

- `builddate` (from `build_date`)
- `imagename` (from `IMAGE_BASENAME`/`IMAGE_NAME`)
- `imageversion` (from `image_version`)

## Class override variables

The class supports these optional overrides:

- `TUXBOX_IMAGEBUILD` (default `${DATETIME}`)
- `TUXBOX_IMAGE_BASE_VERSION` (default `${DISTRO_VERSION}`)
- `TUXBOX_IMAGE_PATCH_VERSION` (default `${META_VERSION}`, the
  `git rev-list --count HEAD` value of `meta-tuxbox`)
- `TUXBOX_IMAGE_PATCH_SOURCE` (default `${METAVERSION_LAYER_BASENAME}`,
  normally `meta-tuxbox`)
- `TUXBOX_IMAGE_VERSION` (default
  `${TUXBOX_IMAGE_BASE_VERSION}.${TUXBOX_IMAGE_PATCH_VERSION}`)

  > Note: Setting `IMAGE_VERSION` directly (e.g. in `local.conf`) has no effect
  > for Tuxbox images — `tuxbox-version.bbclass` derives `IMAGE_VERSION` from
  > `TUXBOX_IMAGE_VERSION`. Override `TUXBOX_IMAGE_VERSION`, or
  > `TUXBOX_IMAGE_BASE_VERSION` / `TUXBOX_IMAGE_PATCH_VERSION`, instead.

- `TUXBOX_IMAGE_DESCRIPTION` (default `${IMAGE_NAME}`)
- `TUXBOX_IMAGE_DIR` (builder default: URL-safe image directory alias; raw
  OE-Alliance `${IMAGEDIR}` remains available to flash/image classes)
- `TUXBOX_IMAGE_CHANNEL` (default mapped from `DISTRO_TYPE`)
- `TUXBOX_IMAGE_UPDATE_BASE_URL` (default `${IMAGE_LOCATION_URL}` or `${DISTRO_FEED_URI}`;
  builder local default from `conf/local-image-server.inc` is
  `http://<host-ip>:33334/feed`)
- `TUXBOX_IMAGE_UPDATE_URL` (default empty; auto-derived from base/channel/imagedir if unset)
- `TUXBOX_IMAGE_UPDATE_INFO_FILE` (default `imageversion`)
- `TUXBOX_IMAGE_FILE_SUFFIX` (default `multi` for `fastboot` machines, else `usb`)
- `TUXBOX_IMAGE_FILE_NAME` (default `${IMAGE_NAME}_${TUXBOX_IMAGE_FILE_SUFFIX}.zip`)
- `TUXBOX_IMAGE_MANIFEST_FILE` (default `manifest.json`)
- `TUXBOX_IMAGE_DISCOVERY_API_URL` (default empty)
- `TUXBOX_SERVICE_KEY` (distro default; overridable via
  `local.conf`; propagated to `image_service_key=` in
  `/etc/image-version` and to Neutrino compile-time default via
  `--with-service-key`; builder-generated local image server configs only set
  this when `TUXBOX_SERVICE_KEY` is explicitly passed to `make config`)
- `TUXBOX_VERSION_STAMP` (default `${TUXBOX_IMAGEBUILD}`)
- `TUXBOX_VERSION_LINK_OS_RELEASE` (default `0`)
- `TUXBOX_VERSION_LEGACY_LINK_TARGET` (default `/etc/image-version`)
- `TUXBOX_VERSION_GIT_PATH` (optional explicit git repo)
- `TUXBOX_VERSION_GIT_REF` (default `HEAD`)
- `METAVERSION_GIT_PATH` (optional explicit git repo for the image patch
  version source)
- `METAVERSION_LAYER_BASENAME` (default `meta-tuxbox` in
  `tuxbox-version.bbclass`)
- `TUXBOX_FEED_WRITE_METADATA` (default `1`)
- `TUXBOX_FEED_WRITE_SIDECARS` (default `1`)

## Deploy metadata outputs

In addition to `/etc/image-version`, the class writes feed metadata artifacts
into `${DEPLOY_DIR_IMAGE}` during image post-processing:

- `${TUXBOX_IMAGE_UPDATE_INFO_FILE}` (legacy marker, default `imageversion`)
- `${TUXBOX_IMAGE_MANIFEST_FILE}` (default `manifest.json`)
- `*.sha256` and `*.md5` sidecar files for selected archives
- `manifest.json.sha256` sidecar for manifest integrity

Important distinction:

- `/etc/image-version` key `imageversion` is the full user-visible image
  version, for example `4.0.35.486`.
- The deploy archive filenames and the deploy-root marker
  `${TUXBOX_IMAGE_UPDATE_INFO_FILE}` derive from `${IMAGE_NAME}`, which now
  encodes the version **and** a timestamp, for example
  `tuxbox-image-hd60-4.0.35.486-20260614123456`. The timestamp keeps the marker
  unique per build; ofgwrite uses the marker's MD5 for per-slot comparisons, so
  the marker must stay `${IMAGE_NAME}` (build-unique) and must not be reduced to
  the bare semantic version.

Selection behavior:

- primary archive preference is:
  1. `${TUXBOX_IMAGE_FILE_NAME}`
  2. `${IMAGE_NAME}_multi.zip`
  3. `${IMAGE_NAME}_usb.zip`
- optional `${IMAGE_NAME}_recovery_emmc.zip` is included when present.

Manifest notes:

- each `files[]` entry includes `name`, `size`, `sha256`, and `md5`.
- `describe` contains git describe metadata when available.
- `image_description` contains the human-readable image label.
- `image_version` contains the full image version, for example `4.0.35.486`.
- `image_base_version` contains the Yocto/OE base version, for example
  `4.0.35`.
- `image_patch_version` contains the `meta-tuxbox` commit count.
- `meta_tuxbox_dirty` is `1` when the selected `meta-tuxbox` worktree has
  uncommitted changes. Dirty builds are warned and marked, but
  `image_version` remains numeric.

## Flash backend model

Global distro variable:

- `TUXBOX_FLASH_BACKEND` (default `script`)
- `TUXBOX_FLASH_MACHINE_CAP_OFGWRITE` (default `0` on `qemu*`, else `1`)
- `TUXBOX_FLASH_SCRIPT_MODE` (default `legacy`)
- `TUXBOX_FLASH_SCRIPT_GIT_BRANCH` (default `master`)

Currently supported values:

- `script`
- `ofgwrite`

Runtime marker file installed by `flash-script`:

- `/etc/tuxbox/flash-backend.conf`
  - `FLASH_BACKEND=<value>`
- `/etc/tuxbox/flash-machine-profile.conf`
  - `FLASH_MACHINE`
  - `FLASH_MACHINEBUILD`
  - `FLASH_MACHINE_DRIVER`
  - `FLASH_IMAGE_DIR`
  - `FLASH_MTD_KERNEL`
  - `FLASH_MTD_ROOTFS`
  - `FLASH_KERNEL_FILE`
  - `FLASH_ROOTFS_FILE`
  - `FLASH_IMAGE_FSTYPES`
  - `FLASH_MACHINE_CAP_OFGWRITE`
  - `FLASH_SCRIPT_MODE`

Runtime preflight command installed by `flash-script`:

- `flash-backend-preflight`
  - default mode checks configured backend from
    `/etc/tuxbox/flash-backend.conf`.
  - loads machine capabilities from
    `/etc/tuxbox/flash-machine-profile.conf`.
  - fails early for `ofgwrite` when
    `FLASH_MACHINE_CAP_OFGWRITE=0`.
  - for `ofgwrite`, use `--image-dir <dir>` to execute explicit no-write mode:
    `ofgwrite -n -q <dir>`.

Runtime flash dispatcher installed by `flash-script`:

- `/usr/bin/flash`
  - dispatches by `FLASH_BACKEND`
  - `script` backend delegates to `/usr/libexec/tuxbox/flash-backend-script.sh`
    (which reads `FLASH_SCRIPT_MODE` from the machine profile and currently
    supports `legacy` -> `/usr/bin/flash-legacy`)
  - `ofgwrite` backend delegates to `/usr/libexec/tuxbox/flash-backend-ofgwrite.sh`
  - `ofgwrite` supports:
    - `flash <slot>` (download/check mode)
    - `flash <slot> force` (force download)
    - `flash <slot> restore` (restore path)
    - `flash <slot> /absolute/path [force]` (local path mode)

Dependency behavior:

- `flash-script` adds runtime dependency `ofgwrite` only when
  `TUXBOX_FLASH_BACKEND = "ofgwrite"`.
- `tuxbox-image-base.inc` installs `ofgwrite` only in `ofgwrite` backend mode.

Host-side smoke helper:

- `make flash-preflight-smoke` validates preflight, backend dispatch routing,
  and ofgwrite backend invocation modes.

## Notes

- Keep key names stable. Existing plugins parse names literally.
- Additions are allowed; removals or renames are breaking changes.
- Host publishing tools must treat manifest `imagedir` as an online/API slug.
  Values containing path separators are invalid for portal feeds; keep raw
  flash-specific directory values in `/etc/tuxbox/flash-machine-profile.conf`.
