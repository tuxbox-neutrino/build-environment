# Tuxbox-OS Quickstart (detailliert)

English: [../QUICKSTART.md](../QUICKSTART.md)

Diese Anleitung führt dich zum ersten erfolgreichen Build mit sicheren
Standardeinstellungen.
Wenn du den kürzesten Weg willst, starte in [../../README.de.md](../../README.de.md)
und komm für Details hierher zurück.

Wichtige Begriffe in dieser Seite erklärt das
[Glossar](GLOSSARY.md) (zum Beispiel:
[Submodule](GLOSSARY.md#submodule),
[Pinning](GLOSSARY.md#pinning),
[MACHINE](GLOSSARY.md#machine),
[MACHINEBUILD](GLOSSARY.md#machinebuild)).

## 1. Host-Voraussetzungen

Unterstützte Host-Systeme:

- Debian 11/12
- Ubuntu 20.04/22.04 LTS

Mindestens benötigte Tools:

- `bash`, `git`, `python3`
- Build-Toolchain-Pakete aus dem nächsten Abschnitt

## 2. Abhängigkeiten installieren

### Debian/Ubuntu

```bash
sudo apt update
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 curl
```

Für 32-Bit-Targets auf einem 64-Bit-Host (zum Beispiel `armhf`-Maschinen wie
HD60/HD61):

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

Optionale, aber empfohlene Locale-Prüfung:

```bash
locale | grep -E 'LANG=|LC_ALL='
```

Wenn nötig:

```bash
sudo dpkg-reconfigure locales
```

## 3. Quellen klonen und vorbereiten

Frischer Clone (empfohlen):

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

Wenn du bereits ohne Submodule geklont hast:

```bash
git submodule update --init --recursive
```

Wenn du Zugriff auf private GitHub-Submodule hast und SSH statt HTTPS nutzen willst:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

Die Standard-Flash-Abläufe der STB-Plugins sichern Einstellungen über
Neutrinos `backup.sh` und `/etc/neutrino/config/tobackup.conf`. `etckeeper`
bleibt als optionales Extra-/Feed-Paket verfügbar und gehört nicht mehr zum
Standard-Image-Inhalt.

## 4. Host prüfen und sicher synchronisieren

```bash
make check
make update
```

Was `make update` macht:

- Zieht Änderungen im Top-Level-Repository ohne rekursiven Submodul-Fetch.
- Setzt Submodule auf gepinnte Commits (sicher/reproduzierbar).

## 5. Maschinenwerte wählen

Verfügbare Maschinen anzeigen:

```bash
make list-machines
```

Eine Maschine im Detail prüfen:

```bash
make machine-info MACHINE=hd51
```

Wenn deine Maschine ein spezielles `MACHINEBUILD` braucht, zeigt
`make machine-info` das an. Bei vielen Maschinen ist `MACHINEBUILD` gleich
`MACHINE`.

## 6. Erstes Image bauen

### Bewährte Starter-Beispiele

```bash
# GFutures HD51
make image MACHINE=hd51 MACHINEBUILD=mutant51

# GFutures HD60
make image MACHINE=hd60 MACHINEBUILD=mutant60

# Zgemma H7
make image MACHINE=zgemmah7 MACHINEBUILD=zgemmah7
```

Wenn du zuerst nur Konfiguration erzeugen willst:

```bash
make config MACHINE=hd51 MACHINEBUILD=mutant51
make show-config MACHINE=hd51
```

## 7. Build-Artefakte finden

Image-Artefakte liegen typischerweise hier:

- `builds/build/tmp/deploy/images/<machine>/`
- `build/build/tmp/deploy/images/<machine>/`

Beispiel:

```bash
ls -lah builds/build/tmp/deploy/images/hd51 2>/dev/null || \
ls -lah build/build/tmp/deploy/images/hd51
```

## 8. Täglicher Workflow (sicher)

```bash
# Top-Level-Repo + gepinnte Submodule aktualisieren
make update

# Image bauen
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Paket-Feeds bauen
make feeds MACHINE=hd51 MACHINEBUILD=mutant51

# Build-Artefakte löschen (Caches bleiben)
make clean
```

Optionale Sync-Variante:

```bash
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

## 9. Optional: Toaster-Webfrontend (experimentell)

Diese Integration ist aktuell experimentell.

Nutze die separate Anleitung:

- [Toaster (Experimentell)](TOASTER_EXPERIMENTAL.md)

Für bestehende Builds kannst du dein aktuelles Build-Verzeichnis in Toaster
importieren:

```bash
make toaster-import-build
```

Defaults:
- `TOASTER_IMPORT_NAME=$(DISTRO)-build`
- `TOASTER_IMPORT_PATH=$(TOASTER_BUILD_DIR)`

## 10. Aktualisieren: Nutzer Vs Entwickler

### Für Nutzer: bei `make update` bleiben

`make update` checkt immer die **gepinnten Submodul-Commits** aus — eine
getestete, stabile Kombination. Dein Build ist reproduzierbar. Das ist der
einzige Update-Befehl, den du als Nutzer brauchst.

### Für Entwickler: `make update-upstream`

```bash
make update-upstream
```

Damit werden alle Submodule auf den **neuesten Commit** ihres Tracking-Branches
gezogen (z.B. `kirkstone` für Poky/meta-openembedded, `5.1` für OE-Alliance,
`master` für meta-neutrino/meta-tuxbox). Du bleibst auf dem gleichen
Yocto-Release, bekommst aber die neuesten Upstream-Patches.

**Warnung:** Das kann deinen Build brechen, weil die neue Kombination noch
nicht getestet wurde. Nutze das nur, wenn du testen und die Pins aktualisieren
willst.

Nach einem erfolgreichen Build den neuen Stand pinnen:

```bash
git add poky oe-alliance meta-openembedded meta-neutrino meta-tuxbox
git commit -m "chore (deps): pin submodules to latest tracked branches"
```

Allgemeine Pin-Policy:
- Während der aktiven Entwicklung darf lokal auf den aktuellen
  Upstream-Tracking-Ständen der aktiven Yocto-Linie gearbeitet werden.
- Die gespeicherten Pins werden erst aktualisiert, wenn ein validierter
  gemeinsamer Stand, ein Maintenance-Fixset oder ein Release-Kandidat
  vorliegt.
- Sobald ein Kirkstone-Release geschnitten ist, bleiben diese Pins stabil und
  werden nur noch über gezielte, validierte Maintenance-Updates bewegt.

Um jederzeit zum sicheren gepinnten Stand zurückzukehren:

```bash
make update
```

### Mitarbeit

Wenn du einen Bug findest oder eine Änderung vorschlagen möchtest:

- Erstelle ein [Issue](https://github.com/tuxbox-neutrino/build-environment/issues)
  um Probleme zu melden oder Verbesserungen vorzuschlagen.
- Reiche einen [Pull Request](https://github.com/tuxbox-neutrino/build-environment/pulls)
  für Code-Änderungen ein. Bitte teste deine Änderungen vorher.
- Schiebe keine ungetesteten Submodul-Pins auf `master`.

## 11. Fehlersuche (kurz)

### "No space left on device"

```bash
df -h
make clean
```

### Fehlendes Host-Paket oder Tool

```bash
make check
```

### Submodule-Zustand wirkt falsch

```bash
make update
```

### basehash mismatch in `do_image_hdfastboot8gb`

```bash
bitbake hdf-toolbox-image -c cleanall
make image MACHINE=hdfastboot8gb MACHINEBUILD=hdfastboot8gb
```

## 12. Nächste sinnvolle Dokus

- [Layer und Submodule](SUBMODULES.md)
- [Architektur](ARCHITECTURE.md)
- [QEMU](QEMU.md)
- [Hardware-Integration](HARDWARE_INTEGRATION.md)
- [Image-Version-Vertrag](IMAGE_VERSION_CONTRACT.md)
- [Glossar](GLOSSARY.md)
- [Toaster (Experimentell)](TOASTER_EXPERIMENTAL.md)

Englische Dokus:

- [Quickstart (EN)](../QUICKSTART.md)
- [Submodules (EN)](../SUBMODULES.md)
- [Glossary (EN)](../GLOSSARY.md)
- [Toaster (EN, Experimental)](../TOASTER_EXPERIMENTAL.md)
