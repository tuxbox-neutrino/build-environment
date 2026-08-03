# Service-Key

Stand: 2026-08-03

English (maßgebliche Vollfassung): [../SERVICE-KEY.md](../SERVICE-KEY.md)

## Zweck

Der Image-Portal-Service kann öffentlich oder im privaten LAN betrieben
werden. Öffentlich erreichbare Katalog- und Download-Endpunkte werden über
einen gemeinsamen **Service-Key** abgesichert, der diesen Weg nimmt:

1. Buildsystem → Image (Compile-Default in Neutrino +
   `image_service_key=` als Seed in `/etc/image-version`),
2. Image → Neutrino-Einstellung (vom Nutzer änderbar, maskierte Eingabe),
3. Neutrino → Helper `flash-online-check` (explizites `--key`),
4. Helper → Portal als HTTP-Header `X-Tuxbox-Service-Key`,
5. Portal-Validierung.

Der Key ist optional: auf beiden Seiten leer = Betrieb ohne Key.

## Lokaler Builder-Fluss (automatische Paarung)

`make config`/`make image` schreibt `TUXBOX_IMAGE_UPDATE_BASE_URL` **und**
`TUXBOX_SERVICE_KEY` nach `builds/<machine>/conf/local-image-server.inc`.
Der Key kommt aus einem einzigen Resolver (`scripts/image-server.sh key`):

- Eine harte `TUXBOX_SERVICE_KEY`-Zuweisung in den persistenten
  Conf-Quellen (inkl. der bblayers-User-Includes) **gewinnt** — BitBake
  ließe sie ohnehin gewinnen — und wird in die persistente Datei
  `image-server/service-key` gesynct; das Portal folgt damit dem Image.
- Sonst wird einmalig ein Key erzeugt und dort abgelegt (0600,
  shell-sicherer Zeichensatz `A-Za-z0-9._-`, 8–64 Zeichen).
- Der lokale Image-Server seedet denselben Dateiwert als seinen
  Opt-in-Local-Service-Key — Image und Server können nicht auseinanderlaufen.

Kommandos: `make image-server-key` (zeigen), `make image-server-key KEY=…`
(setzen), `make image-server-restart` (rotierten Key auf einen laufenden
Server anwenden). Eine nicht parsebare oder unbrauchbare harte Zuweisung
(Beispielwert, X-only-Platzhalter, fremde Zeichen) bricht `make config` ab,
statt einen Key zu baken, der abgelehnt würde. Bei laufendem Server im
Env-Key-Modus unterdrückt `make image-server-url` die Key-/curl-Zeilen,
wenn der tatsächliche Startwert nicht verifizierbar ist.

## Unbrauchbare Werte

Zwei Werteklassen authentifizieren **nie**, auf keinem Pfad:

- der dokumentierte Beispielwert `LOCAL_SERVICE_KEY` (seit der
  Auth-Härtung hart abgelehnt, auch wenn explizit gesetzt),
- X-only-Platzhalter (`^[Xx]{8,}$`) — Neutrino behandelt sie als „nicht
  gesetzt" und sendet bei privaten URLs stattdessen den Literalwert.

## Portal-Validierung (aktueller Vertrag)

Das Portal akzeptiert drei Key-Quellen parallel: Env-Allowlist
`IMAGE_PORTAL_SERVICE_KEYS` (kommagetrennt, Rotation), verwaltete Keys aus
dem Admin-WebIF (`keys.json`) und den Opt-in-Local-Key
(`IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY=1` plus eigener
`IMAGE_PORTAL_LOCAL_SERVICE_KEY`; nur von privaten/Loopback-Quelladressen).
Vergleiche sind konstantzeitig.

- Key nötig, Header fehlt → `401` (`missing_key`)
- Ungültiger Key → `403` (`invalid_key`)
- Auth konfiguriert, aber kein brauchbarer Key vorhanden → `503`
  (`keys_unavailable`) — fail-closed statt offen
- Zero-Config (keine Keys-/Channels-Datei, keine Env-Keys, kein
  Local-Key-Schalter) → historisch offenes Verhalten für rein lokale Nutzung

## Migration: Box meldet 403

Boxen mit Images von vor dem Generated-Key-Fluss tragen den
X-Platzhalter; Neutrino sendet dann für private URLs den Literalwert —
der by design abgelehnt wird. Zwei Wege:

1. Auf der Box `image_service_key=<Wert aus make image-server-key>` in
   `/etc/image-version` setzen; Neutrino liest die Datei bei jedem Start
   von „Online-Update" neu, kein Reboot nötig.
2. Nach `make config` neu bauen — der generierte Key wird automatisch
   ins Image gebakt.
