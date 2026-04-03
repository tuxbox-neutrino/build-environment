# Tuxbox-OS Builder

English: [README.md](README.md)

Du baust hier Tuxbox-Neutrino-Images mit einem Yocto/OpenEmbedded-Workflow.
Dieses Repository ist der Orchestrator um gepinnte Layer-Submodule.
Die Standard-Kommandos sind sicher und reproduzierbar.

## Starte Hier (Erster Build)

Wenn du schnell zum ersten Ergebnis willst, kopiere diesen Block:

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
make check
make update
make image MACHINE=hd51 MACHINEBUILD=mutant51
```

Das passiert dabei:

1. Du klonst das Repository inklusive Submodule.
2. Du prüfst Host-Abhängigkeiten.
3. Du synchronisierst Repository und gepinnte Submodule (`make update`, sicherer Standard).
4. Du baust dein erstes Image.

Wenn `make check` fehlende Pakete meldet, nutze den Abhängigkeits-Abschnitt in
[docs/de/QUICKSTART.md](docs/de/QUICKSTART.md).

Fastboot-/Multiboot-Maschinen wie die HD60 enthalten das STB-Lua-Plugin-Bündel
standardmäßig im Image. Dazu gehören Laufzeitwerkzeuge wie `stb-startup`,
`stb-flash`, `stb-backup` und `stb-restore`. `logoupdater` ist ebenfalls
standardmäßig enthalten, ebenso die yWeb-Helfer für OSD-Screenshots und
AutoMount (`grab`, `fbshot` und `autofs`/`automount`). Die
Standardeinstellungssicherung für Flash-Abläufe läuft über Neutrinos
`backup.sh` mit `/etc/neutrino/config/tobackup.conf`; `etckeeper` bleibt als
optionales Extra-/Feed-Paket verfügbar und wird nicht mehr standardmäßig
installiert.

## Täglicher Workflow (Sicherer Standard)

```bash
# Aktuelle Top-Level-Änderungen und gepinnte Submodule holen
make update

# Image bauen (nutzt vorhandene Konfiguration weiter)
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Optional: Build-Artefakte löschen, Caches behalten
make clean
```

Nützliche Varianten:

```bash
# Gleiches sicheres Verhalten wie make update
make sync

# Große Submodule beim Sync auslassen
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

## Maschine Auswählen

```bash
make list-machines
make machine-info MACHINE=hd51
```

Bei vielen Geräten ist `MACHINEBUILD` gleich `MACHINE`.
Mit `make machine-info` prüfst du die maschinenspezifischen Werte.

## Wo Die Build-Ausgaben Liegen

Standardpfade für Images sind:

- `builds/build/tmp/deploy/images/<machine>/`
- `build/build/tmp/deploy/images/<machine>/`

Beispiel für `hd51`:

- `builds/build/tmp/deploy/images/hd51/`

## Aktualisieren: Nutzer Vs Entwickler

### Für Nutzer: `make update` (sicherer Standard)

```bash
make update
```

Damit werden die **gepinnten Submodul-Commits** ausgecheckt, die zusammen
getestet wurden. Dein Build ist reproduzierbar und geht nicht unerwartet
kaputt. Nutze immer diesen Befehl, es sei denn du weißt was du tust.

### Für Entwickler: `make update-upstream`

```bash
make update-upstream
```

Damit werden alle Submodule auf den **neuesten Commit** ihres Tracking-Branches
gezogen (z.B. `kirkstone` für Poky/meta-openembedded, `5.1` für OE-Alliance,
`master` für meta-neutrino/meta-tuxbox). Der Code bleibt auf dem gleichen
Yocto-Release, aber du bekommst die neuesten Patches und Änderungen von
Upstream. **Das kann deinen Build brechen**, weil diese Kombination noch nicht
getestet wurde.

Nach `update-upstream` solltest du deinen Build testen. Wenn alles funktioniert,
pinne den neuen Stand für andere Nutzer:

```bash
git add poky oe-alliance meta-openembedded meta-neutrino meta-tuxbox
git commit -m "chore (deps): pin submodules to latest tracked branches"
```

Allgemeine Pin-Policy:
- Während der aktiven Entwicklung auf einer Yocto-Linie darf lokal gegen die
  aktuellen Upstream-Tracking-Branches gearbeitet werden.
- Submodul-Updates werden erst gepinnt, wenn ein validierter gemeinsamer
  Stand, ein Maintenance-Update oder ein Release veröffentlicht wird.
- Release-Stände wie ein finales Kirkstone-Build behalten explizite stabile
  Pins. Wenn später Fixes, Security-Updates oder sonstige Maintenance nötig
  sind, werden diese Pins nach Validierung gezielt aktualisiert.

**Wichtig für Entwickler:**
- Wenn du einen Bug findest oder eine Änderung vorschlagen möchtest, erstelle
  bitte ein [Issue](https://github.com/tuxbox-neutrino/build-environment/issues)
  oder reiche einen [Pull Request](https://github.com/tuxbox-neutrino/build-environment/pulls) ein.
- Schiebe keine ungetesteten Submodul-Pins auf `master`.

Wenn du `update-upstream` versehentlich ausgeführt hast, kehre zum sicheren
gepinnten Stand zurück:

```bash
make update
```

## Experimentell: Toaster-Frontend

Die Toaster-Integration ist verfügbar, aber derzeit als experimentell markiert
und nicht Teil des empfohlenen Standard-Workflows.

Details stehen in der separaten Anleitung:

- [Toaster (Experimentell)](docs/de/TOASTER_EXPERIMENTAL.md)

## Image-Portal Feed-Workflow

Portal-Feed-Staging und `catalog.json` aus dem letzten Machine-Deploy erzeugen:

```bash
make portal-catalog MACHINE=hd60 \
  PORTAL_ARTIFACT_BASE_URL=https://images.tuxbox-neutrino.org/feed
```

Den erzeugten Feed per rsync auf einen Portal-Host synchronisieren:

```bash
make portal-sync \
  PORTAL_SYNC_DEST=user@host:/srv/tuxbox/feed \
  PORTAL_SYNC_DRYRUN=0
```

## Doku-Wegweiser

Lies am besten in dieser Reihenfolge:

1. [Detaillierter Quickstart](docs/de/QUICKSTART.md)
2. [Layer und Submodule](docs/de/SUBMODULES.md)
3. [Glossar (Yocto/OE Begriffe)](docs/de/GLOSSARY.md)

Danach bei Bedarf tiefer einsteigen:

- [Architektur](docs/de/ARCHITECTURE.md)
- [Image-Portal Einsteigeranleitung](docs/de/IMAGE_PORTAL_BEGINNER_GUIDE.md)
- [QEMU Nutzung](docs/de/QEMU.md)
- [Hardware-Integration](docs/de/HARDWARE_INTEGRATION.md)
- [Image-Version-Vertrag](docs/de/IMAGE_VERSION_CONTRACT.md)
- [Toaster (Experimentell)](docs/de/TOASTER_EXPERIMENTAL.md)

## Englisch?

- [README.md](README.md)
- [QUICKSTART (EN)](docs/QUICKSTART.md)
- [SUBMODULES (EN)](docs/SUBMODULES.md)
- [GLOSSARY (EN)](docs/GLOSSARY.md)
- [IMAGE PORTAL BEGINNER GUIDE (EN)](docs/IMAGE_PORTAL_BEGINNER_GUIDE.md)
- [IMAGE VERSION CONTRACT (EN)](docs/IMAGE_VERSION_CONTRACT.md)
- [TOASTER (EN, Experimental)](docs/TOASTER_EXPERIMENTAL.md)
