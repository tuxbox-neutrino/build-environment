# Konzept: Flash-Integration Neutrino + flash/ofgwrite

Stand: 2026-03-10

## Ziel

Eine saubere, datengetriebene Flash-Architektur für Neutrino, bei der:

- `flash` die stabile öffentliche API ist (UI/Lua/Shell).
- `ofgwrite` die robuste Low-Level-Schreibschicht bleibt.
- Legacy-Updatepfade (`CFlashUpdate` in `update.cpp`) für ältere Boxen
  unverändert weiter funktionieren.

## Harte Leitplanken

- Keine disruptive Änderung am bestehenden Legacy-Updatecode.
- Neue Flash-Workflows nur dort aktivieren, wo Runtime-Fähigkeiten vorhanden sind.
- Slot-/Layout-/Maschinenlogik darf nicht mehr in mehreren UI-Komponenten
  dupliziert werden.
- Immer zuerst Preflight, dann Schreiben.

## Verifizierter Ist-Zustand

- Neutrino-Legacy-Flow enthält direkte Flashlogik in `update.cpp` (`fileType == 'Z'`,
  Slotauswahl, `STARTUP`-Umschaltung, Aufruf `ofgwrite_caller`).
- Runtime liefert bereits Dispatcher und Profile:
  - `/usr/bin/flash` (dispatch `script|ofgwrite`)
  - `/etc/tuxbox/flash-backend.conf`
  - `/etc/tuxbox/flash-machine-profile.conf`
  - `flash-backend-preflight`
- `ofgwrite` unterstützt Multiboot-Slotparameter (`-m`), `-n` (nowrite), weitere
  device-spezifische Optionen.
- STB-Lua-Plugins nutzen aktuell überwiegend servicebasierte Shell-Aufrufe
  (`systemctl start flash@<slot>`), mit eigener Slot-/Layout-Logik.

## Zielarchitektur

### Schichtmodell

1. UI/Lua/API-Schicht:
- Neutrino-Menü und Lua-Plugins fragen nur hohe Intentionsparameter ab:
  - Zielslot
  - Quelle (`online`/`local`/`restore`)
  - optional `force`

2. Orchestrierung:
- Einziger Einstieg: `/usr/bin/flash <slot> <mode> [<arg>] [force]`
  - `mode=online|local|restore`
- Verantwortlich für:
  - Preflight
  - Slotschutz
  - ggf. Settings-Backup
  - Backendwahl

3. Schreibschicht:
- `ofgwrite` (für Maschinen/Layouts, die davon profitieren)
- `script`-Backend (Legacy/andere Layouts)

## Runtime-Entscheidung: Legacy vs neues Modell

Neuer Neutrino-Flashpfad wird nur angeboten, wenn alle Bedingungen erfüllt sind:

- `/usr/bin/flash` existiert und ist ausführbar.
- `/etc/tuxbox/flash-machine-profile.conf` existiert.
- `/etc/tuxbox/flash-backend.conf` ist lesbar.

Wenn nicht erfüllt:

- Nur Legacy-Updatepfad (`CFlashUpdate`) sichtbar/aktiv.

Damit bleibt Althardware ohne neues Profil vollständig kompatibel.

## Neutrino-Integration (ohne Legacy-Bruch)

Neue Dateien in `gui-neutrino`:

- `src/gui/flash_profile.h/.cpp`
  - Lädt und validiert Runtime-Profile.
  - Kapselt Detection-Logik (`isAvailable()`, Backend, Capabilities).
- `src/gui/flash_result.h/.cpp`
  - Normiert Exitcode-/Fehler-Mapping für UI.
- `src/gui/flash_manager.h/.cpp`
  - Neuer, datengetriebener Flash-Flow über `/usr/bin/flash`.
  - Slotauswahl, Bestätigung, Aufruf, Ergebnisdarstellung.

Bestehende Dateien:

- `src/gui/update.cpp`: unverändert (Legacy bleibt).
- `src/gui/update_menue.cpp`: zusätzlicher Menüeintrag für den neuen Manager,
  nur bei erfolgreicher Runtime-Detection.

## Exitcode-/Fehlervertrag

Zwischen `flash` und Neutrino wird ein stabiler Exitcodevertrag festgelegt:

