# Tuxbox-OS Architektur

English: [../ARCHITECTURE.md](../ARCHITECTURE.md)

Verständnis der Build-System-Architektur und der Designentscheidungen.

## Inhalt

- [Übersicht](#übersicht)
- [Grundkonzepte](#grundkonzepte)
- [Verzeichnisstruktur](#verzeichnisstruktur)
- [Wichtige Designentscheidungen](#wichtige-designentscheidungen)
- [Build-Optimierung](#build-optimierung)
- [Sicherheitsaspekte](#sicherheitsaspekte)
- [Erweiterbarkeit](#erweiterbarkeit)

## Übersicht

Tuxbox-OS Builder ist ein **parasitisches Integrationssystem**, das die
reife Build-Infrastruktur von OE-Alliance nutzt und gleichzeitig eine
Neutrino-fokussierte Distribution bereitstellt.

```
[Benutzeroberflaeche]
  - Makefile
  - cli.py
  - Skripte
      |
[Orchestrator-Layer]
  - Config-Generator
    - bblayers.conf (Layer-Komposition)
    - local.conf (Build-Settings)
    - State-Tracking (.tuxbox/state.json)
      |
[Build-System]
  - OE-Alliance (Submodule - unveraendert)
    - oe-alliance-core (meta-oe + meta-brands)
    - Yocto Kirkstone (Whinlasser)
    - 300+ Hardware-Definitionen
    - DVB-Driver, Kernel, Bootloader
  - meta-neutrino (Submodule - Kirkstone Branch)
    - neutrino-mp recipes
    - libstb-hal
    - Plugins (Standard + Lua)
    - Themes
  - meta-tuxbox (Submodule - Tuxbox layer)
    - conf/distro/tuxbox.conf
    - recipes-distros/tuxbox/
      - image/tuxbox-image.bb
      - packagegroup/packagegroup-tuxbox-*.bb
      - bootlogo/
    - bbappends fuer OE-Alliance Integration
  - meta-tuxbox-toolchain (Optional)
    - Externe Toolchain-Unterstuetzung (Coolstream)
    - conf/distro/tuxbox-uclibc.conf
    - recipes-core/external-toolchain/
      |
[Build-Artefakte]
  - Images: builds/tmp/deploy/images/<machine>/
  - Packages: builds/tmp/deploy/ipk/
  - SDK: builds/tmp/deploy/sdk/
```

## Grundkonzepte

### 1. Parasitische Integration

**Philosophie**: Das Rad nicht neu erfinden. OE-Alliance unverändert nutzen.

**Vorteile**:
- OK: Geringe Wartung für Hardware-Definitionen (Neutrino-Integration bleibt nötig)
- OK: Automatische Upstream-Updates
- OK: Bewährte, produktionsreife Infrastruktur
- OK: 300+ Maschinen-Definitionen verfügbar (Neutrino-Integration je Boxmodel)

**Umsetzung**:
- OE-Alliance als **unverändertes Git-Submodule** (pinned SHA)
- Wir legen nur unsere Distribution oben drauf
- bbappends entfernen Enigma2-Dependencies aus gemeinsamen Recipes

### 2. Layer-Hierarchie

Layer werden mit Prioritätsreihenfolge gestapelt (höher = wichtiger):

```
Priority 15: meta-local          (User-Anpassungen)
Priority 10: meta-tuxbox         (Tuxbox Distribution)
Priority  9: meta-tuxbox-toolchain (Externe Toolchains)
Priority  7: meta-brands         (Hardware-Support aus OE-A)
Priority  7: meta-oe             (OE-Alliance Basis)
Priority  7: meta-neutrino       (Neutrino Recipes)
Priority  6: meta-openembedded   (Erweiterte Recipes)
Priority  5: meta                (Yocto Core - niedrigste Prioritaet)
```

Höhere Priorität kann Recipes aus niedrigeren Layern **überschreiben**.

### 3. Distributionsmodell

**Tuxbox** ist eine **Distribution** (wie OpenATV, OpenVix für E2).

**Distribution definiert**:
- conf/distro/tuxbox.conf - Kern-Settings
- Preferred Provider (Neutrino statt Enigma2)
- DISTRO_FEATURES (systemd, keine E2-spezifischen Features)
- Optimierungsflags
- Image-Namen und Versionierung

**Maschinen sind getrennt** von der Distribution:
- Die gleiche Tuxbox-Distribution kann für jede OE-Alliance Maschine bauen
- `MACHINE=hd51 DISTRO=tuxbox` -> Tuxbox auf HD51
- `MACHINE=hd60 DISTRO=tuxbox` -> Tuxbox auf HD60

### 4. Hardware-Abdeckung und Neutrino-Integration

OE-Alliance bietet 300+ Maschinen-Definitionen, aber nicht alle sind getestet
oder für Neutrino integriert. Neutrino benötigt `libstb-hal` Support, und die
Library listet nur einen Teil der `boxmodel` Werte. Für Maschinen ausserhalb
dieser Liste musst du `libstb-hal` und das Hardware-Backend erweitern.

Für einen genauen Bring-up-Workflow siehe:
`docs/de/HARDWARE_INTEGRATION.md`.

### 5. Image-Zusammensetzung

Images werden aus **Packagegroups** gebaut:

```
tuxbox-image.bb
  +- requires: packagegroup-tuxbox-base
       +- systemd
       +- busybox
       +- e2fsprogs
       +- ... (system essentials)

  +- requires: packagegroup-tuxbox-neutrino
       +- neutrino-mp
       +- libstb-hal
       +- neutrino-plugins
       +- neutrino-webif
       +- ... (Neutrino stack)

  +- conditionally:
       +- packagegroup-tuxbox-wifi (if MACHINE_FEATURES += "wifi")
       +- packagegroup-tuxbox-dvb-c (if dvb-c support)
       +- ... (hardware-dependent)
```

### 6. Konfigurations-Generierung

Build-Konfigurationen werden **dynamisch generiert**:

**bblayers.conf** (Layer-Zusammensetzung):
```
BBLAYERS = " \
    ${TOPDIR}/oe-alliance/openembedded-core/meta \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-oe \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-python \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-networking \
    ${TOPDIR}/oe-alliance/meta-oe \
    ${TOPDIR}/oe-alliance/meta-brands/meta-gfutures \  # For HD51/60/61
    ${TOPDIR}/meta-neutrino \
    ${TOPDIR}/meta-tuxbox \
    ${TOPDIR}/meta-local \
"
```

**local.conf** (Build-Einstellungen):
```
MACHINE = "hd51"
DISTRO = "tuxbox"
DL_DIR = "${TOPDIR}/downloads"
SSTATE_DIR = "${TOPDIR}/sstate-cache"
# Parallelism defaults: leave unset to use BitBake auto CPU count
# BB_NUMBER_THREADS ?= "${@oe.utils.cpu_count()}"
# PARALLEL_MAKE ?= "-j ${@oe.utils.cpu_count()}"
# Optional: switch Lua provider if needed
# PREFERRED_PROVIDER_virtual/lua = "lua"
```

Konfigurationen sind **hash-getrackt** - regeneriert nur, wenn Variablen
sich ändern.

### 7. Build-Flow

```
1. Nutzer startet: make image MACHINE=hd51
              -> cli.py build --machine hd51

2. Voraussetzungen pruefen
   +- Pruefe installierte Tools
   +- Freien Speicher pruefen (100GB+)
   +- Python-Version pruefen

3. Submodule initialisieren
   +- git submodule init
   +- git submodule update --recursive

4. Konfiguration erzeugen
   +- Maschinen-Brand erkennen -> passenden meta-brand Layer laden
   +- bblayers.conf erzeugen (Layer-Komposition)
   +- local.conf erzeugen (Build-Variablen)
   +- Config hashen -> ueberspringen wenn unveraendert

5. BitBake starten
   +- source oe-init-build-env
   +- bitbake tuxbox-image

6. BitBake Verarbeitung
   +- Recipes aus allen Layern parsen
   +- Abhaengigkeiten aufloesen
   +- Sources herunterladen (nach downloads/)
   +- Packages kompilieren
   +- Build-Status cachen (nach sstate-cache/)
   +- Image zusammenbauen

7. Artefakte bereitstellen
   +- builds/tmp/deploy/images/hd51/
       +- tuxbox-image-hd51.zip
       +- bzImage (Kernel)
       +- rootfs.tar.bz2
```

## Verzeichnisstruktur

```
build-environment/               # Orchestrator-Repository
+-- Makefile                     # Einfaches Build-Interface
+-- cli.py                       # Erweiterte Python-CLI
+-- scripts/                     # Hilfsskripte
|   +-- check-prerequisites.sh
|   +-- init.sh
|   +-- machine-info.sh
|   +-- migration/               # Kirkstone-Migrations-Tools
|   +-- qemu/                    # QEMU-Testskripte
+-- templates/                   # Konfigurations-Templates
|   +-- bblayers.conf.template
|   +-- local.conf.template
+-- .tuxbox/                     # State-Tracking
|   +-- state.json               # Build-Status
+-- builds/                       # Build-Output (generiert)
|   +-- conf/                    # Generierte Configs
|   +-- tmp/                     # Build-Artefakte
+-- downloads/                   # Source-Downloads (geteilt)
+-- sstate-cache/                # Shared State Cache (geteilt)
+-- docs/                        # Dokumentation
+-- .github/workflows/           # CI/CD

Submodule (Git-Submodule):
+-- oe-alliance/                 # OE-Alliance (unveraendert)
|   +-- meta-oe/                 # Basis-Recipes
|   +-- meta-brands/             # Hardware-Support
|   |   +-- meta-gfutures/
|   |   +-- meta-airdigital/
|   |   +-- ... (30+ brands)
|   +-- openembedded-core/       # Yocto Core
+-- meta-neutrino/               # Neutrino Recipes (Kirkstone Branch)
|   +-- recipes-neutrino/
|   |   +-- neutrino/
|   |   +-- libstb-hal/
|   |   +-- neutrino-plugins/
|   +-- conf/
+-- meta-tuxbox/                 # Tuxbox Distribution Layer
|   +-- conf/
|   |   +-- distro/tuxbox.conf
|   |   +-- layer.conf
|   +-- recipes-distros/tuxbox/
|   |   +-- image/
|   |   +-- packagegroup/
|   |   +-- bootlogo/
|   +-- recipes-bsp/             # bbappends fuer Treiber
+-- meta-tuxbox-toolchain/       # Externe Toolchains (Coolstream)
    +-- conf/distro/tuxbox-uclibc.conf
    +-- recipes-core/external-toolchain/
```

## Wichtige Designentscheidungen

### Warum Submodule?

**Pros**:
- OK: Upstream-Änderungen explizit getrackt (pinned SHA)
- OK: Einfaches Update: `git submodule update --remote`
- OK: Klare Trennung zwischen unserem Code und Upstream
- OK: Keine Merge-Konflikte mit Upstream

**Cons**:
- Contra: Nutzer müssen beim Klonen `--recursive` beachten
- Contra: Submodule-Updates brauchen einen expliziten Commit

**Mitigation**: Unsere Init-Skripte handhaben Submodule automatisch.

### Warum Python CLI + Makefile?

**Makefile**: Einfaches Interface für Einsteiger
- `make image MACHINE=hd51` - funktioniert direkt

**Python CLI**: Power für Entwickler
- State-Tracking (JSON)
- Bessere Fehlerbehandlung
- Erweiterte Features (offline, devshell, sync)
- Erweiterbar

**Best of both worlds**: Makefile delegiert an die CLI, wenn vorhanden.

### Warum Kirkstone (nicht neuestes Yocto)?

**Kirkstone (4.0)**:
- OK: LTS Release (Support bis Mai 2026)
- OK: Stabil, gut getestet
- OK: Gute Balance aus modern + bewährt

**Nicht Scarthgap (5.0)**:
- Contra: OE-Alliance nicht überall auf Whinlasser
- Contra: Neuer = mehr Churn, weniger stabil
- Contra: Migrationsaufwand für meta-neutrino

**Strategie**: Jetzt Kirkstone, Upgrade auf nächstes LTS wenn OE-A ready ist.

### Warum separate Toolchain-Layer?

**Coolstream Tank braucht uClibc** (nicht glibc):
- Unterschiedliche ABI, unterschiedliche Toolchain
- glibc und uClibc nicht in einem Layer mischen
- Saubere Trennung über `meta-tuxbox-toolchain`

**Status**: Coolstream-Support ist experimentell/PoC und nicht produktiv.

**Vorteile**:
- OK: Verschmutzt den Main-Layer nicht
- OK: Optional (nur für Tank-Builds geladen)
- OK: Einfach weitere externe Toolchains hinzufügen

## Build-Optimierung

### Shared State Cache (sstate)

**Was**: Vorab gebaute Package-Cache
**Wo**: `sstate-cache/`
**Nutzen**: Rebuilds 10-20x schneller

**Erster Build**: 2-4 Stunden (alles aus Source)
**Inkrementeller Build**: 20-40 Minuten (90% aus Cache)

**Zwischen Maschinen teilen**:
```bash
# Same sstate for all builds
SSTATE_DIR = "/opt/tuxbox-os/sstate-cache"
```

### Download-Cache

**Was**: Source-Tarballs Cache
**Wo**: `downloads/`
**Nutzen**: Keine Re-Downloads bei Rebuilds

**Größe**: ~10GB nach vollem Build

**Zwischen Maschinen teilen**:
```bash
DL_DIR = "/opt/tuxbox-os/downloads"
```

### Parallele Builds

**Default**: BitBake setzt Parallelität automatisch auf CPU-Anzahl, wenn
Variablen nicht gesetzt sind (siehe `poky/meta/conf/bitbake.conf`).

**Optionales Override** (in `local.conf.user.inc`):
```
BB_NUMBER_THREADS = "8"  # 8 Recipes parallel
PARALLEL_MAKE = "-j 8"   # 8 gcc Jobs parallel
```

**Empfehlung**: `nproc - 1` nutzen, wenn du einen Core freihalten willst.

## Sicherheitsaspekte

### Submodule pinning

**Submodule immer auf konkrete SHAs pinnen**:
```bash
cd oe-alliance
git checkout <specific-sha>
cd ..
git add oe-alliance
git commit -m "Pin OE-Alliance to <sha>"
```

**Warum**: Verhindert, dass Upstream-Änderungen Builds brechen.

### Source-Verification

**BitBake verifiziert Quellen**:
- SRC_URI mit Checksums (MD5, SHA256)
- Signatur-Prüfung für kritische Pakete

**Beispiel**:
```
SRC_URI[sha256sum] = "abc123..."
```

Wenn Checksums nicht passen -> Build fällt (schutz gegen MITM).

## Erweiterbarkeit

### Neue Maschine hinzufügen

1. Sicherstellen, dass der meta-brand Layer in bblayers.conf enthalten ist
2. MACHINE Variable setzen
3. Build

**Beispiel für Vu+ Ultimo 4K**:
```bash
# Add meta-vuplus to bblayers.conf (if not already)
make image MACHINE=ultimo4k
```

### Neue Distribution hinzufügen

1. `conf/distro/mydistro.conf` in meta-tuxbox anlegen
2. DISTRO Features definieren
3. Mit `DISTRO=mydistro` bauen

### Custom Packages

1. Recipe in `meta-tuxbox/recipes-custom/` anlegen
2. Über Packagegroup ins Image aufnehmen
3. Rebuild

---

**Für mehr Details siehe:**
- [QUICKSTART.md](QUICKSTART.md) - Erste Build-Schritte
- [SUBMODULES.md](SUBMODULES.md) - Layer und Pinning
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Neue Hardware integrieren
- [COOLSTREAM.md](COOLSTREAM.md) - Externe Toolchain-Details
- [README.de.md](../../README.de.md) - Projektüberblick und Kommandos
