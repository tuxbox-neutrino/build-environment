# QEMU Smoke-Tests (qemux86-64)

English: [../QEMU.md](../QEMU.md)

Dieses Dokument beschreibt den QEMU-Workflow für Smoke-Tests. Es ist für
Entwicklung und CI gedacht, nicht für produktive Images.

Kurze Begriffsdefinitionen findest du im [GLOSSARY.md](GLOSSARY.md).

## Umfang

- Aktuelles Target: nur `qemux86-64`.
- Image: `tuxbox-qemu-image` (inklusive Neutrino + X11 für GUI-Tests).

## Referenz-Policy

- QEMU dient als primäre Vorab-Referenz für Workflows der realen Boxen.
- Für möglichst hohe Praxisnähe `bridge` bevorzugen (`bridge=br0`, falls verfügbar).
- Paket-Install/Update-Flows und Service-Start zuerst in QEMU validieren, dann
  auf realer Hardware testen.
- Hardware-spezifische Unterschiede (Tuner, CI, Vendor-Treiber, HDMI-CEC) sind
  erwartbar und müssen auf echter Box verifiziert werden.

## Build

Wenn `builds/conf` bereits auf eine andere Maschine zeigt, entweder neu
generieren oder ein separates Build-Verzeichnis nutzen.

Option A (Build in `builds/`):

```bash
make config MACHINE=qemux86-64
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
```

Option B (separates Build-Verzeichnis):

```bash
./cli.py config --machine qemux86-64 --builddir build-qemu
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image --builddir build-qemu
BUILD_DIR=build-qemu ./scripts/qemu/run-qemu.sh nographic
```

## QEMU starten

GUI (empfohlen für Neutrino):

```bash
./scripts/qemu/run-qemu.sh
```

Headless (keine sichtbare Neutrino-GUI):

```bash
./scripts/qemu/run-qemu.sh nographic
```

Hinweise:
- Standard-Netzwerkmodus ist automatisch:
  - `bridge=br0`, wenn `br0` auf dem Host existiert.
  - sonst Fallback auf `slirp`.
- Im `slirp`-Modus ist SSH auf `127.0.0.1:2222` weitergeleitet.
- Wenn `2222` belegt ist, verschiebt runqemu den Port; `SSH_PORT=...` nutzen.
- Neutrino startet in der GUI-Variante automatisch auf dem QEMU-Display.
- `tuxbox-qemu-image` deaktiviert den Autostart von `neutrino.service`;
  Neutrino wird nur über `tuxbox-qemu-neutrino.service` gestartet.
- Maintainer-Detail: `systemd_preset_all` in `do_image` kann
  `neutrino.service` wieder aktivieren; das QEMU-Image entfernt den Symlink
  danach erneut im Image-Preprocess.
- Bluetooth-Power-On wird in VMs übersprungen, um Boot-Delays zu vermeiden;
  Bluetooth bitte auf echter Hardware testen.

## Makefile-Shortcuts

```bash
make qemu-run
make qemu-smoke
```

Häufige Overrides:

```bash
make qemu-run QEMU_BUILD_DIR=build-qemu
make qemu-run QEMU_ARGS="slirp"
make qemu-run QEMU_ARGS="nographic bridge=br0"
SSH_PORT=2223 make qemu-smoke
```

### SSH Login

Im `slirp`-Modus:

```bash
ssh -p 2222 root@127.0.0.1
```

Im `bridge`-Modus:

```bash
ssh root@<guest-ip-oder-hostname>
```

Das Root-Passwort ist leer, außer du setzt `ROOTPW` beim Build.

Hinweise:
- SSH-Host-Keys bleiben über Reboots erhalten, wenn das Rootfs beschreibbar ist.
- Wenn QEMU mit `snapshot` oder einem tmpfs-Rootfs läuft, werden die Host-Keys
  bei jedem Boot neu erzeugt und der Fingerprint ändert sich.

## Webmin

In QEMU-Images lauscht Webmin auf Port `10001`, damit es keinen Konflikt mit
Webmin auf dem Host gibt.

- Im `bridge`-Modus: direkt `http://<guest-ip>:10001` öffnen.
- Im `slirp`-Modus: SSH-Tunnel nutzen:

```bash
ssh -p 2222 -N -L 10001:127.0.0.1:10001 root@127.0.0.1
```

Danach `http://127.0.0.1:10001` öffnen.

## Smoke-Tests

```bash
./scripts/qemu/smoke-test.sh
```

Nützliche Variablen:
- `SHUTDOWN=1` (Default) fährt den Guest nach den Checks herunter.
- `SHUTDOWN=0` QEMU nach dem Test weiterlaufen lassen.
- `SKIP_PING=1` Ping-Checks überspringen.
- `REQUIRED_UNITS=...` systemd-Units überschreiben.
- `EXPECTED_FAILED_UNITS=...` erlaubte failed Units überschreiben.
- `FAIL_ON_UNEXPECTED_FAILED_UNITS=1` bei zusätzlichen failed Units abbrechen.
- `SSH_PORT=...` falls runqemu den Port verschoben hat.

Logs liegen unter `builds/qemu-logs/`.

Erwartete failed Units in QEMU (default): keine.
Falls failed Units auftreten, bitte als Regression ansehen und prüfen.

## opkg Feeds

`tuxbox-feed-config` erzeugt `/etc/opkg/base-feeds.conf`, wenn
`IPK_FEED_SERVER` oder `FEED_DEPLOYDIR_BASE_URI` beim Build gesetzt ist.

Beispiel (HTTP-Server zeigt auf deploy-Verzeichnis):

```conf
IPK_FEED_SERVER = "http://192.168.1.202:33333/tmp-${MACHINE}/deploy/ipk"
```

Dann in QEMU:

```bash
opkg update
opkg install <paket>
```

## Rootfs-Größe (opkg-Tests)

Das QEMU-Image enthält zusätzlichen Rootfs-Platz, damit größere Pakete
(z. B. Neutrino) installiert werden können. Falls dennoch `No space left
on device` erscheint, erhöhe den Wert in deiner lokalen Konfiguration:

```conf
TUXBOX_QEMU_ROOTFS_EXTRA_SPACE = "2097152"
```

Wert in KB (Beispiel: ~2 GB zusätzlich).

## Troubleshooting

- QEMU bleibt schwarz: `nographic` verwenden und
  `builds/qemu-logs/runqemu-*.log` prüfen.
- Bridge-Modus bricht früh ab: mit `QEMU_ARGS="slirp"` testen und Host-Bridge
  bzw. Berechtigungen prüfen.
- SSH wird zuerst abgelehnt: 20-60s auf Boot/sshd warten.
- `base-feeds.conf` fehlt: prüfen, ob `tuxbox-feed-config` installiert ist,
  dann Image neu bauen.