- `0`: Erfolg
- `1`: generischer Fehler
- `2`: ungültige Eingabe/Image nicht gefunden
- `3`: Preflight fehlgeschlagen
- `4`: Schreibfehler
- `5`: Verifikation/Nachprüfung fehlgeschlagen
- `6`: Active-Slot blockiert oder Backup-Anforderung nicht erfüllt
- `127`: Backend/Binary nicht gefunden

Wichtig:

- `flash-dispatch.sh`, `flash-backend-script.sh` und
  `flash-backend-ofgwrite.sh` müssen denselben Vertrag liefern.
- Lokales Runtime-Profil hat Vorrang gegenüber Remote-Metadaten:
  `flash-backend.conf`/`flash-machine-profile.conf` schlagen manifestbasierte
  Backend-Hinweise.

## Rolle von Lua-Plugins

Kurzfristig:

- Lua ruft weiterhin `systemctl start flash@<slot>` bzw. `/usr/bin/flash`.

Mittelfristig:

- Lua entfernt eigene Slot-/Layout-Heuristiken und delegiert vollständig an
  `flash` (Datenquelle bleibt Profil + `/etc/image-version`).

## Sicherheits- und Stabilitätsanforderungen

- Kein echter Schreiblauf ohne Preflight.
- Einheitlicher Statuskanal für UI/Automatisierung:
  `/run/tuxbox/flash/status.json` mit stabilen Phasen-IDs.
- Active-Slot-Policy standardmäßig restriktiv:
  - deny by default
  - explizite Freigabe nur mit Backup-Policy
- Profilvalidierung zur Laufzeit gegen reales Systemlayout
  (`/proc/cmdline`, `/proc/mounts`, `/proc/partitions`/`/proc/mtd`).
- Downloadpfade müssen Integritätsprüfung ermöglichen
  (mindestens Hash-Validierung, optional Signaturphase).

## Umsetzungsphasen

### Phase 1: Minimal-invasive Einführung

- Exitcodevertrag backendübergreifend festziehen.
- Neue Neutrino-Klassen `flash_profile`, `flash_result`, `flash_manager` einführen.
- Neuen Menüpunkt in `update_menue.cpp` hinzufügen (feature-gated über Runtime).
- Legacypfad unverändert lassen.

### Phase 2: Lua entkoppeln

- `stb_flash`/`stb_local-flash` Slot-/Layoutlogik abbauen.
- Plugins an die `flash`-API andocken (nur Parameterübergabe + UI).

### Phase 3: Härtung und Rollout

- Fehler-/Statusmodell in UI verbessern.
- Optional maschinenabhängige Deep-Preflight-Checks erweitern.
- Dokumentation und Rollback-Runbook finalisieren.

## Go/No-Go Kriterien

Alle Punkte müssen erfüllt sein:

1. Kein Flash startet ohne erfolgreichen Preflight.
2. Active-Slot-Schutz reproduzierbar aktiv (inkl. Backup-Policy-Gates).
3. Legacy-Updateflow auf Altsystemen unverändert lauffähig.
4. Dispatcher-Routing `script|ofgwrite` deterministisch verifiziert.
5. Mindestens ein realer HD60-Testlauf mit neuem UI-Flow erfolgreich
   (Flash, Boot, Versionsverifikation).

## Konkrete Risiken und Gegenmaßnahmen

- Risiko: Bypass am Dispatcher (direkte `ofgwrite_caller`-Aufrufe).
  Maßnahme: immer Dispatcher/Preflight erzwingen oder Caller auf Dispatcher
  vereinheitlichen.
- Risiko: Duplizierte Slot-Erkennung in mehreren Stellen.
  Maßnahme: gemeinsame Helper/Lib-Funktion für Slot-Detection.
- Risiko: Profil passt nicht zur realen Partitionierung.
  Maßnahme: Runtime-Abgleich + harter Abort.
- Risiko: Branch-Drift im Flashskript.
  Maßnahme: Refactor-Branch zeitnah stabilisieren/mergen, nicht dauerhaft als
  Release-Basis führen.

## Ergebnis

Dieses Modell hält die Legacy stabil, verschiebt neue Komplexität in eine
profilegetriebene Orchestrierungsschicht und nutzt `ofgwrite` weiter dort, wo
es robust ist. Dadurch werden Neutrino-UI, Lua-Plugins und Shell-Aufrufe auf
eine gemeinsame, wartbare Flash-API konsolidiert.
