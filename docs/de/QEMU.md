# QEMU Smoke-Tests (qemux86-64)

Dieses Dokument beschreibt den QEMU-Workflow für Smoke-Tests. Es ist für
Entwicklung und CI gedacht, nicht für produktive Images.

## Umfang

- Aktuelles Target: nur `qemux86-64`.
- Image: `tuxbox-qemu-image` (inklusive Neutrino + X11 für GUI-Tests).

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
BUILD_DIR=build-qemu ./scripts/qemu/run-qemu.sh nographic slirp
```

## QEMU starten

GUI (empfohlen für Neutrino):

```bash
./scripts/qemu/run-qemu.sh slirp
```

Headless (keine sichtbare Neutrino-GUI):

```bash
./scripts/qemu/run-qemu.sh nographic slirp
```

Hinweise:
- User-Networking (slirp). SSH ist auf `127.0.0.1:2222` weitergeleitet.
- Wenn `2222` belegt ist, verschiebt runqemu den Port; `SSH_PORT=...` nutzen.
- Neutrino startet in der GUI-Variante automatisch auf dem QEMU-Display.
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
make qemu-run QEMU_ARGS="nographic slirp"
SSH_PORT=2223 make qemu-smoke
```

### SSH Login

```bash
ssh -p 2222 root@127.0.0.1
```

Das Root-Passwort ist leer, außer du setzt `ROOTPW` beim Build.

Hinweise:
- SSH-Host-Keys bleiben über Reboots erhalten, wenn das Rootfs beschreibbar ist.
- Wenn QEMU mit `snapshot` oder einem tmpfs-Rootfs läuft, werden die Host-Keys
  bei jedem Boot neu erzeugt und der Fingerprint ändert sich.

## Webmin

In QEMU-Images lauscht Webmin auf Port `10001`, damit es keinen Konflikt mit
Webmin auf dem Host gibt. Für Zugriff vom Host mit slirp Port-Forwarding
einrichten oder SSH-Tunneling verwenden.

## Smoke-Tests

```bash
./scripts/qemu/smoke-test.sh
```

Nützliche Variablen:
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
- SSH wird zuerst abgelehnt: 20-60s auf Boot/sshd warten.
- `base-feeds.conf` fehlt: prüfen, ob `tuxbox-feed-config` installiert ist,
  dann Image neu bauen.
