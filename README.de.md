# Tuxbox-OS Builder

English: [README.md](README.md)

Du baust hier Tuxbox-Neutrino-Images mit einem Yocto/OpenEmbedded-Workflow.
Dieses Repository ist der Orchestrator um gepinnte Layer-Submodule.
Die Standard-Kommandos sind sicher und reproduzierbar.

## Ich will …

| … | → |
|---|---|
| zum ersten Mal ein Image bauen | [Starte hier](#starte-hier-erster-build) (4 Befehle) |
| täglich bauen und aktualisieren | [Täglicher Workflow](#täglicher-workflow-sicherer-standard) |
| wissen, welche Box ich bauen kann | [Maschine auswählen](#maschine-auswählen) |
| mein fertiges Image finden | [Wo die Build-Ausgaben liegen](#wo-die-build-ausgaben-liegen) |
| meine Box mit Paketen versorgen | [Lokaler IPK-Feed](#lokaler-ipk-feed) |
| Online Flash lokal testen | [Lokaler Image-Server](#lokaler-image-server-für-online-flash) |
| tiefer einsteigen | [Doku-Wegweiser](#doku-wegweiser) |

<details>
<summary><b>Alle Abschnitte</b></summary>

- [Starte Hier (Erster Build)](#starte-hier-erster-build)
- [Täglicher Workflow (Sicherer Standard)](#täglicher-workflow-sicherer-standard)
- [Maschine Auswählen](#maschine-auswählen)
- [Wo Die Build-Ausgaben Liegen](#wo-die-build-ausgaben-liegen)
- [Aktualisieren: Nutzer Vs Entwickler](#aktualisieren-nutzer-vs-entwickler) — [für Nutzer](#für-nutzer-make-update-sicherer-standard) · [für Entwickler](#für-entwickler-make-update-upstream)
- [Experimentell: Toaster-Frontend](#experimentell-toaster-frontend)
- [Lokaler IPK-Feed](#lokaler-ipk-feed)
- [Lokaler Image-Server Für Online Flash](#lokaler-image-server-für-online-flash)
- [Image-Portal Feed-Workflow](#image-portal-feed-workflow)
- [Doku-Wegweiser](#doku-wegweiser)
- [Englisch?](#englisch)

</details>

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
3. Du führst den sicheren Zwei-Phasen-Sync für Repository und gepinnte
   Submodule aus (`make update`, sicherer Standard).
4. Du baust dein erstes Image und bereitest dafür einen lokalen IPK-Feed vor.

Wenn `make check` fehlende Pakete meldet, nutze den Abhängigkeits-Abschnitt in
[docs/de/QUICKSTART.md](docs/de/QUICKSTART.md).

Fastboot-Maschinen wie die HD60 enthalten das reduzierte STB-Lua-Laufzeitbündel
standardmäßig im Image. Es behält sichere Laufzeitwerkzeuge wie `stb-startup`,
`stb-log` und `stb-shell`; ältere Flash-, Backup-, Restore- und
Image-Move-Plugins bleiben bis zur Neutrino-Flashmanager-Integration als
optionale Pakete verfügbar. Multiboot-Plattformen mit STARTUP-Slotwechsel, etwa die
HD51-Familie und H7, enthalten das einzelne Plugin `stb-startup` auch dann,
wenn sie nicht über das OE-A-Feature `fastboot` markiert sind. `logoupdater`
ist ebenfalls standardmäßig enthalten, ebenso das Neutrino-Plugin `mediathek`
und die yWeb-Helfer für OSD-Screenshots und AutoMount (`grab`, `fbshot` und
`autofs`/`automount`). Die Einstellungssicherung für künftige Flash-Abläufe
läuft über Neutrinos `backup.sh` mit `/etc/neutrino/config/tobackup.conf`;
`etckeeper` bleibt als optionales Extra-/Feed-Paket verfügbar und wird nicht
mehr standardmäßig installiert.

## Täglicher Workflow (Sicherer Standard)

```bash
# Aktuelle Top-Level-Änderungen und gepinnte Submodule holen
make update

# Image bauen (nutzt vorhandene Konfiguration weiter)
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Feed-URL anzeigen, die in neue Images geschrieben wird
make feed-server-url MACHINE=hd51

# Optional: das letzte Image für lokale Online-Flash-Tests anbieten
make image-server-start MACHINE=hd51 MACHINEBUILD=mutant51

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

- `builds/<machine>/tmp/deploy/images/<machine>/`

Beispiel für `hd51`:

- `builds/hd51/tmp/deploy/images/hd51/`

Gemeinsame BitBake-/User-Konfiguration liegt in `builds/conf`. Die generierten
`builds/<machine>/conf/local.conf` Dateien sind dünne Machine-Einstiege: Sie
setzen `MACHINE`, `MACHINEBUILD`, `TMPDIR` und die Image-Identität und
inkludieren danach die gemeinsame Config sowie
`builds/<machine>/conf/local.conf.<machine>.inc`. Gemeinsame lokale Layer,
inklusive zentralem Devtool-Workspace, bleiben in
`builds/conf/bblayers.conf.user.inc`.

## Aktualisieren: Nutzer Vs Entwickler

### Für Nutzer: `make update` (sicherer Standard)

```bash
make update
```

Damit werden die **gepinnten Submodul-Commits** ausgecheckt, die zusammen
getestet wurden. Zuerst wird nur das Top-Level-Repository per Fast-Forward
aktualisiert, danach werden die Submodul-URLs synchronisiert, die Submodule
explizit auf die gepinnten Stände gesetzt und die lokale Config-Migration
ausgeführt. Alte Shared-Configs wie `build/conf` werden gesichert und, wenn
eindeutig möglich, nach `builds/conf` plus dünne `builds/<machine>/conf`
Einstiegskonfigurationen migriert.
und hält den normalen Workflow reproduzierbar. Nutze immer diesen Befehl, es
sei denn du weißt was du tust.

Wenn `make update` trotzdem abbricht, liegt die Ursache meist noch in lokalem
Submodul-Zustand, zum Beispiel eigenen Commits oder uncommitted Änderungen in
einem Submodul. Bereinige oder übernimm diesen lokalen Zustand zuerst und
starte dann `make update` erneut.

Ein Submodul-Branch, der Commits enthält die der Pin nicht hat, wird nie
verschoben. Das Submodul bleibt am gepinnten Commit detached, der Branch behält
deine ungepushte Arbeit, und du bekommst einen entsprechenden Hinweis. Pushe die
Layer-Änderung und bumpe den Pin, oder checke den Branch wieder aus mit
`git -C <submodul> checkout <branch>`.

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

## Lokaler IPK-Feed

`make image` und `make feeds` veröffentlichen den aktuellen `deploy/ipk`-Baum
unter `feed-server/www/<MACHINE>/ipk` und starten einen kleinen statischen
HTTP-Server. Die erzeugte Feed-Konfiguration im Image zeigt auf:

```text
http://<host-ip>:33333/<MACHINE>/ipk
```

Im Image reicht danach:

```bash
opkg update
opkg install <paket>
```

Nützliche Kommandos:

```bash
make feed-server-url MACHINE=hd60
make feed-server-urls
make feed-server-start-all
make feed-server-status
make feed-server-stop
```

Wenn `lighttpd` installiert ist, nutzt der Builder ihn; sonst fällt er auf
`python3 -m http.server` zurück. Port `33333/tcp` muss in der Host-Firewall
erlaubt sein, wenn die Box den Feed im Heimnetz erreichen soll.

Für einen öffentlichen Feed überschreibst du die URL in der zentralen
User-/Site-Config `builds/conf/local.conf`:

```conf
IPK_FEED_SERVER = "https://feeds.example.org/tuxbox/${MACHINE}/ipk"
```

Der automatische lokale Feed-Default lässt sich pro Build deaktivieren:

```bash
make image MACHINE=hd60 LOCAL_FEED=0
```

## Lokaler Image-Server Für Online Flash

Der IPK-Feed oben ist für Paketinstallation mit `opkg`. Für Online-Flash-Tests
brauchst du die Image-Artefakte und den PHP-Service aus `online-update`. Der
Builder kapselt das in den `image-server-*` Befehlen:

```bash
make image-server-stage MACHINE=h7 MACHINEBUILD=zgemmah7
make image-server-start MACHINE=h7 MACHINEBUILD=zgemmah7
make image-server-url MACHINE=h7 MACHINEBUILD=zgemmah7
```

Die Standard-URL sieht so aus:

```text
http://<host-ip>:33334/feed/<channel>/<imagedir>
```

Bei neuen lokalen Builds schreibt `make config`/`make image` die lokale
Image-Basis-URL und den Service-Key nach
`builds/<machine>/conf/local-image-server.inc`, damit `/etc/image-version`
standardmäßig `http://<host-ip>:33334/feed/...` und einen funktionierenden
`image_service_key` enthält. Der Key wird einmal erzeugt, liegt in
`image-server/service-key` (`make image-server-key` zeigt ihn, `KEY=…` setzt
ihn) und wird vom lokalen Server als Opt-in-Local-Service-Key akzeptiert —
derselbe Wert auf beiden Seiten, ohne manuelles Paaren. Der dokumentierte
Beispielwert `LOCAL_SERVICE_KEY` und X-only-Platzhalter authentifizieren
nie. Den Einstellungsblock aus `make image-server-url` nutzt du zur
Kontrolle der effektiven Werte oder als manuellen Fallback für ältere
Images. Die separate Zeile `admin webif` öffnest
du im Browser; sie ist nur für Betreiber. Neutrino liest sie nicht und sie wird
nicht für Flash-Downloads genutzt. Logs liegen unter `image-server/logs/`.

Für öffentliche Image-Server überschreibst du den lokalen Default in
`builds/conf/local.conf`:

```conf
TUXBOX_IMAGE_UPDATE_BASE_URL = "https://images.example.org/feed"
TUXBOX_SERVICE_KEY = "public-update-service-key"
```

Mit `LOCAL_IMAGE_SERVER=0` lässt du die Image-Update-URL bei der
Config-Erzeugung den Distro-/Site-Defaults.

## Image-Portal Feed-Workflow

Die `portal-*` Befehle sind der technische Produktionspfad für Catalog-Erzeugung
und Sync auf einen echten Server. Für lokale Tests ist `image-server-*`
einfacher: Es staged mit lokaler Artefakt-URL und startet den PHP-Service.

Portal-Feed-Staging und `catalog.json` aus dem letzten Machine-Deploy erzeugen:

```bash
make portal-catalog MACHINE=hd60 MACHINEBUILD=ax60 \
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
