# Tuxbox-OS Schnellstartanleitung

English: [../QUICKSTART.md](../QUICKSTART.md)

Starte mit dem Bauen von Neutrino-Images in unter 10 Minuten.

## Inhalt

- [Voraussetzungen](#voraussetzungen)
- [Schritt 1: Abhaengigkeiten installieren](#schritt-1-abhaengigkeiten-installieren)
- [Schritt 2: Repository klonen](#schritt-2-repository-klonen)
- [Schritt 3: Build-Umgebung initialisieren](#schritt-3-build-umgebung-initialisieren)
- [Schritt 4: Erstes Image bauen](#schritt-4-erstes-image-bauen)
- [Schritt 5: Image finden](#schritt-5-image-finden)
- [Schritt 6: Image flashen](#schritt-6-image-flashen)
- [Haeufige Aufgaben](#haeufige-aufgaben)
- [Fehlersuche](#fehlersuche)
- [Naechste Schritte](#naechste-schritte)
- [Hilfe](#hilfe)

## Voraussetzungen

### Hardware-Anforderungen
- **CPU**: Moderner Multi-Core-Prozessor (4+ Kerne empfohlen)
- **RAM**: 8GB minimum, 16GB+ empfohlen
- **Disk**: 100GB+ freier Platz (SSD empfohlen)
- **Netzwerk**: Breitbandverbindung fuer Downloads

### Software-Anforderungen
- **OS**: Debian 11/12, Ubuntu 20.04/22.04 LTS (oder aehnlich)
- **Python**: 3.6 oder hoeher
- **Git**: 1.8.3.1 oder hoeher

## Schritt 1: Abhaengigkeiten installieren

### Debian 11/12 oder Ubuntu 20.04/22.04

```bash
sudo apt update
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 curl
```

Fuer 32-bit Targets auf einem 64-bit Host (z.B. armhf Maschinen wie HD60/HD61)
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

### Was sind Submodule (einfach erklaert)?

Dieses Projekt haelt die Build-Layer in eigenen Git-Repositories.
Diese Repositories sind als "Submodule" verlinkt, damit wir exakte Versionen
pinnen koennen und die Layer sauber und unabhaengig bleiben.

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
. poky/oe-init-build-env build
```

Dann `build/conf/local.conf` anpassen:

```bash
MACHINE = "hd60"
MACHINEBUILD = "ax60"
```

Du kannst `MACHINEBUILD` nur weglassen, wenn eine Maschine nur eine (oder
keine) OEM-Variante hat. Wenn mehrere Varianten existieren, musst du
`MACHINEBUILD` setzen.

## Schritt 4: Erstes Image bauen

Wichtig: Der erste Build benoetigt `MACHINE` (und `MACHINEBUILD` wenn noetig).
`make image` ohne `MACHINE` funktioniert nur, wenn bereits eine Konfiguration
existiert. Wenn du bei `MACHINEBUILD` unsicher bist, nutze:

```bash
make list-machines
make machine-info MACHINE=hd51
```

### Fuer GFutures (Mut@nt/AX) HD51

```bash
# Mit Python CLI
./cli.py build --machine hd51 --machinebuild mutant51

# Oder mit Makefile (MACHINEBUILD nutzen, wenn es von MACHINE abweicht)
make image MACHINE=hd51 MACHINEBUILD=mutant51
```

### Fuer GFutures (Mut@nt/AX) HD60/HD61

```bash
make image MACHINE=hd60 MACHINEBUILD=ax60   # oder mutant60
make image MACHINE=hd61 MACHINEBUILD=ax61
```

Wenn `build/conf/local.conf` bereits existiert, kannst du auch nur:

```bash
make image
```

Es nutzt die bestehende Konfiguration (und fragt nach, falls mehrere
Build-Verzeichnisse existieren).

### Fuer Zgemma H7

```bash
make image MACHINE=zgemmah7
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
Kommando vor der Ausfuehrung aus, damit du es bei Bedarf manuell nutzen kannst.

### BitBake- und devtool-Wrapper (optional)

Du kannst BitBake-Targets ohne direktes `bitbake` ausfuehren:

```bash
make bb-ffmpeg
make bb TARGET=ffmpeg BB_TASK=clean
make bb BB_ARGS="-s"
```

Fuer devtool:

```bash
make devtool ARGS="modify freetype"
```

Diese Wrapper verwenden die aktuelle Konfiguration. Uebergib
`MACHINE`/`MACHINEBUILD`, wenn du ein bestimmtes Build-Verzeichnis willst.

### Dauerhafte lokale Overrides (empfohlen)

Bearbeite `build/conf/local.conf` nicht direkt. Verwende stattdessen die
Include-Dateien:

- `build/conf/local.conf.user.inc` (persoenliche Defaults)
- `build/conf/local.conf.<machine>.inc` (maschinenspezifische Tweaks)
- `build/conf/bblayers.conf.user.inc` (zusaetzliche Layer/Masks)

Diese Dateien werden durch `make config` automatisch erzeugt und bleiben bei
Regeneration erhalten.

Standardmaessig enthaelt `local.conf.<machine>.inc` ein maschinenspezifisches
TMPDIR:

```
TMPDIR = "${TOPDIR}/build/tmp-${MACHINE}"
```

(Coolstream nutzt standardmaessig `build-${MACHINE}/tmp`.) Nach Bedarf anpassen.

### Parallelitaet (Standard)

Wir setzen **absichtlich keine** `BB_NUMBER_THREADS` oder `PARALLEL_MAKE` in
`local.conf`. BitBake nutzt bereits per Default die CPU-Anzahl
(siehe `poky/meta/conf/bitbake.conf`).

Wenn du ueberschreiben willst, setze es in `build/conf/local.conf.user.inc`:

```conf
BB_NUMBER_THREADS = "8"
PARALLEL_MAKE = "-j 8"
```

### Sstate-Cache teilen (optional)

Wenn du regelmaessig baust, kannst du deinen sstate-Cache auf einen Server
hochladen, damit andere ihn wiederverwenden koennen. Das ist sinnvoll, wenn
alle die gleichen gepinnten Layer-Revs nutzen.

Standardmaessig zeigen die generierten Konfigs auf den oeffentlichen Mirror:
`https://sstate.tuxbox-neutrino.org/kirkstone/release`. Du kannst ihn
abschalten, indem du `SSTATE_MIRRORS = ""` in `build/conf/local.conf.user.inc`
setzt.

Hash-Equivalence ist standardmaessig deaktiviert, wenn der oeffentliche Mirror
verwendet wird. Ein lokaler Hash-Server (unix socket) nutzt einen anderen
unihash-Kontext, was Mirror-Treffer sehr selten macht. Wenn du einen
geteilten Hash-Server betreibst, kannst du ihn in
`build/conf/local.conf.user.inc` aktivieren:

```conf
BB_HASHSERVE = "auto"
BB_HASHSERVE_UPSTREAM = "hashserv.tuxbox-neutrino.org:8686"
BB_SIGNATURE_HANDLER = "OEEquivHash"
```

Wenn du Hash-Equivalence deaktivierst (default), faellt der Signature Handler
auf `OEBasicHash` zurueck.

### Download-Mirror fuer Quellen (optional)

Der oeffentliche Source-Mirror liefert vorab geladene Downloads. Er ist
getrennt vom sstate-Cache und betrifft nur `DL_DIR` Fetches.

Generierte Konfigs aktivieren den Mirror in `build/conf/local.conf.user.inc`,
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

2) Deploy-Kommando ausfuehren (standardmaessig Dry-Run zur Sicherheit):

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

Oder fuer Downloads:

```bash
make deploy-downloads DL_DEPLOY_DRYRUN=0
```

Hinweise:
- Verwende getrennte Server-Pfade fuer verschiedene Branches/Distro-Typen, um
  inkompatible Caches nicht zu vermischen.
- Nutzer koennen auf deinen Server mit `SSTATE_MIRRORS` in
  `build/conf/local.conf.user.inc` zeigen.
- Wenn du `$HOME` in dieser Datei nutzt, maskiere es als `$${HOME}` (Make
  expandiert `$`).
- `SSTATE_RSYNC_EXCLUDE` akzeptiert Patterns getrennt durch Leerzeichen oder
  Komma. Anfuehrungszeichen sind optional.

### Image-Namens-Overrides (optional)

`build/conf/local.conf.user.inc` enthaelt eine kommentierte Vorlage fuer
Image-Namen-Variablen und Beispiele. Aktiviere nur, was du brauchst.

Diese Stolperfallen vermeiden:
- Keine Leerzeichen in `IMAGE_VER_STRING` (einige OA-Skripte brechen bei Spaces).
- `vardepsexclude` beibehalten, wenn `DATE`/`DATETIME` genutzt werden, um
  Build-Churn zu vermeiden.
- Kein `:=` (sofortige Expansion) mit `DATE`/`DATETIME` verwenden, sonst
  entstehen basehash-Aenderungen; nutze `=` oder `?=`.
- Keine Slashes in `IMAGE_NAME` (muss ein Dateiname sein).
- `IMAGE_NAME_SUFFIX` nicht aendern, ausser deine Tools erwarten das.

**Buildzeit**: 2-4 Stunden beim ersten Build (Downloads ~10GB Sources)

**Folge-Builds**: 20-40 Minuten (mit Cache)

## Schritt 5: Image finden

Gebautes Image findest du hier:

```
build/tmp/deploy/images/<machine>/
```

Beispiel fuer HD51:
```
build/tmp/deploy/images/hd51/tuxbox-image-hd51-20231217120000.zip
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
4. Bestaetigen und warten bis das Flashen abgeschlossen ist
5. Receiver startet automatisch neu

## Haeufige Aufgaben

### Quellen aktualisieren

Empfohlen (safe/pinned):
```bash
make sync
# Optional: grosse Submodule ueberspringen
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

Fortgeschritten (unpinned, fuer Maintainer):
```bash
make update
# Or
./cli.py sync
```
Warnung: `make update` / `./cli.py sync` bewegt Submodule auf Upstream HEAD
(unpinned). Das kann dich auf Branches/REVs setzen, die nicht zum gepinnten
Build passen, und laesst den Tree dirty, ausser du committest neue
Submodule-Pointer. Nur verwenden, wenn du Layer-Pins absichtlich aktualisierst.
Wenn du das aus Versehen gemacht hast, nutze `make sync` fuer den gepinnten
Zustand.

### Layer aktualisieren (Submodule)

Dies checkt nur die gepinnten Commits aus, die im Builder hinterlegt sind
(ohne Top-Level Pull). Fuer ein volles Update nutze `make sync`.

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### Build aufraeumen

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

### GitHub Actions (manuell)

Workflows sind standardmaessig manuell, damit private Submodule waehrend des
Setups funktionieren. Starte Runs im Actions-Tab, nachdem Secrets oder SSH
Zugriff fuer Submodule eingerichtet sind. Fuer Automatisierung reaktiviere
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
`IMAGE_NAME` `DATETIME` enthaelt, wodurch sich die Task-Signatur zwischen
Parses aendert. Stelle sicher, dass Submodule aktuell sind; aktuelles
`meta-tuxbox` schliesst `IMAGE_NAME` aus der Task-Signatur aus.

Wenn du *jedes Mal* ein neues Zeitstempel-Image willst, erzwinge die Task:

```bash
bitbake -f -c do_image_hdfastboot8gb tuxbox-image
```

### Alles zuruecksetzen

```bash
make distclean  # Entfernt alle Builds und Caches
./cli.py init   # Re-initialisieren
```

## Naechste Schritte

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - So funktioniert es
- **[SUBMODULES.md](SUBMODULES.md)** - Layer und Pinning
- **[HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md)** - Neue Hardware integrieren
- **[COOLSTREAM.md](COOLSTREAM.md)** - Build fuer Coolstream Tank (experimental/PoC)
- **[README.de.md](../../README.de.md)** - Projektueberblick und Kommandos

## Hilfe

- **Issues**: https://github.com/tuxbox-neutrino/build-environment/issues
- **Forum**: https://forum.tuxbox-neutrino.org
- **IRC**: #tuxbox-neutrino on libera.chat

---

Viel Erfolg beim Bauen!
