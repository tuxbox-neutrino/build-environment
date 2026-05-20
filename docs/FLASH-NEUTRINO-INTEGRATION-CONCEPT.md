# Konzept: Flash-Integration Neutrino + flash/ofgwrite

Stand: 2026-03-11

## Ziel

Eine saubere, datengetriebene Flash-Architektur für Neutrino, bei der:

- `ofgwrite` der primäre Neutrino-Flashpfad ist und die bisher über
  `flash`/`flash-script` validierten Kernfähigkeiten eigenständig
  abbildet.
- `flash` als optionale öffentliche Kompatibilitäts-API für Lua-Plugins,
  Shell und Tests erhalten bleibt, aber keine harte Neutrino-Abhängigkeit
  mehr ist.
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
- Runtime lieferte für die Validierungsphase Dispatcher und Profile:
  - `/usr/bin/flash` (dispatch `script|ofgwrite`)
  - `/etc/tuxbox/flash-backend.conf`
  - `/etc/tuxbox/flash-machine-profile.conf`
  - `flash-backend-preflight`
- Diese Dispatcher-Schicht war wichtig, um Local-/Active-/Inactive-Flash
  reproduzierbar zu testen. Sie beschreibt nicht mehr automatisch den
  finalen Neutrino-Aufrufpfad.
- `ofgwrite` unterstützt Multiboot-Slotparameter (`-m`), `-n` (nowrite), weitere
  device-spezifische Optionen.
- STB-Lua-Plugins nutzen aktuell überwiegend servicebasierte Shell-Aufrufe
  (`systemctl start flash@<slot>`), mit eigener Slot-/Layout-Logik.

## Zielarchitektur

### Schichtmodell

1. Neutrino-UI-Schicht:
- Neutrino fragt nur hohe Intentionsparameter ab:
  - Zielslot
  - Quelle (`online`/`local`/`restore`)
  - optional `force`
- Neutrino übergibt diese Parameter an den Ofgwrite-basierten Runtimepfad
  bzw. dessen internen Handoff. Neutrino soll nicht von `/usr/bin/flash`
  oder einem optional installierten STB-Plugin abhängen.

2. Optionale Plugin-/Shell-Schicht:
- Lua-Plugins und Shell-Tools können weiterhin `/usr/bin/flash` verwenden:
  `/usr/bin/flash <slot> <mode> [<arg>] [force]`
  - `mode=online|local|restore`
- Diese Schicht bleibt als Bedien- und Kompatibilitäts-API erhalten, wenn
  der Nutzer das entsprechende STB-Plugin bzw. Runtimepaket installiert.

3. Ofgwrite-Orchestrierung:
- Verantwortlich für:
  - Preflight
  - Slotschutz
  - ggf. Settings-Backup
  - Archiv-/Payload-Handoff
  - Active-/Inactive-Slot-Ablauf

4. Schreibschicht:
- `ofgwrite` ist der primäre Pfad für Neutrino.
- `script`/`flash-script` bleibt als Plugin-/Shell-Kompatibilität und für
  Alt- bzw. Sonderpfade verfügbar.

## Runtime-Entscheidung: Legacy vs neues Modell

Neuer Neutrino-Flashpfad wird nur angeboten, wenn alle Bedingungen erfüllt sind:

- `ofgwrite` bzw. der Ofgwrite-Handoff ist vorhanden.
- Die für Ofgwrite benötigten Maschinen-/Slotinformationen sind verfügbar.
- Preflight kann das reale Systemlayout erfolgreich verifizieren.

Wenn nicht erfüllt:

- Nur Legacy-Updatepfad (`CFlashUpdate`) sichtbar/aktiv.

Damit bleibt Althardware ohne neues Profil vollständig kompatibel.

## Neutrino-Integration (ohne Legacy-Bruch)

Neue Dateien in `gui-neutrino`:

- `src/gui/flash_manager.h/.cpp`
  - Enthält den neuen, datengetriebenen Neutrino-Flash-Flow über den
    Ofgwrite-basierten Runtimepfad. `/usr/bin/flash` ist nicht die
    Neutrino-Ziel-API, sondern bleibt der optionale Plugin-/Shell-Pfad.
  - Der bisherige öffentliche `ofgwrite_caller` wird durch einen internen
    Ofgwrite-Handoff ersetzt. Direkte Aufrufe eines öffentlichen
    `ofgwrite_caller` aus Neutrino sollen verschwinden; der Handoff ist
    Implementierungsdetail des Ofgwrite-Pfads und keine Plugin-API.
  - Implementiert `CFlashManager` als additive Einheit neben Legacy.
  - Slot-Auswahl, Archiv-Extraktion (soweit vor dem Dispatcher-Aufruf
    nötig), Exitcode-Mapping zu Locale-UI.
- Optional später: interne Helper (`flash_profile`, `flash_result`) nur falls
  `flash_manager.*` inhaltlich zu groß wird.

Bestehende Dateien:

- `src/gui/update.h`: unverändert (Legacy bleibt).
- `src/gui/update.cpp`: unverändert (Legacy bleibt).
- `src/gui/update_menue.cpp`: nur minimaler zusätzlicher Menüeintrag auf
  `CFlashManager`, runtime-gated.

