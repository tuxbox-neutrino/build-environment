# QEMU Smoke Tests (qemux86-64)

This guide covers the QEMU-only smoke test workflow. It is intended for
development and CI, not for production images.

## Scope

- Current target: `qemux86-64` only.
- Image: `tuxbox-qemu-image` (includes Neutrino + X11 for GUI testing).

## Build

If your `builds/conf` already targets another machine, either regenerate config
or use a separate build dir.

Option A (reuse `builds/`):

```bash
make config MACHINE=qemux86-64
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
```

Option B (separate build dir):

```bash
./cli.py config --machine qemux86-64 --builddir build-qemu
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image --builddir build-qemu
BUILD_DIR=build-qemu ./scripts/qemu/run-qemu.sh nographic
```

## Run QEMU

GUI (recommended for Neutrino):

```bash
./scripts/qemu/run-qemu.sh
```

Headless (no visible Neutrino UI):

```bash
./scripts/qemu/run-qemu.sh nographic
```

Notes:
- Default network mode is automatic:
  - `bridge=br0` when `br0` exists on the host.
  - otherwise `slirp` fallback.
- In `slirp` mode, SSH is forwarded to `127.0.0.1:2222`.
- If `2222` is busy, runqemu shifts the port; use `SSH_PORT=...` in tests.
- Neutrino starts automatically on the QEMU display in GUI mode.
- `tuxbox-qemu-image` disables autostart of `neutrino.service`; Neutrino is
  started by `tuxbox-qemu-neutrino.service` only.
- Maintainer detail: `systemd_preset_all` in `do_image` can re-enable
  `neutrino.service`; the QEMU image removes that symlink again in image
  preprocess.
- Bluetooth power-on is skipped in VMs to avoid boot delays; test Bluetooth on
  real hardware.

## Makefile Shortcuts

```bash
make qemu-run
make qemu-smoke
```

Common overrides:

```bash
make qemu-run QEMU_BUILD_DIR=build-qemu
make qemu-run QEMU_ARGS="slirp"
make qemu-run QEMU_ARGS="nographic bridge=br0"
SSH_PORT=2223 make qemu-smoke
```

### SSH Login

In `slirp` mode:

```bash
ssh -p 2222 root@127.0.0.1
```

In `bridge` mode:

```bash
ssh root@<guest-ip-or-hostname>
```

The root password is empty unless you set `ROOTPW` at build time.

Notes:
- SSH host keys persist across reboots when the rootfs is writable.
- If you run QEMU with `snapshot` or a tmpfs rootfs, host keys are regenerated
  on every boot and the fingerprint changes.

## Webmin

In QEMU images, Webmin listens on port `10001` to avoid conflicts with a host
Webmin instance.

- In `bridge` mode: open `http://<guest-ip>:10001` directly.
- In `slirp` mode: use SSH tunneling:

```bash
ssh -p 2222 -N -L 10001:127.0.0.1:10001 root@127.0.0.1
```

Then open `http://127.0.0.1:10001`.

## Smoke Tests

```bash
./scripts/qemu/smoke-test.sh
```

Useful environment variables:
- `SHUTDOWN=1` (default) powers off the guest after checks.
- `SHUTDOWN=0` keep QEMU running after tests.
- `SKIP_PING=1` skip ping checks.
- `REQUIRED_UNITS=...` override systemd units to check.
- `EXPECTED_FAILED_UNITS=...` override allowed failed units.
- `FAIL_ON_UNEXPECTED_FAILED_UNITS=1` fail on extra failed units.
- `SSH_PORT=...` if runqemu shifted the port.

Logs are written to `builds/qemu-logs/`.

Expected failed units in QEMU (default): none.
If you see failed units, treat them as regressions to investigate.

## opkg Feeds

`tuxbox-feed-config` generates `/etc/opkg/base-feeds.conf` when
`IPK_FEED_SERVER` or `FEED_DEPLOYDIR_BASE_URI` is set at build time.

Example (host HTTP server pointing at build deploy dir):

```conf
IPK_FEED_SERVER = "http://192.168.1.202:33333/tmp-${MACHINE}/deploy/ipk"
```

Then inside QEMU:

```bash
opkg update
opkg install <pkg>
```

## Rootfs Size (opkg Testing)

The QEMU image ships with extra rootfs space so you can install larger
packages (e.g. Neutrino) during testing. If you still hit `No space left
on device`, increase the extra space in your local config:

```conf
TUXBOX_QEMU_ROOTFS_EXTRA_SPACE = "2097152"
```

Value is in KB (the example adds ~2 GB).

## Troubleshooting

- QEMU window stays black: use `nographic` and check
  `builds/qemu-logs/runqemu-*.log`.
- Bridge mode fails early: retry with `QEMU_ARGS="slirp"` and check host bridge
  setup/permissions.
- SSH refused early: wait 20-60s for boot/sshd.
- `base-feeds.conf` missing: ensure `tuxbox-feed-config` is installed and
  rebuild the image.
