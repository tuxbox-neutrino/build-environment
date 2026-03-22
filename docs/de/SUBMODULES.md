# Layer und Submodule (Einsteigerleitfaden)

English: [../SUBMODULES.md](../SUBMODULES.md)

Dieses Projekt hält die Build-Layer in eigenen Git-Repositories:

- `meta-neutrino`
- `meta-tuxbox`
- `oe-alliance`
- `poky`
- `meta-openembedded`

Das `build-environment` Repo orchestriert nur den Build.
Submodule erlauben es, exakte Versionen zu pinnen und die Layer sauber
voneinander zu trennen.
Wenn du kurze Definitionen für Begriffe wie Submodule/Pinning willst, nutze das
[Glossar](GLOSSARY.md).

## Inhalt

- [1. Mit Submodulen klonen](#1-mit-submodulen-klonen)
- [2. SSH für private Submodule](#2-ssh-für-private-submodule)
- [3. Leere Layer-Ordner beheben](#3-leere-layer-ordner-beheben)
- [4. Auf gepinnte (sichere) Versionen aktualisieren](#4-auf-gepinnte-sichere-versionen-aktualisieren)
- [5. make update vs make update-upstream (wichtig)](#5-make-update-vs-make-update-upstream-wichtig)
- [6. Layer auf aktuelles Upstream bringen (fortgeschritten)](#6-layer-auf-aktuelles-upstream-bringen-fortgeschritten)
- [7. Branch- und Tag-Richtlinie](#7-branch--und-tag-richtlinie)
- [Verwandte Dokus](#verwandte-dokus)

## 1. Mit Submodulen klonen

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

## 2. SSH für private Submodule

Wenn du Zugriff auf private GitHub-Submodule hast, nutze SSH statt HTTPS:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

Wenn du wiederholt nach der Passphrase gefragt wirst, lade deinen SSH-Key einmal:

```bash
ssh-add ~/.ssh/id_rsa
```

## 3. Leere Layer-Ordner beheben

Wenn ein Layer-Ordner nach dem Klonen leer ist:

```bash
git submodule update --init --recursive
```

## 4. Auf gepinnte (sichere) Versionen aktualisieren

Nutze das im normalen Workflow. Es aktualisiert das Top-Level Repo und setzt
alle Submodule auf die exakten gepinnten Commits des Builders:

```bash
make update
# Gleichwertig:
make sync
# Oder, raw git (kein Top-Level Pull):
git submodule sync --recursive
git submodule update --init --recursive
```

## 5. make update vs make update-upstream (wichtig)

- `make update`: sicherer Standard für den täglichen Workflow (pinned).
- `make sync`: gleiches sicheres Verhalten wie `make update` (pinned); nutze
  das für `SYNC_EXCLUDE=...`.
- `make update-upstream` / `./cli.py sync`: bewegt Submodule auf Upstream HEAD
  (wie in `.gitmodules` gesetzt), lässt den Tree dirty, wenn du keine neuen
  Pointer committest, und kann Layer auf Branches/REVs bringen, die nicht zum
  gepinnten Build passen.
- Aktuell getrackt werden `master` für `meta-neutrino`/`meta-tuxbox`,
  `kirkstone` für `poky`/`meta-openembedded` und `5.1` für `oe-alliance`.

Wenn du `make update-upstream` aus Versehen ausgeführt hast, nutze
`make update` (oder `make sync`), um zurück zum gepinnten Stand zu kommen.

## 6. Layer auf aktuelles Upstream bringen (fortgeschritten)

Nur tun, wenn du weisst, warum du neuere Layer-Commits brauchst.

```bash
cd meta-tuxbox
git checkout master
git pull
cd ..
git add meta-tuxbox
git commit -m "Update meta-tuxbox"
```

Bei Bedarf für `meta-neutrino` wiederholen.

## 7. Branch- und Tag-Richtlinie

- Standard-Branch: `master` (aktuelle Yocto-Linie)
- Maintenance-Branches: `gatesgarth`, `kirkstone`, usw.
- Tags: `<codename>-<yocto_version>` (Beispiel: `kirkstone-4.0.12`)

So ist schnell erkennbar, welche Layer-Version zu einer bestimmten Yocto-Version
gehört.

## Verwandte Dokus

- [QUICKSTART.md](QUICKSTART.md) - Erste Build-Schritte
- [GLOSSARY.md](GLOSSARY.md) - Kurze Begriffsdefinitionen
- [ARCHITECTURE.md](ARCHITECTURE.md) - Systemüberblick
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Neue Hardware integrieren
- [README.de.md](../../README.de.md) - Projektüberblick und Kommandos
