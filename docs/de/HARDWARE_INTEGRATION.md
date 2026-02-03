# Hardware-Integration Leitfaden (Neutrino + libstb-hal)

English: [../HARDWARE_INTEGRATION.md](../HARDWARE_INTEGRATION.md)

Dieses Dokument erklärt, wie Hardware-Support verdrahtet ist und warum nicht
jede OE-Alliance Maschine sofort für Neutrino funktioniert.

## Inhalt

- [Realitätscheck](#realitätscheck)
- [Kurzglossar](#kurzglossar)
- [Wo Hardware-Support liegt](#wo-hardware-support-liegt)
- [OE-Alliance Referenzen](#oe-alliance-referenzen)
- [libstb-hal Auswahl und Boxmodel Mapping](#libstb-hal-auswahl-und-boxmodel-mapping)
- [Integrationsfluss (Entscheidung)](#integrationsfluss-entscheidung)
- [MACHINE vs MACHINEBUILD](#machine-vs-machinebuild)
- [Vorhandene Maschine in meta-brands: Integrationsschritte](#vorhandene-maschine-in-meta-brands-integrationsschritte)
- [Hardware Caps: wo man sie findet](#hardware-caps-wo-man-sie-findet)
- [BOXMODEL-Verzweigungen in Neutrino reduzieren](#boxmodel-verzweigungen-in-neutrino-reduzieren)
- [Beispiel: Neues Boxmodel hinzufügen](#beispiel-neues-boxmodel-hinzufügen)
- [Workflow: Neue Maschine hinzufügen](#workflow-neue-maschine-hinzufügen)
- [Prüfliste](#prüfliste)
- [Beiträge Upstream](#beiträge-upstream)

## Realitätscheck

- OE-Alliance liefert 300+ Maschinen-Definitionen in `meta-brands`.
- Das Build-System kann viele davon parsen/bauen, aber wir testen nur einen Teil.
- Neutrino benötigt `libstb-hal` Support. Wenn eine Maschine nicht in der
  `boxmodel` Liste ist, brechen Builds oder das Runtime-Verhalten.
- Support hinzuzufügen ist möglich und willkommen, aber es ist echte
  Bring-up-Arbeit.
- Für eine echte Integration brauchst du Hardware (seriell/SSH und ein
  funktionierendes Kernel/DTB). Ohne Box geht nur best-effort.

## Kurzglossar

- `MACHINE`: der OE-Alliance Maschinenname, den du für den Build setzt.
- `MACHINEBUILD`: optionale OEM-Variante für die gleiche Basis-Maschine.
- `boxtype`: grobe Familie (`generic`, `armbox`, `mipsbox`).
- `boxmodel`: exakter String, den libstb-hal für die Box erwartet (oft = `MACHINE`).
- `libstb-hal`: Hardware-Abstraktions-Layer für Neutrino.

## Wo Hardware-Support liegt

- **Maschinen-Definitionen**:
  `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`
- **Kernel/DTB/Bootloader**:
  `oe-alliance/meta-brands/meta-<brand>/recipes-*`
- **Distro und Images**:
  `meta-tuxbox` (image/packagegroups, distro config)
- **Neutrino und Hardware-Abstraktion**:
  `meta-neutrino` (Neutrino, `libstb-hal`)

## OE-Alliance Referenzen

OE-Alliance pflegt eine öffentliche Liste von Maschinen und Herstellern. Sie
ist ein guter Startpunkt, aber keine Garantie, dass Neutrino-Integration
existiert.

- Lokal (wenn Submodule ausgecheckt): `oe-alliance/README.md`
- Upstream: `https://github.com/oe-alliance/oe-alliance-core/blob/master/README.md`

## libstb-hal Auswahl und Boxmodel Mapping

`meta-tuxbox/conf/distro/tuxbox.conf` setzt `FLAVOUR` (default: `tuxbox`). Das
`libstb-hal` Recipe includiert `${FLAVOUR}.inc`, das den Upstream Repo wählt:

- `tuxbox.inc` -> `tuxbox-neutrino/library-stb-hal`
- `ni.inc` -> `neutrino-images/ni-libstb-hal`
- `tango.inc` -> `TangoCash/libstb-hal-tangos`

Hinweis: Diese Forks sind nicht garantiert kompatibel zueinander. Dieser Guide
fokussiert `library-stb-hal` (tuxbox flavour). Die Community teilt Wissen
über Forks, aber Stil und Commit-Kultur können abweichen. Ändere nur in dem
Fork, gegen den du wirklich baust.

Der Build übergibt:

- `--with-boxtype=${TARGET_ARCH}box`
- `--with-boxmodel=${MACHINE}`

Neutrino nutzt die gleichen Flags (siehe
`meta-neutrino/recipes-neutrino/neutrino/*.inc`). Stelle sicher, dass beide
Recipes übereinstimmen. Wenn die Namen abweichen, überschreibe
`EXTRA_OECONF` via bbappend.

Gültige boxtype Werte sind `generic`, `armbox`, `mipsbox`. Boxtype ist eine
breite Familie, boxmodel ist der exakte Geräte-String. Die `boxmodel` Liste ist
in `library-stb-hal/acinclude.m4` definiert (und ähnlich in anderen Forks).

Aktuelle boxmodels (library-stb-hal):

- generic: `generic`, `raspi`
- armbox: `hd60`, `hd61`, `multibox`, `multiboxse`, `hd51`, `bre2ze4k`, `h7`,
  `e4hdultra`, `protek4k`, `osmini4k`, `osmio4k`, `osmio4kplus`, `vusolo4k`,
  `vuduo4k`, `vuduo4kse`, `vuultimo4k`, `vuuno4k`, `vuuno4kse`, `vuzero4k`
- mipsbox: `vuduo`, `vuduo2`, `gb800se`, `osnino`, `osninoplus`, `osninopro`

Wenn dein Maschinenname nicht in dieser Liste ist, fällt `configure` und
Neutrino kann nicht laufen. Du musst das boxmodel und die Hardware Caps
hinzufügen (oder `MACHINE` via bbappend auf ein vorhandenes boxmodel mappen).

## Integrationsfluss (Entscheidung)

```
Start
  |
  +-- Ist MACHINE bereits in meta-brands? -- ja --> Schritte fuer vorhandene Maschine
  |                                         nein -> Neue Maschine anlegen
```

Integrations-Map (vorhandene meta-brands Maschine):

```
OE-A machine.conf -> MACHINE -> libstb-hal configure -> hardware_caps -> Neutrino
        |                |             |                    |            |
        |                |             |                    |            \- nutzt libstb-hal headers/libs
        |                |             |                    \- model-spezifische Caps
        |                |             \- --with-boxtype/--with-boxmodel
        |                \- Name muss bekanntes boxmodel sein (oder override)
        \- Kernel/DTB/Driver existieren bereits
```

## MACHINE vs MACHINEBUILD

- `MACHINE` wählt die Basis-Hardware-Config:
  `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`.
- `MACHINEBUILD` wählt eine OEM- oder Varianten-Konfiguration für dieselbe
  Basis-Maschine. Das toggelt oft Tuner, Frontpanel, Branding, Partitionen oder
  Image-Layout.
- Manche OE-A Layer setzen `MACHINEOVERRIDES` basierend auf `MACHINEBUILD` und
  erlauben damit recipe-spezifische Overrides.
- Wenn es keine OEM-Varianten gibt, kann `MACHINEBUILD` weggelassen werden (oder
  = `MACHINE`).

Wie man gültige `MACHINEBUILD` Werte findet:

- Maschine und Includes nach `MACHINEBUILD` oder `MACHINEOVERRIDES` durchsuchen.
- In vielen OE-A Layern stehen OEM-Varianten in
  `conf/machine/include/*-oem.inc` oder `*oem*.inc`.
- Schnellsuche:

```bash
rg -n "MACHINEBUILD" oe-alliance/meta-brands/meta-<brand>/conf/machine -S
```

Bei der Integration von `libstb-hal`:

- `MACHINE`/boxmodel ist der zentrale Input. `MACHINEBUILD` mappt **nicht**
  automatisch auf boxmodel.
- Wenn eine OEM-Variante andere Caps braucht, lege ein neues boxmodel an und
  mappe es via bbappend overrides.

## Vorhandene Maschine in meta-brands: Integrationsschritte

Wenn eine Box bereits in `oe-alliance/meta-brands` existiert, kannst du die
Maschinen-Definition überspringen und dich auf Neutrino-Integration fokussieren:

1) **MACHINE Name bestätigen.**
   - `make list-machines` und `make machine-info MACHINE=<name>` nutzen.
   - Wenn OEM-Varianten existieren, `MACHINEBUILD` setzen.
   - Der Maschinenname muss zu einem libstb-hal boxmodel passen oder gemappt werden.

2) **Boxtype/boxmodel zwischen libstb-hal und Neutrino abgleichen.**
   - Neutrino nutzt `--with-boxtype=${TARGET_ARCH}box` und
     `--with-boxmodel=${MACHINE}`.
   - Wenn `TARGET_ARCH` einen nicht unterstützten boxtype liefert (z.B.
     `aarch64box`, `mipselbox`), auf `armbox` oder `mipsbox` überschreiben.
   - Bevorzuge bbappends in `meta-tuxbox`, damit Overrides in der Distro liegen.

Beispiel-Overrides:

```bitbake
# meta-tuxbox/recipes-neutrino/libstb-hal/libstb-hal_git.bbappend
EXTRA_OECONF:append = " --with-boxtype=armbox --with-boxmodel=<boxmodel>"

# meta-tuxbox/recipes-neutrino/neutrino/neutrino_git.bbappend
EXTRA_OECONF:append = " --with-boxtype=armbox --with-boxmodel=<boxmodel>"
```

3) **libstb-hal für die Maschine vorbereiten.**
   - boxmodel zu `library-stb-hal/acinclude.m4` hinzufügen.
   - Caps in `libarmbox/` oder `libmipsbox/` setzen (siehe unten).
   - Backend-Code in `libarmbox/` oder `libmipsbox/` anpassen, wenn Device-Nodes
     oder IOCTLs für die neue SoC/Driver-Stack abweichen.

4) **Bauen und Smoke-Test auf Hardware.**
   - `bitbake libstb-hal -c compile`
   - `bitbake neutrino`
   - `bitbake tuxbox-image`
   - Prüfen: `/proc/stb/info/*`, video/audio, demux, frontpanel, standby.

## Hardware Caps: wo man sie findet

`libstb-hal` stellt Hardware-Fähigkeiten über `hw_caps_t` bereit:

- Struct-Definition: `library-stb-hal/include/hardware_caps.h`
- ARM Caps: `library-stb-hal/libarmbox/hardware_caps.c`
- MIPS Caps: `library-stb-hal/libmipsbox/hardware_caps.c`
- Generic/PC: `library-stb-hal/libgeneric-pc/hardware_caps.c`
- Raspberry Pi: `library-stb-hal/libraspi/hardware_caps.c`

Häufige Felder:

- `has_CI`, `has_HDMI`, `has_SCART`, `can_cec`, `can_shutdown`
- `display_type`, `display_xres`, `display_yres`, display flags
- `boxmodel`, `boxvendor`, `boxname`, `boxarch`

Woher Werte kommen:

- `/proc/stb/info/*` für boxtype/model Info
- Maschinen-Dokus oder OEM-Datenblätter (Display-Res, CI-Slots, HDMI)
- Ähnliche Modelle in `hardware_caps.c` (gleicher SoC/Brand)
- Device-Nodes (`/dev/dvb/*`, `/dev/fb*`) und Frontpanel-Treiber

Tipp für Einsteiger: Starte mit einem ähnlichen Modell und verifiziere dann
auf echter Hardware. Falsche Caps können Features verstecken oder falsche
Code-Pfade triggern.

## BOXMODEL-Verzweigungen in Neutrino reduzieren

libstb-hal wurde entwickelt, um Hardware-Spezifika zu isolieren, damit Neutrino
möglichst frei von `#if BOXMODEL_*` und `HAVE_*_HARDWARE` bleibt. In der
Praxis gibt es noch Compile-Time Checks in Neutrino und Treibern (Device-Paths,
Display-Typen, PIP-Gating, Frontpanel-Handling). Das macht Bring-up schwerer
und führt zu Build-time Verhalten statt Runtime-Caps.

Zielzustand: Boxmodel-Wissen in libstb-hal halten, Neutrino nutzt
`g_info.hw_caps` oder HAL-Helper-APIs. Wenn eine box-spezifische Regel nötig
ist, erweitere `hw_caps_t` oder füge einen kleinen HAL-Accessor hinzu, dann
ersetze `#if BOXMODEL_*` durch eine Runtime-Abfrage.

Praktische Schritte:

1) `#if BOXMODEL_*` Blöcke in Neutrino finden (Core + `src/driver/`).
2) Entscheiden, welche Cap oder welches Device-Detail in `hw_caps_t` fehlt.
3) Feld in `hardware_caps.h` hinzufügen und pro boxmodel in `libarmbox/`
   oder `libmipsbox/` setzen.
4) Compile-Time Branch durch Runtime-Check ersetzen (Caps oder Helper).
5) Compile-Time Branching nur für echte boxtype Backends behalten, nicht für UI-Logik.

Wenn du neu bist, kannst du diesen Refactor später machen und zuerst die
fehlenden Caps ergänzen.

## Beispiel: Neues Boxmodel hinzufügen

Beispiel: `gb800solo` (MIPS) ist in OE-A definiert, aber nicht in `libstb-hal`.
Nutze `gb800se` als Startpunkt und passe echte Hardware-Werte an.

1) boxmodel zu `library-stb-hal/acinclude.m4` hinzufügen:

```m4
AS_HELP_STRING([], [valid for mipsbox: vuduo, vuduo2, gb800se, gb800solo, osnino, osninoplus, osninopro]),
...
AM_CONDITIONAL(BOXMODEL_GB800SOLO, test "$BOXMODEL" = "gb800solo")
...
elif test "$BOXMODEL" = "gb800solo"; then
    AC_DEFINE(BOXMODEL_GB800SOLO, 1, [gb800solo])
```

2) Hardware Caps in `library-stb-hal/libmipsbox/hardware_caps.c` setzen:

```c
#if BOXMODEL_GB800SOLO
    caps.has_CI = 1; /* verify */
    caps.can_cec = 0; /* verify */
    caps.can_shutdown = 1;
    caps.display_type = HW_DISPLAY_LINE_TEXT; /* or LED, verify */
    caps.display_xres = 16;
    caps.display_can_deepstandby = 1;
    caps.display_can_set_brightness = 1;
    caps.has_HDMI = 1;
    caps.has_SCART = 1; /* verify */
    strcpy(caps.startup_file, "");
    strcpy(caps.boxmodel, "gb800solo");
    strcpy(caps.boxvendor, "GigaBlue");
    strcpy(caps.boxname, "GB800 SOLO");
    strcpy(caps.boxarch, "BCM7325"); /* verify */
#endif
```

3) Bauen und testen:

```bash
bitbake libstb-hal -c compile
bitbake neutrino
bitbake tuxbox-image
```

Wenn es bootet, HDMI, Audio, Demux, PIP, Frontpanel und Standby prüfen.

## Workflow: Neue Maschine hinzufügen

Wenn eine Maschine in `meta-brands` fehlt, dort zuerst anlegen und dann
"Vorhandene Maschine" Schritte nutzen:

1) `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf` anlegen.
2) `SOC_FAMILY`, `TUNE_FEATURES`, `KERNEL_IMAGETYPE`, `KERNEL_DEVICETREE`,
   `IMAGE_FSTYPES`, `SERIAL_CONSOLE`, `MACHINE_FEATURES` setzen.
3) `linux-<brand>_<ver>.bb` und defconfig/DTB im gleichen Layer pflegen.
4) Kernel/Driver Bring-up prüfen (`/dev/dvb/*`, `/proc/stb/info/*`).
5) Danach Integrationsschritte oben durchführen.

## Prüfliste

- `configure` akzeptiert `--with-boxtype` und `--with-boxmodel`
- `libstb-hal` baut und installiert Headers nach `STAGING_INCDIR/libstb-hal`
- Neutrino linkt und startet
- `caps` Werte passen zur Hardware (Display, HDMI, CI, PIP)
- Image bootet und Basisfunktionen laufen

## Beiträge Upstream

Neue Hardware-Aktivierung ist auf mehrere Upstreams verteilt:

- **libstb-hal**: boxmodel + Backend-Anpassungen im gewählten Repo.
- **OE-Alliance meta-brands**: Maschinen-Config, Kernel/Bootloader, DTBs.
- **Dieses Repo**: Submodule-Pointer nach Upstream-Änderungen aktualisieren.
