# Image Portal Beginner Guide

This guide is for users without Yocto/OE background.

Goal:

1. Take your built image artifacts from `build/build/...`.
2. Create a clean portal feed + `catalog.json`.
3. Start a local web/API service.
4. Open the landing page and API in your browser.

## 1. Prerequisites

- Repository path: `/home/tg/sources/tuxbox-os-builder`
- Online update service repo path: `/home/tg/sources/online-update`
- A completed image build for your machine (example: `hd60`)

## 2. Build portal feed from deploy artifacts

Run this in the builder repo:

```bash
cd /home/tg/sources/tuxbox-os-builder

make portal-catalog \
  MACHINE=hd60 \
  SOURCE_DIR=/home/tg/sources/tuxbox-os-builder/build/build/tmp-hd60/deploy/images/hd60 \
  PORTAL_FEED_ROOT=/tmp/tuxbox-feed \
  PORTAL_CATALOG_OUT=/tmp/tuxbox-feed/catalog.json \
  PORTAL_ARTIFACT_BASE_URL=http://127.0.0.1:18091 \
  PORTAL_ONLINE_UPDATE_REPO=/home/tg/sources/online-update
```

What this creates:

- `/tmp/tuxbox-feed/nightly/hd60/<build_date>/...`
- `/tmp/tuxbox-feed/catalog.json`

## 3. Start static feed server

This serves the real artifact files:

```bash
cd /tmp/tuxbox-feed
python3 -m http.server 18091
```

Keep this terminal open.

## 4. Start API + landing page server

Open a second terminal:

```bash
cd /home/tg/sources/online-update

ONLINE_UPDATE_CATALOG=/tmp/tuxbox-feed/catalog.json \
ONLINE_UPDATE_ARTIFACT_BASE_URL=http://127.0.0.1:18091 \
ONLINE_UPDATE_PORTAL_BASE_URL=http://127.0.0.1:18090 \
php -S 127.0.0.1:18090 -t public
```

## 5. Open in browser

- Landing page: `http://127.0.0.1:18090/`
- Catalog API: `http://127.0.0.1:18090/api/v1/catalog.php`
- Latest API: `http://127.0.0.1:18090/api/v1/latest.php?channel=nightly&imagedir=hd60`
- Legacy check: `http://127.0.0.1:18090/legacy/update.php?boxname=hd60&image_type=nightly`

## 6. Point Neutrino to this service

On your test box, set:

- `image_update_url=http://<host-ip>:18091/nightly/hd60`
- `image_manifest_file=manifest.json`
- optional `image_discovery_api_url=http://<host-ip>:18090/api/v1`

Use your real host LAN IP instead of `127.0.0.1`.

## Troubleshooting

- If browser shows nothing on `:18090`, check if PHP server is still running.
- If API returns `catalog unavailable`, verify `ONLINE_UPDATE_CATALOG` path.
- If download redirects fail, verify static server on `:18091`.
- If Neutrino box cannot reach host, use host LAN IP and open firewall.
