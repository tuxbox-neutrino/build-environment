# /etc/image-version Contract

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

## Required keys

- `version`: build/version stamp used by compatibility code paths.
- `imageversion`: image version string used by legacy plugin logic.
- `imagedescription`: human-readable image description.
- `imagename`: legacy image name key.
- `machine`: machine identifier.
- `imagedir`: machine image directory identifier.
- `image_update_url`: update feed base URL.
- `image_update_info_file`: update info filename (default `imageversion`).
- `image_file_name`: update image archive filename.
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
- `image_file_name`
- `flash_backend`
- `image_update_url`
- `image_update_info_file`
- `build_date`
- `creator`
- `git_hash` (optional)
- `describe` (optional)

## Compatibility keys

These are intentionally duplicated for legacy scripts/plugins:

- `builddate` (from `build_date`)
- `imagename` (from `IMAGE_BASENAME`/`IMAGE_NAME`)
- `imageversion` (from `DISTRO_VERSION`)

## Class override variables

The class supports these optional overrides:

- `TUXBOX_IMAGEBUILD` (default `${DATETIME}`)
- `TUXBOX_IMAGE_DESCRIPTION` (default `${IMAGE_NAME}`)
- `TUXBOX_IMAGE_DIR` (default `${IMAGEDIR}` or `${MACHINE}`)
- `TUXBOX_IMAGE_UPDATE_URL` (default `${IMAGE_LOCATION_URL}`)
- `TUXBOX_IMAGE_UPDATE_INFO_FILE` (default `imageversion`)
- `TUXBOX_IMAGE_FILE_NAME` (default `${IMAGE_NAME}_usb.zip`)
- `TUXBOX_VERSION_STAMP` (default `${TUXBOX_IMAGEBUILD}`)
- `TUXBOX_VERSION_LINK_OS_RELEASE` (default `0`)
- `TUXBOX_VERSION_LEGACY_LINK_TARGET` (default `/etc/image-version`)
- `TUXBOX_VERSION_GIT_PATH` (optional explicit git repo)
- `TUXBOX_VERSION_GIT_REF` (default `HEAD`)

## Flash backend model

Global distro variable:

- `TUXBOX_FLASH_BACKEND` (default `script`)
- `TUXBOX_FLASH_MACHINE_CAP_OFGWRITE` (default `0` on `qemu*`, else `1`)

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
  - `script` backend delegates to `/usr/bin/flash-legacy`
  - `ofgwrite` backend delegates to `/usr/libexec/tuxbox/flash-backend-ofgwrite.sh`

Dependency behavior:

- `flash-script` adds runtime dependency `ofgwrite` only when
  `TUXBOX_FLASH_BACKEND = "ofgwrite"`.
- `tuxbox-image-base.inc` installs `ofgwrite` only in `ofgwrite` backend mode.

Host-side smoke helper:

- `make flash-preflight-smoke` validates that the preflight path invokes
  `ofgwrite` in no-write mode.

## Notes

- Keep key names stable. Existing plugins parse names literally.
- Additions are allowed; removals or renames are breaking changes.
