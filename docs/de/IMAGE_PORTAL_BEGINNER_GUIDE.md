# Image-Portal Einsteigeranleitung

English: [../IMAGE_PORTAL_BEGINNER_GUIDE.md](../IMAGE_PORTAL_BEGINNER_GUIDE.md)

Diese Anleitung ist für Nutzer ohne Yocto/OE-Vorkenntnisse.

Es gibt drei verschiedene Dinge:

- **IPK-Feed**: Paket-Feed für `opkg`, lokal auf Port `33333`.
- **Lokaler Image-Server**: Image-Dateien für Neutrino Online Flash, ausgeliefert
  über den echten PHP-Service aus `online-update` auf Port `33334`.
- **Portal-Sync**: Produktionsworkflow, der den vorbereiteten Image-Feed auf
  einen echten Webserver kopiert.

Für lokale Online-Flash-Tests nutzt du den lokalen Image-Server. Starte keinen
zusätzlichen statischen Dateiserver von Hand.

## 1. Voraussetzungen

- Builder-Repo: `/home/tg/sources/tuxbox-os-builder`
- Online-Update-Service-Repo: `/home/tg/sources/online-update`
- Ein fertiger Image-Build für deine Maschine

Beispiel-Maschinen:

- `MACHINE=h7 MACHINEBUILD=zgemmah7`
- `MACHINE=hd51 MACHINEBUILD=mutant51`
- `MACHINE=hd60 MACHINEBUILD=mutant60`

## 2. Image Bauen

Im Builder-Repo ausführen:

```bash
cd /home/tg/sources/tuxbox-os-builder
make image MACHINE=h7 MACHINEBUILD=zgemmah7
```

Am Ende des Builds zeigt der Builder den Image-Deploy-Pfad und einen Hinweis
auf `make image-server-start`.

## 3. Lokalen Image-Server Starten

```bash
make image-server-start MACHINE=h7 MACHINEBUILD=zgemmah7
```

Dieser Befehl macht zwei Dinge:

1. Er staged das letzte Image nach `portal-feed/` und erzeugt `catalog.json`.
2. Er startet den PHP-Service aus `online-update` auf Port `33334`.

Der Service nutzt den echten Pfad `/feed/<channel>/<imagedir>/...`. Damit
werden Manifest-Auflösung, Service-Key-Logik und Range-Downloads über denselben
Code getestet, den Neutrino nutzt.

## 4. Werte Für Neutrino Kopieren

```bash
make image-server-url MACHINE=h7 MACHINEBUILD=zgemmah7
```

Beispielausgabe:

```text
image_update_url=http://192.168.1.36:33334/feed/release/zgemmah7
image_manifest_file=manifest.json
image_service_key=LOCAL_SERVICE_KEY

manifest: http://192.168.1.36:33334/feed/release/zgemmah7/manifest.json
curl: curl -H 'X-Tuxbox-Service-Key: LOCAL_SERVICE_KEY' '...'
logs: .../image-server/logs
admin webif: http://192.168.1.36:33334/admin/
```

Der erste Block enthält die drei Werte für die Online-Flash-Einstellungen
von Neutrino. Ändere nichts von Hand, außer die Host-IP ist falsch.

`LOCAL_SERVICE_KEY` ist nur für lokale/private Netze gedacht. Auf öffentlichen
Servern nutzt du richtige Service-Keys.

Die Zeile `admin webif` ist nur für Betreiber: Diese URL öffnest du im
Browser, um die Server-Verwaltung zu erreichen. Neutrino liest diese URL
nicht, und sie gehört nicht zum Flash-Download-Pfad.

## 5. Schneller Host-Test

Nutze die `curl`-Zeile aus `make image-server-url`, zum Beispiel:

```bash
curl -H 'X-Tuxbox-Service-Key: LOCAL_SERVICE_KEY' \
  'http://192.168.1.36:33334/feed/release/zgemmah7/manifest.json'
```

Als Antwort sollte ein JSON-Manifest kommen. Server-Logs liegen hier:

```text
image-server/logs/
```

## 6. Lokalen Server Stoppen

```bash
make image-server-stop
```

Das stoppt nur den lokalen Image-Server auf Port `33334`. Der IPK-Feed-Server
auf Port `33333` bleibt unberührt.

## Produktions-Portal-Sync

Für einen echten Webserver bleibt der technische `portal-*` Workflow zuständig:

```bash
make portal-catalog MACHINE=h7 MACHINEBUILD=zgemmah7 \
  PORTAL_ARTIFACT_BASE_URL=https://images.example.org/feed

make portal-sync \
  PORTAL_SYNC_DEST=user@host:/srv/tuxbox/feed \
  PORTAL_SYNC_DRYRUN=0
```

Nutze `make portal-sync` nur, wenn du den vorbereiteten Feed wirklich auf einen
Server kopieren willst. Lokale Online-Flash-Tests laufen über
`image-server-start`.

## Fehlersuche

- Wenn Neutrino den Server nicht erreicht, nutze die LAN-IP des Hosts, nicht
  `127.0.0.1`, und öffne TCP-Port `33334` in der Firewall.
- Wenn `make image-server-start` `missing manifest` meldet, baue das Image mit
  dem aktuellen Builder-Stand neu.
- Wenn der Service `401`, `403` oder `429` liefert, prüfe den Service-Key. Für
  lokale Tests nutzt du `LOCAL_SERVICE_KEY`.
- Wenn Downloads fehlschlagen, aber das Manifest funktioniert, prüfe
  `image-server/logs/php-server.log`.
