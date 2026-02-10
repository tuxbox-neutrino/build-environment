# Tuxbox-OS Schnellstartanleitung

English: [../QUICKSTART.md](../QUICKSTART.md)

Starte mit dem Bauen von Neutrino-Images in unter 10 Minuten.

## Inhalt

- [Voraussetzungen](#voraussetzungen)
- [Schritt 1: Abhängigkeiten installieren](#schritt-1-abhängigkeiten-installieren)
- [Schritt 2: Repository klonen](#schritt-2-repository-klonen)
- [Schritt 3: Build-Umgebung initialisieren](#schritt-3-build-umgebung-initialisieren)
- [Schritt 4: Erstes Image bauen](#schritt-4-erstes-image-bauen)
- [Schritt 5: Image finden](#schritt-5-image-finden)
- [Schritt 6: Image flashen](#schritt-6-image-flashen)
- [Häufige Aufgaben](#häufige-aufgaben)
- [Fehlersuche](#fehlersuche)
- [Nächste Schritte](#nächste-schritte)
- [Hilfe](#hilfe)

## Voraussetzungen

### Hardware-Anforderungen
- **CPU**: Moderner Multi-Core-Prozessor (4+ Kerne empfohlen)
- **RAM**: 8GB minimum, 16GB+ empfohlen
- **Disk**: 100GB+ freier Platz (SSD empfohlen)
- **Netzwerk**: Breitbandverbindung für Downloads

### Software-Anforderungen
- **OS**: Debian 11/12, Ubuntu 20.04/22.04 LTS (oder ähnlich)
- **Python**: 3.6 oder höher
- **Git**: 1.8.3.1 oder höher

## Schritt 1: Abhängigkeiten installieren

### Debian 11/12 oder Ubuntu 20.04/22.04

```bash
sudo apt update
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 curl
```

Für 32-bit Targets auf einem 64-bit Host (z.B. armhf Maschinen wie HD60/HD61)
Multilib-Header installieren:

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

### Locale konfigurieren

```bash
sudo dpkg-reconfigure locales
# Select: en_US.UTF-8
```

### Git konfigurieren

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Schritt 2: Repository klonen

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

Falls du bereits ohne Submodule geklont hast:

```bash
git submodule update --init --recursive
```

Wenn du Zugriff auf private GitHub-Submodule hast, nutze SSH statt HTTPS:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

Wenn du wiederholt nach der Passphrase gefragt wirst, lade deinen SSH-Key einmal:

```bash
ssh-add ~/.ssh/id_rsa
```

### Was sind Submodule (einfach erklärt)?

Dieses Projekt hält die Build-Layer in eigenen Git-Repositories.
Diese Repositories sind als "Submodule" verlinkt, damit wir exakte Versionen
pinnen können und die Layer sauber und unabhängig bleiben.

## Schritt 3: Build-Umgebung initialisieren

### Option A: Python CLI (empfohlen)

```bash
./cli.py check   # Voraussetzungen pruefen
./cli.py init    # Umgebung initialisieren
```

### Option B: Makefile

```bash
make check  # Voraussetzungen pruefen
make init   # Umgebung initialisieren
```

### Option C: Manuelles OE-Init (Workspace-Stil)

Wenn du den klassischen Yocto-Workflow im Build-Verzeichnis bevorzugst:

```bash
. poky/oe-init-build-env builds
```

Dann `builds/conf/local.conf` anpassen:

```bash
MACHINE = "hd60"
MACHINEBUILD = "ax60"
```

Du kannst `MACHINEBUILD` nur weglassen, wenn eine Maschine nur eine (oder
keine) OEM-Variante hat. Wenn mehrere Varianten existieren, musst du
`MACHINEBUILD` setzen.

## Schritt 4: Erstes Image bauen

Wichtig: Der erste Build benötigt `MACHINE` (und `MACHINEBUILD` wenn nötig).
`make image` ohne `MACHINE` funktioniert nur, wenn bereits eine Konfiguration
existiert. Wenn du bei `MACHINEBUILD` unsicher bist, nutze:

```bash
make list-machines
make machine-info MACHINE=hd51
```

### Für GFutures (Mut@nt/AX) HD51

```bash
# Mit Python CLI
./cli.py build --machine hd51 --machinebuild mutant51

# Oder mit Makefile (MACHINEBUILD nutzen, wenn es von MACHINE abweicht)
make image MACHINE=hd51 MACHINEBUILD=mutant51
```

### Für GFutures (Mut@nt/AX) HD60/HD61

```bash
make image MACHINE=hd60 MACHINEBUILD=ax60   # oder mutant60
make image MACHINE=hd61 MACHINEBUILD=ax61
```

Wenn `builds/conf/local.conf` bereits existiert, kannst du auch nur:

```bash
make image
```

Es nutzt die bestehende Konfiguration (und fragt nach, falls mehrere
Build-Verzeichnisse existieren).
Standardmäßig wird `builds/` als gemeinsames Build-Verzeichnis genutzt. Falls
bereits eine alte `build/conf/local.conf` existiert, erkennt das Tooling das
automatisch und nutzt weiter `build/`.

### Für Zgemma H7

```bash
make image MACHINE=zgemmah7
```

Hinweis: Das kanonische Image-Target ist `tuxbox-image`. Die alten Targets
`neutrino-image` und `noneutrino-image` sind Aliasnamen für die Kompatibilität.

### Neutrino‑Flavour (nur tuxbox)

Der Main‑Tree unterstützt nur den `tuxbox`‑Flavour. Wenn du einen Fork
(NI/Tango) bauen willst, nutze `devtool modify` in einem lokalen Workspace und
setze `SRC_URI` auf deinen Fork (oder lege die Änderungen in einen privaten
Layer).

### Image-Metadaten und Flash-Backend

Für Flash-/Update-Metadaten in `/etc/image-version` siehe:
`docs/IMAGE_VERSION_CONTRACT.md`.

Das Flash-Backend wird über `TUXBOX_FLASH_BACKEND` gesteuert
(`script` oder `ofgwrite`).
Der `flash-script`-Quellbranch wird über `TUXBOX_FLASH_SCRIPT_GIT_BRANCH`
gesteuert (Standard: `master`).
Der Script-Backend-Modus wird über `TUXBOX_FLASH_SCRIPT_MODE` gesteuert
(Standard/aktuell gültiger Modus: `legacy`).

Runtime-Preflight aus `flash-script`:

```bash
flash-backend-preflight
flash-backend-preflight --backend ofgwrite --image-dir /pfad/zum/entpackten/image
```

Maschinenprofil-Metadaten liegen unter:
`/etc/tuxbox/flash-machine-profile.conf`.
Dieses Profil enthält `FLASH_SCRIPT_MODE` für die Script-Backend-Weiterleitung.

`/usr/bin/flash` verzweigt jetzt per Backend:
- `script` delegiert an `/usr/libexec/tuxbox/flash-backend-script.sh`
- das Script-Backend delegiert aktuell im Modus `legacy` an `/usr/bin/flash-legacy`
- `ofgwrite` delegiert an einen ofgwrite-Backend-Handler

Aktuelle `ofgwrite`-Aufrufform:

```bash
flash <slot> [<absoluter-image-pfad>|restore|force] [force]
```

### Nur Konfiguration vorbereiten

Nutze die gleichen Parameter wie bei `make image`, aber es werden nur
Konfigurationsdateien erzeugt:

```bash
make config MACHINE=hd51
make show-config MACHINE=hd51   # zeigt Werte + Quelldatei
make edit-conf MACHINE=hd51     # oeffnet die Include-Dateien
```

`make show-config` listet, woher jeder Wert kommt (local.conf vs include
files) und zeigt die Layer aus `bblayers.conf` plus die User-Include-Datei.

Wenn bereits Konfigurationen existieren, nutzt `make image` diese weiter.
Zum erneuten Generieren erzwingen:

```bash
make image MACHINE=hd51 FORCE_CONFIG=1
```

Tipp: Die CLI gibt das zugrundeliegende `oe-init-build-env` + `bitbake`
Kommando vor der Ausführung aus, damit du es bei Bedarf manuell nutzen kannst.

### BitBake- und devtool-Wrapper (optional)

Du kannst BitBake-Targets ohne direktes `bitbake` ausführen:

```bash
make bb-ffmpeg
make bb TARGET=ffmpeg BB_TASK=clean
make bb BB_ARGS="-s"
```

Für devtool:

```bash
make devtool ARGS="modify freetype"
```

Flash-Backend-Preflight-Smoke-Check (gemockter `ofgwrite -n` Aufruf):

```bash
make flash-preflight-smoke
```

Diese Wrapper verwenden die aktuelle Konfiguration. Übergib
`MACHINE`/`MACHINEBUILD`, wenn du ein bestimmtes Build-Verzeichnis willst.

### Dauerhafte lokale Overrides (empfohlen)

Bearbeite `builds/conf/local.conf` nicht direkt. Verwende stattdessen die
Include-Dateien:

- `builds/conf/local.conf.user.inc` (persönliche Defaults)
- `builds/conf/local.conf.<machine>.inc` (maschinenspezifische Tweaks)
- `builds/conf/bblayers.conf.user.inc` (zusätzliche Layer/Masks)

Diese Dateien werden durch `make config` automatisch erzeugt und bleiben bei
Regeneration erhalten.

Standardmäßigig enthält `local.conf.<machine>.inc` ein maschinenspezifisches
TMPDIR:

```
TMPDIR = "${TOPDIR}/build/tmp-${MACHINE}"
```

(Coolstream nutzt standardmäßigig `build-${MACHINE}/tmp`.) Nach Bedarf anpassen.

### Parallelität (Standard)

Wir setzen **absichtlich keine** `BB_NUMBER_THREADS` oder `PARALLEL_MAKE` in
`local.conf`. BitBake nutzt bereits per Default die CPU-Anzahl
(siehe `poky/meta/conf/bitbake.conf`).

Wenn du überschreiben willst, setze es in `builds/conf/local.conf.user.inc`:

```conf
BB_NUMBER_THREADS = "8"
PARALLEL_MAKE = "-j 8"
```

### Sstate-Cache teilen (optional)

Wenn du regelmäßigig baust, kannst du deinen sstate-Cache auf einen Server
hochladen, damit andere ihn wiederverwenden können. Das ist sinnvoll, wenn
alle die gleichen gepinnten Layer-Revs nutzen.

Standardmäßigig zeigen die generierten Konfigs auf den öffentlichen Mirror:
`https://sstate.tuxbox-neutrino.org/kirkstone/release`. Du kannst ihn
abschalten, indem du `SSTATE_MIRRORS = ""` in `builds/conf/local.conf.user.inc`
setzt.

Hash-Equivalence ist standardmäßigig deaktiviert, wenn der öffentliche Mirror
verwendet wird. Ein lokaler Hash-Server (unix socket) nutzt einen anderen
unihash-Kontext, was Mirror-Treffer sehr selten macht. Wenn du einen
geteilten Hash-Server betreibst, kannst du ihn in
`builds/conf/local.conf.user.inc` aktivieren:

```conf
BB_HASHSERVE = "auto"
BB_HASHSERVE_UPSTREAM = "hashserv.tuxbox-neutrino.org:8686"
BB_SIGNATURE_HANDLER = "OEEquivHash"
```

Wenn du Hash-Equivalence deaktivierst (default), fällt der Signature Handler
auf `OEBasicHash` zurück.

### Download-Mirror für Quellen (optional)

Der öffentliche Source-Mirror liefert vorab geladene Downloads. Er ist
getrennt vom sstate-Cache und betrifft nur `DL_DIR` Fetches.

Generierte Konfigs aktivieren den Mirror in `builds/conf/local.conf.user.inc`,
so dass Downloads auch funktionieren, wenn Upstream wackelt. Entferne die
Zeilen unten, wenn du nur Upstream nutzen willst:

```conf
INHERIT += "own-mirrors"
SOURCE_MIRROR_URL = "https://archiv.tuxbox-neutrino.org/"
# Optional: fail if the mirror misses a source (no upstream fetch)
# BB_FETCH_PREMIRRORONLY = "1"
```

Die Datei `.tuxbox/deploy.conf` ist optional. Wenn sie nicht existiert, gib die
Variablen stattdessen auf der Kommandozeile an.

1) Lokale Konfigdatei erstellen (nicht durch git getrackt):

```make
# .tuxbox/deploy.conf
SSTATE_RSYNC_DEST = user@host:/srv/sstate/kirkstone/tuxbox/release
SSTATE_RSYNC_SSH = ssh -i $${HOME}/.ssh/id_rsa
SSTATE_RSYNC_OPTS = -a --info=stats2
SSTATE_RSYNC_EXCLUDE = tmp cache *.done *.siginfo
SSTATE_DEPLOY_DRYRUN = 1
SSTATE_DEPLOY_DELETE = 0
# Optional: if your sstate cache lives elsewhere
# SSTATE_DEPLOY_SRC = /path/to/sstate-cache

# Optional: mirror downloads (DL_DIR) to a server
# DL_RSYNC_DEST = user@host:/srv/downloads/tuxbox/kirkstone
# DL_RSYNC_SSH = ssh -i $${HOME}/.ssh/id_rsa
# DL_RSYNC_OPTS = -a --info=stats2
# DL_RSYNC_EXCLUDE defaults to: tmp cache *.done *.lock *.tmp
# DL_DEPLOY_DRYRUN = 1
# DL_DEPLOY_DELETE = 0
# Optional: if your downloads live elsewhere
# DL_DEPLOY_SRC = /path/to/downloads
```

2) Deploy-Kommando ausführen (standardmäßigig Dry-Run zur Sicherheit):

```bash
make deploy-sstate
```

Um Downloads zu deployen:

```bash
make deploy-downloads
```

3) Wenn du hochladen willst, Dry-Run deaktivieren:

```bash
make deploy-sstate SSTATE_DEPLOY_DRYRUN=0
```

Oder für Downloads:

```bash
make deploy-downloads DL_DEPLOY_DRYRUN=0
```

Hinweise:
- Verwende getrennte Server-Pfade für verschiedene Branches/Distro-Typen, um
  inkompatible Caches nicht zu vermischen.
- Nutzer können auf deinen Server mit `SSTATE_MIRRORS` in
  `builds/conf/local.conf.user.inc` zeigen.
- Wenn du `$HOME` in dieser Datei nutzt, maskiere es als `$${HOME}` (Make
  expandiert `$`).
- `SSTATE_RSYNC_EXCLUDE` akzeptiert Patterns getrennt durch Leerzeichen oder
  Komma. Anführungszeichen sind optional.

### Image-Namens-Overrides (optional)

`builds/conf/local.conf.user.inc` enthält eine kommentierte Vorlage für
Image-Namen-Variablen und Beispiele. Aktiviere nur, was du brauchst.

Diese Stolperfallen vermeiden:
- Keine Leerzeichen in `IMAGE_VER_STRING` (einige OA-Skripte brechen bei Spaces).
- `vardepsexclude` beibehalten, wenn `DATE`/`DATETIME` genutzt werden, um
  Build-Churn zu vermeiden.
- Kein `:=` (sofortige Expansion) mit `DATE`/`DATETIME` verwenden, sonst
  entstehen basehash-Änderungen; nutze `=` oder `?=`.
- Keine Slashes in `IMAGE_NAME` (muss ein Dateiname sein).
- `IMAGE_NAME_SUFFIX` nicht ändern, ausser deine Tools erwarten das.

### Locale-Defaults (optional)

Standard-Images liefern nur `en-us`, um den Footprint klein zu halten. Das QEMU
Smoke-Image behält mehrere Locales zur Bequemlichkeit. Pro Build kannst du das
in `builds/conf/local.conf.user.inc` überschreiben:

```conf
IMAGE_LINGUAS = "en-us"
```

**Buildzeit**: 2-4 Stunden beim ersten Build (Downloads ~10GB Sources)

**Folge-Builds**: 20-40 Minuten (mit Cache)

## Schritt 5: Image finden

Gebautes Image findest du hier:

```
builds/build/tmp/deploy/images/<machine>/
```

Beispiel für HD51:
```
builds/build/tmp/deploy/images/hd51/tuxbox-image-hd51-20231217120000.zip
```

## Schritt 6: Image flashen

### USB-Flash-Methode (empfohlen)

1. **Image-ZIP entpacken**
2. **Inhalt** auf FAT32-formatierten USB-Stick kopieren
3. **USB-Stick** in den Receiver stecken
4. **Receiver einschalten**
5. Anweisungen am Bildschirm befolgen

### WebIF-Flash-Methode

1. WebIF aufrufen: `http://<receiver-ip>`
2. Zu **System** -> **Software Update** wechseln
3. Image-Datei hochladen
4. Bestätigen und warten bis das Flashen abgeschlossen ist
5. Receiver startet automatisch neu

## Häufige Aufgaben

### Quellen aktualisieren

Empfohlen (safe/pinned):
```bash
make sync
# Optional: grosse Submodule ueberspringen
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

Fortgeschritten (unpinned, für Maintainer):
```bash
make update
# Or
./cli.py sync
```
Warnung: `make update` / `./cli.py sync` bewegt Submodule auf Upstream HEAD
(unpinned). Das kann dich auf Branches/REVs setzen, die nicht zum gepinnten
Build passen, und lässt den Tree dirty, ausser du committest neue
Submodule-Pointer. Nur verwenden, wenn du Layer-Pins absichtlich aktualisierst.
Wenn du das aus Versehen gemacht hast, nutze `make sync` für den gepinnten
Zustand.

### Layer aktualisieren (Submodule)

Dies checkt nur die gepinnten Commits aus, die im Builder hinterlegt sind
(ohne Top-Level Pull). Für ein volles Update nutze `make sync`.

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### Build aufräumen

```bash
./cli.py clean --machine hd51
# Or
make clean
```

### Package-Feeds bauen

Image-Builds erzeugen bereits Package-Index-Dateien als Teil des Image-Builds.
Nutze den Feeds-Target, wenn du Indizes ohne Image-Build aktualisieren willst
oder als Teil einer Release-Pipeline.

```bash
./cli.py build --machine hd51 --target feeds
# Or
make feeds MACHINE=hd51
```

### WLAN-Pakete

WLAN-User-Space-Tools sind standardmäßig enthalten, damit USB-WLAN-Sticks
maschinenübergreifend genutzt werden können. Um sie für einen Build zu
deaktivieren, setze dies in `builds/conf/local.conf.user.inc`:

```conf
TUXBOX_WIFI = "0"
```

Firmware-Pakete werden ebenfalls standardmäßig eingebunden. Kernel-Module
kommen aus dem Maschinen-Kernel (und dem modules-Tarball). Fehlt ein Treiber
für einen Stick, muss er in der Kernel-Konfiguration aktiviert werden. Für ein
minimales Image oder eine eigene Auswahl setze `TUXBOX_WIFI = "0"` und füge die
Pakete gezielt hinzu.

### QEMU Smoke-Tests (qemux86-64)

Vollständige Anleitung: `docs/de/QEMU.md` (DE) / `docs/QEMU.md` (EN).

Quick-Start:

```bash
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
./scripts/qemu/run-qemu.sh slirp
./scripts/qemu/smoke-test.sh
```

Makefile-Shortcuts:

```bash
make qemu-run
make qemu-smoke
```

Beispiele:

```bash
make qemu-run QEMU_BUILD_DIR=build-qemu
SSH_PORT=2223 make qemu-smoke
```

### GitHub Actions (manuell)

Workflows sind standardmäßigig manuell, damit private Submodule während des
Setups funktionieren. Starte Runs im Actions-Tab, nachdem Secrets oder SSH
Zugriff für Submodule eingerichtet sind. Für Automatisierung reaktiviere
`push`/`schedule` in `.github/workflows/*.yml`, sobald Auth funktioniert.

### Offline-Build

Zuerst alle Quellen herunterladen:
```bash
./cli.py fetch-only --machine hd51
```

Dann offline bauen:
```bash
./cli.py build --machine hd51 --offline
```

### Entwickler-Shell

```bash
./cli.py build --machine hd51 --devshell
```

## Fehlersuche

### Build scheitert: "No space left on device"

```bash
# Freien Platz pruefen
df -h .

# Alte Builds entfernen
make clean

# Oder Downloads loeschen (werden neu geladen)
rm -rf downloads/
```

### Build scheitert: Fehlende Pakete

```bash
# Abhaengigkeiten erneut installieren
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1
```

### Submodule-Probleme

```bash
git submodule update --init --recursive --force
```

### Build scheitert: basehash mismatch in do_image_hdfastboot8gb

Das kann auf GFutures fastboot Maschinen (hd60/hd61/hd66se) auftreten, wenn
`IMAGE_NAME` `DATETIME` enthält, wodurch sich die Task-Signatur zwischen
Parses ändert. Stelle sicher, dass Submodule aktuell sind; aktuelles
`meta-tuxbox` schliesst `IMAGE_NAME` aus der Task-Signatur aus.

Wenn du *jedes Mal* ein neues Zeitstempel-Image willst, erzwinge die Task:

```bash
bitbake -f -c do_image_hdfastboot8gb tuxbox-image
```

### Alles zurücksetzen

```bash
make distclean  # Entfernt alle Builds und Caches
./cli.py init   # Re-initialisieren
```

## Nächste Schritte

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - So funktioniert es
- **[SUBMODULES.md](SUBMODULES.md)** - Layer und Pinning
- **[HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md)** - Neue Hardware integrieren
- **[COOLSTREAM.md](COOLSTREAM.md)** - Build für Coolstream Tank (experimental/PoC)
- **[README.de.md](../../README.de.md)** - Projektüberblick und Kommandos

## Hilfe

- **Issues**: https://github.com/tuxbox-neutrino/build-environment/issues
- **Forum**: https://forum.tuxbox-neutrino.org
- **IRC**: #tuxbox-neutrino on libera.chat

---

Viel Erfolg beim Bauen!
