# QEMU Smoke Tests (qemux86-64)

This guide covers the QEMU-only smoke test workflow. It is intended for
development and CI, not for production images.

## Scope

- Current target: `qemux86-64` only.
- Image: `tuxbox-qemu-image` (minimal, no Neutrino/multimedia stack).

## Build

If your `build/conf` already targets another machine, either regenerate config
or use a separate build dir.

Option A (reuse `build/`):

```bash
make config MACHINE=qemux86-64
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
```

Option B (separate build dir):

```bash
./cli.py config --machine qemux86-64 --builddir build-qemu
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image --builddir build-qemu
BUILD_DIR=build-qemu ./scripts/qemu/run-qemu.sh nographic slirp
```

## Run QEMU

```bash
./scripts/qemu/run-qemu.sh nographic slirp
```

Notes:
- Uses user networking (slirp). SSH is forwarded to `127.0.0.1:2222`.
- If `2222` is busy, runqemu shifts the port; use `SSH_PORT=...` in tests.

### SSH Login

```bash
ssh -p 2222 root@127.0.0.1
```

The root password is empty unless you set `ROOTPW` at build time.

## Webmin

In QEMU images, Webmin listens on port `10001` to avoid conflicts with a host
Webmin instance. If you want host access with slirp, add a port forward or use
SSH tunneling.

## Smoke Tests

```bash
./scripts/qemu/smoke-test.sh
```

Useful environment variables:
- `SHUTDOWN=0` keep QEMU running after tests.
- `SKIP_PING=1` skip ping checks.
- `REQUIRED_UNITS=...` override systemd units to check.
- `EXPECTED_FAILED_UNITS=...` override allowed failed units.
- `FAIL_ON_UNEXPECTED_FAILED_UNITS=1` fail on extra failed units.
- `SSH_PORT=...` if runqemu shifted the port.

Logs are written to `build/qemu-logs/`.

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

## Troubleshooting

- QEMU window stays black: use `nographic` and check
  `build/qemu-logs/runqemu-*.log`.
- SSH refused early: wait 20-60s for boot/sshd.
- `base-feeds.conf` missing: ensure `tuxbox-feed-config` is installed and
  rebuild the image.
