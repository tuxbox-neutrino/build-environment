# Layer und Submodule (Einsteigerleitfaden)

English: [../SUBMODULES.md](../SUBMODULES.md)

Dieses Projekt haelt die Build-Layer in eigenen Git-Repositories:

- `meta-neutrino`
- `meta-tuxbox`
- `oe-alliance`
- `poky`
- `meta-openembedded`

Das `build-environment` Repo orchestriert nur den Build.
Submodule erlauben es, exakte Versionen zu pinnen und die Layer sauber
voneinander zu trennen.

## Inhalt

- [1. Mit Submodulen klonen](#1-mit-submodulen-klonen)
- [2. SSH fuer private Submodule](#2-ssh-fuer-private-submodule)
- [3. Leere Layer-Ordner beheben](#3-leere-layer-ordner-beheben)
- [4. Auf gepinnte (sichere) Versionen aktualisieren](#4-auf-gepinnte-sichere-versionen-aktualisieren)
- [5. make sync vs make update (wichtig)](#5-make-sync-vs-make-update-wichtig)
- [6. Layer auf aktuelles Upstream bringen (fortgeschritten)](#6-layer-auf-aktuelles-upstream-bringen-fortgeschritten)
- [7. Branch- und Tag-Richtlinie](#7-branch--und-tag-richtlinie)
- [Verwandte Dokus](#verwandte-dokus)

## 1. Mit Submodulen klonen

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

## 2. SSH fuer private Submodule

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

Damit werden alle Submodule auf die exakten Commits gebracht, die der Builder
pinned:

```bash
make sync
# Oder, raw git (kein Top-Level Pull):
git submodule sync --recursive
git submodule update --init --recursive
```

## 5. make sync vs make update (wichtig)

- `make sync`: zieht das Top-Level Repo und checkt die gepinnten Submodule aus
  (sicher fuer Builds).
- `make update` / `./cli.py sync`: bewegt Submodule auf Upstream HEAD (wie in
  `.gitmodules` gesetzt), laesst den Tree dirty, wenn du keine neuen Pointer
  committest, und kann Layer auf Branches/REVs bringen, die nicht zum gepinnten
  Build passen.

Wenn du `make update` aus Versehen ausgefuehrt hast, nutze `make sync`, um
zurueck zum gepinnten Stand zu kommen.

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

Bei Bedarf fuer `meta-neutrino` wiederholen.

## 7. Branch- und Tag-Richtlinie

- Standard-Branch: `master` (aktuelle Yocto-Linie)
- Maintenance-Branches: `gatesgarth`, `kirkstone`, usw.
- Tags: `<codename>-<yocto_version>` (Beispiel: `kirkstone-4.0.12`)

So ist schnell erkennbar, welche Layer-Version zu einer bestimmten Yocto-Version
gehoert.

## Verwandte Dokus

- [QUICKSTART.md](QUICKSTART.md) - Erste Build-Schritte
- [ARCHITECTURE.md](ARCHITECTURE.md) - Systemueberblick
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Neue Hardware integrieren
- [README.de.md](../../README.de.md) - Projektueberblick und Kommandos
