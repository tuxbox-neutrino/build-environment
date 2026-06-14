# /etc/image-version Vertrag

English: [../IMAGE_VERSION_CONTRACT.md](../IMAGE_VERSION_CONTRACT.md)

Dieses Dokument beschreibt den Metadaten-Vertrag, den
`meta-tuxbox/classes/tuxbox-version.bbclass` schreibt.

Die Datei wird erzeugt als:

- `/etc/image-version`
- `/.version` Symlink-Ziel wird per Klassen-Option gesteuert:
  - Standard: `/etc/image-version`
  - Optional: `/etc/os-release`

## Zweck

- `flash-script` liest Update-/Flash-Einstellungen aus `/etc/image-version`.
- STB-Lua-Plugins (`stb-flash`, `stb-startup`, `stb-backup`, `stb-restore`,
  `stb-move`) lesen Image-Identität/-Version aus dieser Datei.
- Neutrino-Integrationspfade werden darauf ausgerichtet, diese Datei als
  primäre Quelle für Flash-/Update-Metadaten zu nutzen.

## Pflichtschlüssel

- `version`: Build-/Versionsstempel für Kompatibilitätspfade.
- `imageversion`: Image-Version für Legacy-Plugin-Logik.
- `imagedescription`: menschenlesbare Image-Beschreibung.
- `imagename`: Legacy-Image-Namensschlüssel.
- `machine`: Maschinenkennung.
- `imagedir`: Maschinen-Image-Verzeichniskennung.
- `image_update_url`: Basis-URL für Update-Feed. In builder-generierten
  lokalen Konfigurationen kommt diese URL aus `conf/local-image-server.inc`;
  Standard bei `LOCAL_IMAGE_SERVER=1` ist
  `http://<host-ip>:33334/feed/<channel>/<imagedir>`.
- `image_update_admin_webif_url`: optionale Verwaltungs-URL des
  Update-Servers. Sie ist für Betreiber und Diagnose gedacht, nicht für
  Manifest- oder Archiv-Downloads. Der Image-Build erzeugt diesen Schlüssel
  noch nicht; er wird manuell oder von lokalen Werkzeugen wie
  `make image-server-url` gesetzt. Die Build-Erzeugung ist mit dem
  WORK-135-Admin-WebIF-Review geplant.
- `image_update_info_file`: Dateiname für Update-Info (Standard `imageversion`).
- `image_manifest_file`: Dateiname des Online-Manifests (Standard `manifest.json`).
- `image_discovery_api_url`: optionaler API-Endpunkt für Discovery.
- `image_service_key`: Build-Zeit-Seed für den Portal-Service-Key. Er kann
  für die Erstbefüllung der Neutrino-Einstellung und zur manuellen Prüfung
  eines Images genutzt werden. Er ist kein Runtime-Fallback; Neutrino löst den
  effektiven Key auf und übergibt ihn per `--key` an den Helper.
  Builder-generierte lokale Konfigurationen schreiben standardmäßig keinen
  echten Key. Der Distro-Platzhalter bleibt im Image, und Neutrino behandelt
  diesen Platzhalter für lokale/private URL-Fallbacks als ungesetzt.
- `image_file_name`: Dateiname des Update-Image-Archivs.
- `channel`: Release-Kanal (`release|beta|nightly`).
- `flash_backend`: Flash-Backend-Fähigkeit (`script` oder `ofgwrite`).
- `builddate`: Kompatibilitäts-Builddatum.
- `creator`: Ersteller-/Vendor-String.

## Kanonische Metadaten-Schlüssel

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
- `image_update_admin_webif_url` (optional, noch nicht build-generiert)
- `image_update_info_file`
- `image_manifest_file`
- `image_discovery_api_url`
- `image_service_key`
- `build_date`
- `creator`
- `channel`
- `git_hash` (optional)
- `describe` (optional)

## Kompatibilitäts-Schlüssel

Diese Felder werden absichtlich für Legacy-Skripte/Plugins dupliziert:

- `builddate` (aus `build_date`)
- `imagename` (aus `IMAGE_BASENAME`/`IMAGE_NAME`)
- `imageversion` (aus `DISTRO_VERSION`)

## Klassen-Override-Variablen

Die Klasse unterstützt folgende optionale Overrides:

- `TUXBOX_IMAGEBUILD` (Standard `${DATETIME}`)
- `TUXBOX_IMAGE_DESCRIPTION` (Standard `${IMAGE_NAME}`)
- `TUXBOX_IMAGE_DIR` (Builder-Standard: URL-sicherer Image-Verzeichnis-Alias;
  raw OE-Alliance `${IMAGEDIR}` bleibt für Flash-/Image-Klassen erhalten)
- `TUXBOX_IMAGE_CHANNEL` (Standard aus `DISTRO_TYPE` abgeleitet)
- `TUXBOX_IMAGE_UPDATE_BASE_URL` (Standard `${IMAGE_LOCATION_URL}` oder
  `${DISTRO_FEED_URI}`; lokaler Builder-Standard aus
  `conf/local-image-server.inc` ist `http://<host-ip>:33334/feed`)
