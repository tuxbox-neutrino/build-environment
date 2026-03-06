# Toaster-Integration (Experimentell)

Status: experimentell.

Diese Funktion ist für lokale Tests und spätere Integrationsarbeit verfügbar,
gehört aber aktuell nicht zum stabilen Standard-Workflow des Projekts.

## Geltungsbereich

- Für Entwickler gedacht, die eine Web-Oberfläche um BitBake-Builds nutzen wollen.
- Die aktuelle Umsetzung verwendet Helfer-Targets im Top-Level-`Makefile`.
- Verhalten und Defaults können sich ändern.

## Kommandos

Einmalig initialisieren (idempotent):

```bash
make init-toaster MACHINE=hd60 MACHINEBUILD=ax60
```

Start und Stop:

```bash
make toaster-start TOASTER_WEBPORT=127.0.0.1:18083
make toaster-stop
```

Vorhandenes Build-Verzeichnis als Toaster-Projekt importieren:

```bash
make toaster-import-build
```

Bereits importiertes Projekt nach lokalen `conf/`- oder Layer-Änderungen
neu einlesen:

```bash
make toaster-reconfigure-build
```

Importierte Projektseite öffnen:

```bash
make toaster-open-build \
  TOASTER_WEBPORT=127.0.0.1:18083
```

Admin-Benutzer erstellen (interaktiv):

```bash
make toaster-create-admin
```

Admin-Benutzer erstellen (non-interaktiv):

```bash
make toaster-create-admin \
  TOASTER_ADMIN_USERNAME=admin \
  TOASTER_ADMIN_EMAIL=admin@example.org \
  TOASTER_ADMIN_PASSWORD='dein-passwort'
```

Beispiel für Admin-Login-URL:

- `http://127.0.0.1:18083/admin`

## Was `init-toaster` macht

- Stellt sicher, dass Build-Konfiguration existiert (führt bei Bedarf `make config` aus).
- Erstellt ein dediziertes venv unter `.tuxbox/toaster-venv`.
- Installiert `poky/bitbake/toaster-requirements.txt`.
- Installiert unter Python 3.13+ zusätzlich `legacy-cgi` im venv.
- Initialisiert Toaster-Metadaten über `toaster start noweb nobuild` und stoppt wieder.

## Wichtige Variablen

- `TOASTER_WEBPORT`: Bind-Adresse/Port (Default `localhost:8000`)
- `TOASTER_PYTHON`: Python-Executable für die venv-Erstellung (Default `python3`)
- `TOASTER_BUILD_DIR`: Build-Verzeichnis für `oe-init-build-env`
- `TOASTER_DIR`: Toaster-Datenverzeichnis (Default `.tuxbox/toaster`)
- `TOASTER_START_ARGS`: zusätzliche Argumente für `toaster start`
- `TOASTER_ADMIN_USERNAME`: Admin-Benutzername (non-interaktive Erstellung)
- `TOASTER_ADMIN_EMAIL`: Admin-E-Mail (non-interaktive Erstellung)
- `TOASTER_ADMIN_PASSWORD`: Admin-Passwort (non-interaktive Erstellung)
- `TOASTER_IMPORT_NAME`: Toaster-Projektname für Import/Reconfigure
  (Default `DISTRO-build`, z. B. `tuxbox-build`)
- `TOASTER_IMPORT_PATH`: vorhandenes Build-Verzeichnis für den Import
  (Default `TOASTER_BUILD_DIR`)
- `TOASTER_IMPORT_CALLBACK`: optionales Callback-Skript für `buildimport`
- `TOASTER_LAST_PROJECT_FILE`: lokale Datei mit letzter importierter Projekt-ID

## Toaster mit vorhandenem Build-Verzeichnis verwenden

Wenn Toaster direkt auf eurem bestehenden Build-Verzeichnis arbeiten soll
(Default `TOASTER_BUILD_DIR`):

1. `make toaster-import-build` ausführen.
2. `make toaster-open-build` öffnen (oder die ausgegebene URL nutzen).
3. Nach manuellen Config-/Layer-Änderungen `make toaster-reconfigure-build`
   ausführen.

Wichtig:

- Keinen normalen Build und keinen Toaster-Build gleichzeitig im selben
  Build-Verzeichnis laufen lassen.
- Serielle Nutzung ist unkritisch (normaler Build, dann Toaster-Build oder
  umgekehrt).
- Toaster kann im importierten project-specific-Modus markierte
  Toaster-Konfigabschnitte in `conf/` schreiben/aktualisieren.

## Häufiges Problem: Port bereits belegt

Symptom:

- `CommandError: Port 8000 is already in use`

Lösung:

1. Anderen Port nutzen:
   `make toaster-start TOASTER_WEBPORT=127.0.0.1:18083`
2. Oder den bereits laufenden Dienst auf `8000` beenden.

## Laufzeitdateien

- Session-PID: `build/.toaster-session.pid`
- Session-Log: `build/toaster_session.log`
- Toaster-PIDs: `build/.toastermain.pid`, `build/.runbuilds.pid`
- Letzte importierte Projekt-ID:
  `.tuxbox/toaster/.last-imported-project-id`

## Aufräumen

Toaster zuerst stoppen:

```bash
make toaster-stop
```

Optional lokales Cleanup:

```bash
rm -rf .tuxbox/toaster-venv .tuxbox/toaster
```
