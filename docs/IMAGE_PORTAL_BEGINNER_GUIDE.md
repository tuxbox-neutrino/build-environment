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

## 4. Copy The Neutrino Values

```bash
make image-server-url MACHINE=h7 MACHINEBUILD=zgemmah7
```

Example output:

```text
image_update_url=http://192.168.1.36:33334/feed/release/zgemmah7
image_update_admin_webif_url=http://192.168.1.36:33334/admin/
image_manifest_file=manifest.json
image_service_key=LOCAL_SERVICE_KEY
```

Use these values in Neutrino's Online Flash settings. Replace nothing by hand
unless the host IP is wrong.

`LOCAL_SERVICE_KEY` is only for local/private networks. Use proper service keys
on public servers.

`image_update_admin_webif_url` opens the server administration UI. It is useful
for operators, but it is not part of the Flash download path.

## 5. Quick Host Test

Use the `curl` line printed by `make image-server-url`, for example:

```bash
curl -H 'X-Tuxbox-Service-Key: LOCAL_SERVICE_KEY' \
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
- If the service returns `401`, `403`, or `429`, check the service key. For
  local tests, use `LOCAL_SERVICE_KEY`.
- If downloads fail but the manifest works, check `image-server/logs/php-server.log`.