## Exitcode-/Fehlervertrag

Zwischen Ofgwrite-Handoff und Neutrino wird ein stabiler Exitcodevertrag
festgelegt. `/usr/bin/flash` soll denselben Vertrag spiegeln, damit optionale
Plugin-/Shell-Caller konsistent bleiben:

- `0`: Erfolg
- `1`: generischer Fehler
- `2`: ungültige Eingabe/Image nicht gefunden
- `3`: Preflight fehlgeschlagen
- `4`: Schreibfehler
- `5`: Verifikation/Nachprüfung fehlgeschlagen
- `6`: Active-Slot blockiert oder Backup-Anforderung nicht erfüllt
- `127`: Backend/Binary nicht gefunden

Wichtig:

- Ofgwrite-Handoff und optionale `flash`-Wrapper müssen denselben Vertrag
  liefern.
- Lokales Runtime-Profil hat Vorrang gegenüber Remote-Metadaten:
  `flash-backend.conf`/`flash-machine-profile.conf` schlagen manifestbasierte
  Backend-Hinweise.

## Rolle von Lua-Plugins

Kurzfristig:

- Lua ruft weiterhin `systemctl start flash@<slot>` bzw. `/usr/bin/flash`.

Mittelfristig:

- Lua entfernt eigene Slot-/Layout-Heuristiken und delegiert vollständig an
  `flash` als optionale Plugin-/Shell-API. Diese Plugin-Schicht bleibt von
  der Neutrino-internen Ofgwrite-Integration getrennt.

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
- `flash_manager.h/.cpp` einführen.
- Neuen Menüpunkt in `update_menue.cpp` hinzufügen (feature-gated über Runtime,
  minimaler Hook).
- Legacypfad unverändert lassen.

### Phase 2: Zielarchitektur trennen

- Neutrino vom Dispatcher-/Pluginpfad entkoppeln und auf den Ofgwrite-Pfad
  fokussieren.
- `flash` als optionalen Plugin-/Shell-Vertrag dokumentieren und aus der
  Neutrino-Verfügbarkeitsprüfung entfernen.

### Phase 3: Lua entkoppeln

- `stb_flash`/`stb_local-flash` Slot-/Layoutlogik abbauen.
- Plugins an die `flash`-API andocken (nur Parameterübergabe + UI).

### Phase 4: WebIF/APIv4 Vorbereitung

- Gemeinsamen Laufzeitvertrag für GUI und WebIF festziehen:
  - gleicher Intent-/Exitcodevertrag,
  - gleiche Exitcodes,
  - gleicher Statuskanal (`/run/tuxbox/flash/status.json`).
- APIv4-Endpunkte vorplanen für:
  - Flash-Precheck/Start/Status,
  - OPKG-Precheck/Run/Status.
- Schnittstelle so vorbereiten, dass eine spätere WebIF-Übernahme
  ohne Umbau der Flash-Core-Logik möglich ist.

### Phase 5: Härtung und Rollout

- Fehler-/Statusmodell in UI verbessern.
- Optional maschinenabhängige Deep-Preflight-Checks erweitern.
- Dokumentation und Rollback-Runbook finalisieren.

## Go/No-Go Kriterien

Alle Punkte müssen erfüllt sein:

1. Kein Flash startet ohne erfolgreichen Preflight.
2. Active-Slot-Schutz reproduzierbar aktiv (inkl. Backup-Policy-Gates).
3. Legacy-Updateflow auf Altsystemen unverändert lauffähig.
4. Ofgwrite-Pfad deterministisch verifiziert; optionaler `flash`-Wrapper
   spiegelt den Exitcodevertrag.
5. Mindestens ein realer HD60-Testlauf mit neuem UI-Flow erfolgreich
   (Flash, Boot, Versionsverifikation).

## Konkrete Risiken und Gegenmaßnahmen

- Risiko: Vermischung von Test-Dispatcher und finalem Neutrino-Pfad.
  Maßnahme: Workitems und Code trennen zwischen validierter Testhistorie,
  Neutrino-Ofgwrite-Pfad und optionalem `flash`-Plugin-/Shell-Pfad.
- Risiko: Öffentlicher `ofgwrite_caller` wird zur zweiten API.
  Maßnahme: Öffentliche Caller verschwinden; Neutrino nutzt nur den internen
  Ofgwrite-Handoff, Plugins nutzen bei Bedarf `/usr/bin/flash`.
- Risiko: Duplizierte Slot-Erkennung in mehreren Stellen.
  Maßnahme: gemeinsame Helper/Lib-Funktion für Slot-Detection.
- Risiko: Profil passt nicht zur realen Partitionierung.
  Maßnahme: Runtime-Abgleich + harter Abort.
- Risiko: Branch-Drift im Flashskript.
  Maßnahme: Refactor-Branch zeitnah stabilisieren/mergen, nicht dauerhaft als
  Release-Basis führen.

## Ergebnis

Dieses Modell hält die Legacy stabil, verschiebt den Neutrino-Pfad klar auf
Ofgwrite und lässt `flash` als optionale Plugin-/Shell-Kompatibilität stehen.
Damit werden Testhistorie, Neutrino-Integration und optionale Erweiterungen
nicht mehr vermischt.
