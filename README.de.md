# Tuxbox-OS Builder

English: [README.md](README.md)

Produktionsreifes Build-System für Tuxbox-Neutrino basierend auf der
OE-Alliance Infrastruktur.

## Schnellstart

### 1. Voraussetzungen

```bash
# Debian/Ubuntu
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales \
  libacl1 curl
```

Für 32-bit Targets auf einem 64-bit Host (z.B. armhf Maschinen wie HD60/HD61)
zusatzlich Multilib-Header installieren:

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

Tipp: Nutze SSH statt HTTPS für GitHub Submodule (keine Login-Prompts).

Wenn Git GitHub Repos/Submodule über **HTTPS** (`https://github.com/...`)
clont, fragt es nach Credentials (meist ein **Token** statt Passwort).
Wechsel auf **SSH** (`git@github.com:...`) nutzt deinen **SSH Key** und
vermeidet wiederholte Prompts. Das ist auch besser für automatisierte
Builds/CI.

Alle GitHub HTTPS URLs auf SSH umschreiben (empfohlen):
Das sorgt dafür, dass `https://github.com/` automatisch zu `git@github.com:`
ersetzt wird:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

SSH-Agent starten:
```bash
eval "$(ssh-agent -s)"
```

Dann Key hinzufügen:
```bash
ssh-add ~/.ssh/id_rsa
```

### 2. Initialisieren oder aktualisieren

### 2.1. Klonen für erste Initialisierung
```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
make init
```

### 2.2. Update und Sync
Wenn du ohne Submodule geklont hast oder später resyncen willst (safe/pinned):
```bash
make sync
```

... oder raw git (nur gepinnte Submodule, kein Top-Level Pull):
```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### 2.3 Sync mit Upstream

Nur verwenden, wenn du bewusst Submodule auf Upstream HEAD setzen willst
(unpinned):

```bash
make update
# Oder
./cli.py sync
```

Warnung: `make update` und `./cli.py sync` bewegen Submodule auf Upstream HEAD
(unpinned). Das kann Layer auf Branches/REVs setzen, die nicht zum gepinnten
Build passen, und lässt deinen Tree dirty, bis du neue Submodule-Pointer
committest. Nur verwenden, wenn du Layer-Pins absichtlich aktualisieren willst.
Falls du das aus Versehen ausgeführt hast, nutze `make sync`, um auf den
gepinnten Stand zurückzugehen:

```bash
make sync
```

### 3. Image bauen

Erster Build: immer `MACHINE` (und `MACHINEBUILD` falls nötig) angeben oder
zuerst `make config` ausführen. `make image` ohne `MACHINE` funktioniert nur,
wenn bereits eine Konfiguration existiert.

```bash
# Erster Build (empfohlen): MACHINE (und MACHINEBUILD wenn noetig) angeben.
# Generiert die Config automatisch, falls sie noch nicht existiert.
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Wenn eine Config existiert, kannst du einfach:
make image

# Nur Config erzeugen (kein Build)
make config MACHINE=hd51
make show-config MACHINE=hd51   # zeigt Werte + Quelldatei
make edit-conf MACHINE=hd51     # oeffnet die Include-Dateien

# Wenn Configs existieren, nutzt make image sie weiter.
# Bei Bedarf Regeneration erzwingen:
make image MACHINE=hd51 FORCE_CONFIG=1

# OEM/Brand-Varianten (MACHINEBUILD nutzen wenn es von MACHINE abweicht)
make image MACHINE=hd60 MACHINEBUILD=ax60

# Gueltige MACHINEBUILD Werte finden
make list-machines
make machine-info MACHINE=hd51

