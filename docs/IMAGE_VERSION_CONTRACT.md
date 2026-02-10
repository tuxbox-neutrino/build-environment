# /etc/image-version Contract

This document defines the metadata contract written by
`meta-tuxbox/classes/tuxbox-version.bbclass`.

The file is generated as:

- `/etc/image-version`
- `/.version -> /etc/image-version` (compatibility link, current behavior)

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
- `TUXBOX_VERSION_GIT_PATH` (optional explicit git repo)
- `TUXBOX_VERSION_GIT_REF` (default `HEAD`)

## Notes

- Keep key names stable. Existing plugins parse names literally.
- Additions are allowed; removals or renames are breaking changes.