- `TUXBOX_IMAGE_UPDATE_URL` (Standard leer; wird bei Bedarf aus Basis/Kanal/Imagedir abgeleitet)
- `TUXBOX_IMAGE_UPDATE_INFO_FILE` (Standard `imageversion`)
- `TUXBOX_IMAGE_FILE_SUFFIX` (Standard `multi` bei `fastboot`-Maschinen, sonst `usb`)
- `TUXBOX_IMAGE_FILE_NAME` (Standard `${IMAGE_NAME}_${TUXBOX_IMAGE_FILE_SUFFIX}.zip`)
- `TUXBOX_IMAGE_MANIFEST_FILE` (Standard `manifest.json`)
- `TUXBOX_IMAGE_DISCOVERY_API_URL` (Standard leer)
- `TUXBOX_SERVICE_KEY` (Distro-Standard; per `local.conf` überschreibbar;
  wird als `image_service_key=` nach `/etc/image-version` und als
  Neutrino-Compile-Time-Default via `--with-service-key` weitergegeben;
  builder-generierte lokale Image-Server-Konfigurationen setzen ihn nur, wenn
  `TUXBOX_SERVICE_KEY` explizit an `make config` übergeben wird)
- `TUXBOX_VERSION_STAMP` (Standard `${TUXBOX_IMAGEBUILD}`)
- `TUXBOX_VERSION_LINK_OS_RELEASE` (Standard `0`)
- `TUXBOX_VERSION_LEGACY_LINK_TARGET` (Standard `/etc/image-version`)
- `TUXBOX_VERSION_GIT_PATH` (optional explizites Git-Repo)
- `TUXBOX_VERSION_GIT_REF` (Standard `HEAD`)
- `TUXBOX_FEED_WRITE_METADATA` (Standard `1`)
- `TUXBOX_FEED_WRITE_SIDECARS` (Standard `1`)

## Deploy-Metadaten-Ausgaben

Zusätzlich zu `/etc/image-version` erzeugt die Klasse während der
Image-Post-Processing-Phase Metadaten in `${DEPLOY_DIR_IMAGE}`:

- `${TUXBOX_IMAGE_UPDATE_INFO_FILE}` (Legacy-Marker, Standard `imageversion`)
- `${TUXBOX_IMAGE_MANIFEST_FILE}` (Standard `manifest.json`)
- `*.sha256`- und `*.md5`-Sidecar-Dateien für gewählte Archive
- `manifest.json.sha256`-Sidecar für Manifest-Integrität

Auswahlverhalten:

- Primär-Archiv-Reihenfolge:
  1. `${TUXBOX_IMAGE_FILE_NAME}`
  2. `${IMAGE_NAME}_multi.zip`
  3. `${IMAGE_NAME}_usb.zip`
- optional `${IMAGE_NAME}_recovery_emmc.zip` wird eingebunden, wenn vorhanden.

Manifest-Hinweise:

- jede `files[]`-Struktur enthält `name`, `size`, `sha256` und `md5`.
- `describe` enthält Git-Describe-Metadaten (falls verfügbar).
- `image_description` enthält die menschenlesbare Image-Bezeichnung.

## Flash-Backend-Modell

Globale Distro-Variablen:

- `TUXBOX_FLASH_BACKEND` (Standard `script`)
- `TUXBOX_FLASH_MACHINE_CAP_OFGWRITE` (Standard `0` auf `qemu*`, sonst `1`)
- `TUXBOX_FLASH_SCRIPT_MODE` (Standard `legacy`)
- `TUXBOX_FLASH_SCRIPT_GIT_BRANCH` (Standard `master`)

Aktuell unterstützte Werte:

- `script`
- `ofgwrite`

Runtime-Markerdateien (installiert durch `flash-script`):

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

Runtime-Preflight-Kommando (installiert durch `flash-script`):

- `flash-backend-preflight`
  - Standardmodus prüft das konfigurierte Backend aus
    `/etc/tuxbox/flash-backend.conf`.
  - Lädt Maschinenfähigkeiten aus
    `/etc/tuxbox/flash-machine-profile.conf`.
  - Bricht bei `ofgwrite` früh ab, wenn
    `FLASH_MACHINE_CAP_OFGWRITE=0`.
  - Für `ofgwrite` kann mit `--image-dir <dir>` ein expliziter No-Write-Check
    ausgeführt werden: `ofgwrite -n -q <dir>`.

Runtime-Flash-Dispatcher (installiert durch `flash-script`):

- `/usr/bin/flash`
  - verteilt nach `FLASH_BACKEND`
  - `script`-Backend delegiert an
    `/usr/libexec/tuxbox/flash-backend-script.sh`
    (liest `FLASH_SCRIPT_MODE` aus dem Maschinenprofil und unterstützt aktuell
    `legacy` -> `/usr/bin/flash-legacy`)
  - `ofgwrite`-Backend delegiert an
    `/usr/libexec/tuxbox/flash-backend-ofgwrite.sh`
  - `ofgwrite` unterstützt:
    - `flash <slot>` (Download/Check-Modus)
    - `flash <slot> force` (Download erzwingen)
    - `flash <slot> restore` (Restore-Pfad)
    - `flash <slot> /absolute/path [force]` (lokaler Pfadmodus)

Abhängigkeitsverhalten:

- `flash-script` fügt Runtime-Abhängigkeit `ofgwrite` nur hinzu, wenn
  `TUXBOX_FLASH_BACKEND = "ofgwrite"`.
- `tuxbox-image-base.inc` installiert `ofgwrite` nur im
  `ofgwrite`-Backend-Modus.

Host-seitiger Smoke-Helper:

- `make flash-preflight-smoke` validiert Preflight, Backend-Dispatch-Routing
  und ofgwrite-Backend-Aufrufmodi.

## Hinweise

- Schlüsselnamen stabil halten. Bestehende Plugins parsen Namen wörtlich.
- Ergänzungen sind erlaubt, Entfernen/Umbenennen sind Breaking Changes.
- Host-Publishing-Tools behandeln Manifest-`imagedir` als Online-/API-Slug.
  Werte mit Pfadtrennern sind für Portal-Feeds ungültig; raw
  Flash-spezifische Verzeichniswerte bleiben in
  `/etc/tuxbox/flash-machine-profile.conf`.
