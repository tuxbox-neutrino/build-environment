# Image-Portal Einsteigeranleitung

Diese Anleitung ist für Nutzer ohne Yocto/OE-Vorkenntnisse.

Ziel:

1. Gebaute Image-Artefakte aus `build/build/...` übernehmen.
2. Sauberen Portal-Feed + `catalog.json` erzeugen.
3. Lokalen Web/API-Service starten.
4. Landingpage und API im Browser öffnen.

## 1. Voraussetzungen

- Repository-Pfad: `/home/tg/sources/tuxbox-os-builder`
- Online-Update-Service-Repo: `/home/tg/sources/online-update`
- Ein fertiger Image-Build für deine Maschine (Beispiel: `hd60`)

## 2. Portal-Feed aus Deploy-Artefakten erzeugen

Im Builder-Repo ausführen:

```bash
cd /home/tg/sources/tuxbox-os-builder

make portal-catalog \
  MACHINE=hd60 \
  SOURCE_DIR=/home/tg/sources/tuxbox-os-builder/build/build/tmp-hd60/deploy/images/hd60 \
  PORTAL_FEED_ROOT=/tmp/tuxbox-feed \
  PORTAL_CATALOG_OUT=/tmp/tuxbox-feed/catalog.json \
  PORTAL_ARTIFACT_BASE_URL=http://127.0.0.1:18091 \
  PORTAL_ONLINE_UPDATE_REPO=/home/tg/sources/online-update
```

Das wird erzeugt:

- `/tmp/tuxbox-feed/nightly/hd60/<build_date>/...`
- `/tmp/tuxbox-feed/catalog.json`

## 3. Statischen Feed-Server starten

Damit werden die echten Artefakt-Dateien ausgeliefert:

```bash
cd /tmp/tuxbox-feed
python3 -m http.server 18091
```

Dieses Terminal offen lassen.

## 4. API + Landingpage starten

Zweites Terminal öffnen:

```bash
cd /home/tg/sources/online-update

ONLINE_UPDATE_CATALOG=/tmp/tuxbox-feed/catalog.json \
ONLINE_UPDATE_ARTIFACT_BASE_URL=http://127.0.0.1:18091 \
ONLINE_UPDATE_PORTAL_BASE_URL=http://127.0.0.1:18090 \
php -S 127.0.0.1:18090 -t public
```

## 5. Im Browser öffnen

- Landingpage: `http://127.0.0.1:18090/`
- Catalog-API: `http://127.0.0.1:18090/api/v1/catalog.php`
- Latest-API: `http://127.0.0.1:18090/api/v1/latest.php?channel=nightly&imagedir=hd60`
- Legacy-Check: `http://127.0.0.1:18090/legacy/update.php?boxname=hd60&image_type=nightly`

## 6. Neutrino auf diesen Service zeigen lassen

Auf der Testbox setzen:

- `image_update_url=http://<host-ip>:18091/nightly/hd60`
- `image_manifest_file=manifest.json`
- optional `image_discovery_api_url=http://<host-ip>:18090/api/v1`

Nutze die echte LAN-IP des Hosts statt `127.0.0.1`.

## Fehlersuche

- Wenn im Browser auf `:18090` nichts erscheint, prüfen ob der PHP-Server noch läuft.
- Wenn die API `catalog unavailable` zeigt, `ONLINE_UPDATE_CATALOG` prüfen.
- Wenn Download-Redirects fehlschlagen, statischen Server auf `:18091` prüfen.
- Wenn die Neutrino-Box den Host nicht erreicht, LAN-IP und Firewall prüfen.
