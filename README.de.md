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

## Sicher Vs Fortgeschritten

- Sicherer Standard: `make update` (oder `make sync`) checkt gepinnte Commits aus.
- Fortgeschritten (nur bewusst): `make update-upstream` oder `./cli.py sync`
  zieht Submodule auf Upstream HEAD (unpinned). Das kann deinen Tree dirty
  machen und die Reproduzierbarkeit brechen.

Wenn du den unpinned-Update versehentlich ausgeführt hast:

```bash
make update
```

## Experimentell: Toaster-Frontend

Die Toaster-Integration ist verfügbar, aber derzeit als experimentell markiert
und nicht Teil des empfohlenen Standard-Workflows.

Details stehen in der separaten Anleitung:

- [Toaster (Experimentell)](docs/de/TOASTER_EXPERIMENTAL.md)

## Doku-Wegweiser

Lies am besten in dieser Reihenfolge:

1. [Detaillierter Quickstart](docs/de/QUICKSTART.md)
2. [Layer und Submodule](docs/de/SUBMODULES.md)
3. [Glossar (Yocto/OE Begriffe)](docs/de/GLOSSARY.md)

Danach bei Bedarf tiefer einsteigen:

- [Architektur](docs/de/ARCHITECTURE.md)
- [QEMU Nutzung](docs/de/QEMU.md)
- [Hardware-Integration](docs/de/HARDWARE_INTEGRATION.md)
- [Image-Version-Vertrag](docs/de/IMAGE_VERSION_CONTRACT.md)
- [Toaster (Experimentell)](docs/de/TOASTER_EXPERIMENTAL.md)

## Englisch?

- [README.md](README.md)
- [QUICKSTART (EN)](docs/QUICKSTART.md)
- [SUBMODULES (EN)](docs/SUBMODULES.md)
- [GLOSSARY (EN)](docs/GLOSSARY.md)
- [IMAGE VERSION CONTRACT (EN)](docs/IMAGE_VERSION_CONTRACT.md)
- [TOASTER (EN, Experimental)](docs/TOASTER_EXPERIMENTAL.md)
