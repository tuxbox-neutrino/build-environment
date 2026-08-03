# Image Portal Beginner Guide

Deutsch: [de/IMAGE_PORTAL_BEGINNER_GUIDE.md](de/IMAGE_PORTAL_BEGINNER_GUIDE.md)

This guide is for users without Yocto/OE background.

There are three different things:

- **IPK feed**: package feed for `opkg`, served locally on port `33333`.
- **Local image server**: image files for Neutrino Online Flash, served through
  the real `online-update` PHP service on port `33334`.
- **Portal sync**: production workflow that copies the staged image feed to a
  real web server.

For local Online Flash tests, use the local image server. Do not start a
separate static file server by hand.

## 1. Prerequisites

- Builder repo: `/home/tg/sources/tuxbox-os-builder`
- Online update service repo: `/home/tg/sources/online-update`
- A completed image build for your machine

Example machines:

- `MACHINE=h7 MACHINEBUILD=zgemmah7`
- `MACHINE=hd51 MACHINEBUILD=mutant51`
- `MACHINE=hd60 MACHINEBUILD=mutant60`

## 2. Build An Image

Run this in the builder repo:

```bash
cd /home/tg/sources/tuxbox-os-builder
make image MACHINE=h7 MACHINEBUILD=zgemmah7
```

At the end of the build the builder prints the image deploy path and a hint
for `make image-server-start`.

## 3. Start The Local Image Server

```bash
make image-server-start MACHINE=h7 MACHINEBUILD=zgemmah7
```

This command does two things:

1. It stages the latest image into `portal-feed/` and builds `catalog.json`.
2. It starts the PHP service from `online-update` on port `33334`.

The service uses the real `/feed/<channel>/<imagedir>/...` path. That means
manifest lookup, service-key handling, and Range downloads are tested through
the same code path that Neutrino uses.

## 4. Check The Neutrino Values

```bash
make image-server-url MACHINE=h7 MACHINEBUILD=zgemmah7
```

Example output:

```text
image_update_url=http://192.168.1.36:33334/feed/release/zgemmah7
image_manifest_file=manifest.json
image_service_key=<generated key>

manifest: http://192.168.1.36:33334/feed/release/zgemmah7/manifest.json
curl: curl -H 'X-Tuxbox-Service-Key: <generated key>' '...'
logs: .../image-server/logs
admin webif: http://192.168.1.36:33334/admin/
```

For new local builds, `make config`/`make image` writes the same local image
base URL **and the service key** into
`builds/<machine>/conf/local-image-server.inc`, so the generated
`/etc/image-version` already points to the local image server on port `33334`
and carries a key the server accepts. Use the first block to verify those
values, or copy them as manual fallback when you test an older image.

The key is generated once and stored in `image-server/service-key`;
`make image-server-key` prints it and `make image-server-key KEY=…` sets your
own (a `TUXBOX_SERVICE_KEY` assignment in your conf files wins — the builder
follows it). **Why was my key rejected?** The old example value
`LOCAL_SERVICE_KEY` and X-only placeholders never authenticate; a box flashed
from an older image sends exactly those. Either set
`image_service_key=<generated key>` in `/etc/image-version` on the box
(Neutrino re-reads the file whenever "Online update" starts) or rebuild after
`make config`. Use proper service keys on public servers.

The `admin webif` line is for operators only: open it in a browser to reach
the server administration UI. Neutrino does not read this URL and it is not
part of the Flash download path.

On first login use the user `admin` with the generated initial password from
the server log (also stored in `initial-admin-password` next to `users.json`
until the forced first change); `IMAGE_PORTAL_ADMIN_BOOTSTRAP_PASSWORD` pins
it for local setups. The admin state is stored under
`image-server/run/admin/`. Delete `image-server/run/admin/users.json` to
start the bootstrap again.

## 5. Quick Host Test

Use the `curl` line printed by `make image-server-url`, for example:

```bash
curl -H "X-Tuxbox-Service-Key: $(make -s image-server-key)" \
  'http://192.168.1.36:33334/feed/release/zgemmah7/manifest.json'
```

The response should be a JSON manifest. Server logs are in:

```text
image-server/logs/
```

## 6. Stop The Local Server

```bash
make image-server-stop
```

This stops only the local image server on port `33334`. It does not stop the
IPK feed server on port `33333`.

## Production Portal Sync

For a real web server, keep using the technical `portal-*` workflow:

```bash
make portal-catalog MACHINE=h7 MACHINEBUILD=zgemmah7 \
  PORTAL_ARTIFACT_BASE_URL=https://images.example.org/feed

make portal-sync \
  PORTAL_SYNC_DEST=user@host:/srv/tuxbox/feed \
  PORTAL_SYNC_DRYRUN=0
```

Use `make portal-sync` only when you really want to copy the staged feed to a
server. Local Online Flash tests should use `image-server-start`.

## Troubleshooting

- If Neutrino cannot reach the server, use the host LAN IP, not `127.0.0.1`,
  and open TCP port `33334` in the firewall.
- If `make image-server-start` says `missing manifest`, rebuild the image with
  the current builder state.
- If the service returns `401`, `403`, or `429`, check the service key:
  `make image-server-key` prints the accepted value. `LOCAL_SERVICE_KEY` and
  X-only placeholders are always rejected.
- If downloads fail but the manifest works, check `image-server/logs/php-server.log`.