# Oder mit Python CLI
./cli.py build --machine hd51
MACHINEBUILD=mutant51 ./cli.py build --machine hd51
```

Image-Target: `tuxbox-image` ist das kanonische Image-Rezept. Die alten
Targets `neutrino-image` und `noneutrino-image` sind Aliasnamen zum selben
Rezept.

`make show-config` zeigt, woher Werte kommen (local.conf vs include
files) und listet die Layer inkl. der Quelldatei.

Gebautes Image liegt in `build/tmp/deploy/images/<machine>/` (z.B. `hd51/`).

### QEMU Smoke-Tests (qemux86-64)

Aktuelles QEMU-Target: nur `qemux86-64`.
Das QEMU-Image ist ein schlanker Smoke-Test-Build (ohne Neutrino/Multimedia-Stack).

QEMU-Image bauen:

```bash
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
```

QEMU starten (headless + User-Netzwerk):

```bash
./scripts/qemu/run-qemu.sh nographic slirp
```

Smoke-Test in einem zweiten Terminal:

```bash
./scripts/qemu/smoke-test.sh
```

Hinweise:
- SSH wird auf `127.0.0.1:2222` weitergeleitet (mit `SSH_PORT=...` überschreiben).
- Wenn `2222` belegt ist, verschiebt runqemu den Port; `SSH_PORT` entsprechend setzen.
- Beim ersten SSH-Login kann eine Passwortabfrage kommen (Root ist leer, Enter).
- Mit `SHUTDOWN=0` bleibt QEMU nach dem Test laufen.
- Wenn `build/conf` bereits auf eine andere Maschine zeigt (z.B. hd60),
  entweder die Config neu erzeugen (überschreibt) oder ein separates
  Build-Verzeichnis nutzen und `BUILD_DIR=...` an `run-qemu` übergeben.

### Dauerhafte lokale Overrides (einsteigerfreundlich)

`make config` erzeugt `local.conf` und `bblayers.conf`. Für persönliche
Änderungen, die Updates überstehen sollen, nutze diese Files:

- `build/conf/local.conf.user.inc` (persönliche Defaults)
- `build/conf/local.conf.<machine>.inc` (maschinen-spezifische Tweaks)
- `build/conf/bblayers.conf.user.inc` (extra Layer / masks)

Diese Dateien werden automatisch erzeugt und nie überschrieben.

Standardmäßigig setzt `local.conf.<machine>.inc` ein per-Maschine TMPDIR:

```
TMPDIR = "${TOPDIR}/build/tmp-${MACHINE}"
```

(Coolstream nutzt standardmäßigig `build-${MACHINE}/tmp`.) Bei Bedarf anpassen.

### Image Naming Overrides (optional)

`build/conf/local.conf.user.inc` enthält eine kommentierte Vorlage für
Image-Namen-Variablen und Beispiele. Aktiviere nur, was du brauchst.

Diese Stolperfallen vermeiden:
- Keine Leerzeichen in `IMAGE_VER_STRING` (manche OA-Skripte brechen bei Spaces).
- `vardepsexclude` beibehalten, wenn `DATE`/`DATETIME` genutzt werden, um
  Rebuild-Churn zu vermeiden.
- Keine Slashes in `IMAGE_NAME` (muss ein Dateiname sein).
- `IMAGE_NAME_SUFFIX` nicht ändern, ausser deine Tools erwarten das.

### Locale-Defaults (optional)

Standard-Images liefern nur `en-us`, um den Footprint klein zu halten. Das QEMU
Smoke-Image behält mehrere Locales zur Bequemlichkeit. Pro Build kannst du das
in `build/conf/local.conf.user.inc` überschreiben:

```conf
IMAGE_LINGUAS = "en-us"
```

### Source Download Mirror (optional)

Du kannst den öffentlichen Source-Mirror nutzen, um Downloads zu beschleunigen.
Generierte Configs aktivieren das in `build/conf/local.conf.user.inc`. Entferne
folgende Zeilen, wenn du nur Upstream nutzen willst:

```conf
INHERIT += "own-mirrors"
SOURCE_MIRROR_URL = "https://archiv.tuxbox-neutrino.org/"
# Optional: fail if the mirror misses a source (no upstream fetch)
# BB_FETCH_PREMIRRORONLY = "1"
```

### Troubleshooting: hdfastboot8gb basehash mismatch

Auf GFutures fastboot Maschinen (hd60/hd61/hd66se) kann ein basehash mismatch
auftreten, wenn `IMAGE_NAME` `DATETIME` enthält. Stelle sicher, dass Submodule
aktuell sind; aktuelles `meta-tuxbox` schliesst `IMAGE_NAME` aus der
Task-Signatur aus.

Wenn du für jeden Build ein frisches Image willst, erzwinge die Task:

```bash
bitbake -f -c do_image_hdfastboot8gb tuxbox-image
```

## Dokumentation

- QUICKSTART: [DE](docs/de/QUICKSTART.md), [EN](docs/QUICKSTART.md) - Schnellstart
- SUBMODULES: [DE](docs/de/SUBMODULES.md), [EN](docs/SUBMODULES.md) - Layer und Submodule
- ARCHITECTURE: [DE](docs/de/ARCHITECTURE.md), [EN](docs/ARCHITECTURE.md) - Systemarchitektur
- HARDWARE: [DE](docs/de/HARDWARE_INTEGRATION.md), [EN](docs/HARDWARE_INTEGRATION.md) - Neue Hardware
- COOLSTREAM: [DE](docs/de/COOLSTREAM.md), [EN](docs/COOLSTREAM.md) - uClibc Builds (experimental/PoC)

## Unterstützte Plattformen

### Prioritätsplattformen (getestet)
- **GFutures (Mut@nt/AX)**: HD51, HD60, HD61
- **AirDigital**: ZgemmaH7, H7S, H7C
- **Coolstream**: Tank (uClibc Toolchain, experimentell/PoC)

### Alle OE-Alliance Plattformen (300+ Geräte)
Siehe `make list-machines` für die komplette Liste. Nicht alle Maschinen sind
getestet oder für Neutrino integriert; `libstb-hal` Support ist begrenzt.
Siehe `docs/de/HARDWARE_INTEGRATION.md` für den Bring-up-Workflow.

## Kernfunktionen

- **OE-Alliance Integration**: Unmodifizierte OE-Alliance Infrastruktur
- **Neutrino-Only**: Keine Enigma2-Abhängigkeiten
- **Yocto Kirkstone**: LTS Support bis Mai 2026
- **Hybrid Build System**: Einfach für Einsteiger, stark für Entwickler
- **Externe Toolchain**: Coolstream uClibc Support (experimentell/PoC)
- **QEMU-Tests**: Schnelle Smoke-Tests ohne Hardware

## Build-Kommandos

### Makefile (einfach)
```bash
make image MACHINE=hd51           # Image bauen
make image MACHINE=hd51 FORCE_CONFIG=1  # Config neu erzeugen
make config MACHINE=hd51          # Nur Config erzeugen
make show-config MACHINE=hd51     # Config + Checks anzeigen
make edit-conf MACHINE=hd51       # Config-Dateien bearbeiten
make feeds MACHINE=hd51           # Package-Feeds bauen (optional; Image-Builds erzeugen Indizes)
make clean                        # Build aufraeumen (sstate bleibt)
make distclean                    # Alles bereinigen
make list-machines                # Alle Maschinen anzeigen
make machine-info MACHINE=hd51    # Hardware-Details anzeigen
make help                         # Alle Kommandos anzeigen
```

### Python CLI (fortgeschritten)
```bash
./cli.py init                     # Build-Umgebung initialisieren
./cli.py build -m hd51            # Image bauen
./cli.py config -m hd51           # Nur Config erzeugen
./cli.py show-config -m hd51      # Config + Checks anzeigen
./cli.py build -m hd51 --offline  # Offline-Build
./cli.py build -m hd51 --devshell # In Entwickler-Shell wechseln
./cli.py fetch-only -m hd51       # Nur Sources herunterladen
./cli.py sync --check             # Upstream-Updates pruefen (keine Aenderungen)
./cli.py sync                     # Submodule auf Upstream HEAD aktualisieren (unpinned)
./cli.py clean -m hd51            # Build-Verzeichnis bereinigen
```

## GitHub Actions (standardmäßigig manuell)

Workflows sind vorerst manuell, damit private Submodule funktionieren.
Starte Runs im Actions-Tab, nachdem Secrets oder SSH Zugang für Submodule
konfiguriert sind. Für Automatisierung aktiviere `push`/`schedule` in
`.github/workflows/*.yml`, sobald die Submodule-Auth funktioniert.

## Projektstruktur

```
build-environment/           # Orchestrator (dieses Repo)
+-- Makefile                 # Einfaches Build-Interface
+-- cli.py                   # Erweiterte Python-CLI
+-- scripts/                 # Hilfsskripte
+-- templates/               # Konfigurations-Templates
+-- docs/                    # Dokumentation
+-- .tuxbox/                 # State-Tracking

Submodule (auto-managed):
+-- oe-alliance/             # OE-Alliance (unveraendert)
+-- meta-neutrino/           # Neutrino Recipes (Kirkstone)
+-- meta-tuxbox/             # Tuxbox Distribution Layer
+-- meta-tuxbox-toolchain/   # Externe Toolchains (Coolstream)
```

## Mitmachen

Dies ist ein Tuxbox-Neutrino Community-Projekt. Beiträge willkommen!

- Issues: https://github.com/tuxbox-neutrino/build-environment/issues
- PRs: https://github.com/tuxbox-neutrino/build-environment/pulls

## Lizenz

- Orchestrator Code: MIT License
- OE-Alliance: Various (see upstream)
- Neutrino: GPL-2.0

## Danksagung

- **Tuxbox-Neutrino Team**: GUI und Integration
- **OE-Alliance**: Build-Infrastruktur
- **Yocto Project**: OpenEmbedded core

---

Gebaut mit <3 von der Tuxbox-Community
