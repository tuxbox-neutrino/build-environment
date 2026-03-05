# Coolstream (uClibc) Builds

English: [../COOLSTREAM.md](../COOLSTREAM.md)

Diese Anleitung beschreibt den aktuellen Coolstream-Buildpfad.
Das ist ein fortgeschrittener Workflow und aktuell **experimentell**.

Wenn du neu im Projekt bist, starte zuerst mit
[QUICKSTART.md](QUICKSTART.md).

## 1. Geltungsbereich

Coolstream-Images unterscheiden sich vom normalen glibc-Flow:

- Sie nutzen eine externe uClibc-Toolchain.
- Sie brauchen Coolstream-spezifische Maschinen-Definitionen.
- Sie sind für Bring-up/Tests gedacht, nicht für Einsteiger-Standardbuilds.

Bekanntes Maschinen-Mapping (NI-Boxnamen):

- `coolstream-nevis` (HD1, glibc): HD1/BSE/NEO/NEO2/NEO2 Twin/ZEE
- `coolstream-apollo` (HD2, uClibc): Tank
- `coolstream-shiner` (HD2, uClibc): Trinity V1
- `coolstream-kronos` (HD2, uClibc): Zee2 / Trinity V2
- `coolstream-kronos-v2` (HD2, uClibc): Link / Trinity Duo

## 2. Benötigte Layer und Komponenten

- `meta-coolstream` (Maschinen/BSP)
- `meta-tuxbox-toolchain` (Integration externer Toolchain)
- externes Toolchain-Tarball `toolchain-coolstream-uclibc-armv7.tar.bz2`

Zentrale Begriffe findest du im [Glossar](GLOSSARY.md).

## 3. Toolchain-Quelle

Referenzwerte:

- URL: `https://sourceforge.net/projects/n4k/files/toolchains/`
- Datei: `toolchain-coolstream-uclibc-armv7.tar.bz2`
- SHA256: `b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

Schneller Integritätscheck:

```bash
sha256sum toolchain-coolstream-uclibc-armv7.tar.bz2
```

## 4. Build konfigurieren

### 4.1 Basiskonfiguration erzeugen

```bash
make config MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 4.2 Layer- und libc/Toolchain-Werte prüfen

Trage diese Werte in deine aktiven Build-Konfigurationsdateien ein bzw. prüfe
sie:

```conf
# local.conf (oder local include)
MACHINE = "coolstream-apollo"
MACHINEBUILD = "coolstream-apollo"
TCMODE = "external-coolstream"
TCLIBC = "uclibc"
```

```conf
# bblayers.conf
BBLAYERS += "${TOPDIR}/../meta-coolstream"
```

Bei Bedarf:

```bash
make show-config MACHINE=coolstream-apollo
make edit-conf MACHINE=coolstream-apollo
```

## 5. Build-Workflow

### 5.1 Vollbuild

```bash
make update
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 5.2 Inkrementelles Arbeiten

```bash
# Image nach Recipe-/Config-Änderungen neu bauen
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo

# Bei inkonsistentem Zustand sauber neu aufsetzen
make clean
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 5.3 Optional: BitBake direkt

```bash
make bb MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo TARGET=tuxbox-image
```

## 6. Validierung

Nach dem Build Artefakte prüfen:

```bash
ls -lah builds/build/tmp/deploy/images/coolstream-apollo 2>/dev/null || \
ls -lah build/build/tmp/deploy/images/coolstream-apollo
```

Empfohlen vor Hardware-Flash:

- erzeugte Kernel-/Rootfs-Artefakte prüfen
- Flash-Skripte und Maschinenprofilwerte prüfen
- generische Paket-/Updatepfade wenn möglich zuerst auf QEMU testen

## 7. Fehlersuche

### Toolchain-Download oder Checksumme falsch

```bash
sha256sum toolchain-coolstream-uclibc-armv7.tar.bz2
```

Erwartete SHA256:

`b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

### Compiler nicht gefunden

```bash
find . -type f -name 'arm-cortex-linux-uclibcgnueabi-gcc' | head
```

Wenn kein Compiler gefunden wird, prüfe den Entpackpfad der Toolchain und die
`EXTERNAL_TOOLCHAIN_BIN`-Einstellung in der Toolchain-Integrationsklasse.

### Library-/Runtime-Kompatibilitätsprobleme

- Prüfe, ob `TCLIBC = "uclibc"` im aktuellen Build aktiv ist.
- Prüfe Paketkompatibilität gegen uClibc.
- Betroffene Rezepte sauber neu bauen.

### Kernel-/Treiber-Mismatch

- Prüfe die Ausrichtung von maschinenspezifischem Kernel-Rezept.
- Prüfe Inhalte und Branch des Coolstream-BSP-Layers.

## 8. Referenzen

- [QUICKSTART.md](QUICKSTART.md)
- [SUBMODULES.md](SUBMODULES.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [GLOSSARY.md](GLOSSARY.md)
- [README.de.md](../../README.de.md)
