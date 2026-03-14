# Lua Plugin Extraction Workflow (Monorepo -> Standalone Repo)

This is the standard workflow to extract one plugin from
`https://github.com/tuxbox-neutrino/plugin-scripts-lua` into a dedicated repo
with full history and normalized author/committer identities.

## 1) Prepare variables

```bash
PLUGIN_NAME="logoupdater"
SOURCE_REPO="https://github.com/tuxbox-neutrino/plugin-scripts-lua.git"
TARGET_REPO="git@github.com:tuxbox-neutrino/plugin-lua-${PLUGIN_NAME}.git"
MAILMAP="/home/tg/sources/neutrino/.mailmap"
WORKROOT="$HOME/sources/.tmp-plugin-extract"
WORKDIR="$WORKROOT/plugin-lua-${PLUGIN_NAME}-work-$(date +%Y%m%d%H%M%S)"
```

## 2) Clone source and extract full plugin history

```bash
mkdir -p "$WORKROOT"
git clone "$SOURCE_REPO" "$WORKDIR"
cd "$WORKDIR"

git filter-repo --force \
  --path "plugins/${PLUGIN_NAME}/" \
  --path-rename "plugins/${PLUGIN_NAME}/:plugin/" \
  --mailmap "$MAILMAP"
```

Notes:
- `--path` + `--path-rename` keeps only the plugin path and moves it to `plugin/`.
- `--mailmap` normalizes historical author/committer data.

## 3) Add standalone repo scaffolding

Add/update:
- `.gitignore` (`dist/`)
- `LICENSE`
- `README.md`
- `Makefile` (optional local install helper)
- `metadata.json`
- Any plugin assets needed for self-contained builds (for example `plugin/<name>.png`).

## 4) Apply required plugin fixes directly upstream

- Move any layer patch fixes into `plugin/<name>.lua` in the new repo.
- Commit with conventional commits.

## 5) Push new standalone upstream repo

```bash
git remote add origin "$TARGET_REPO"
git push -u origin master
```

## 6) Migrate recipe in `meta-neutrino`

For `<name>_git.bb`:
- set `SRC_URI` to the new standalone repo
- pin `SRCREV`
- set `MIGIT_ENABLED = "0"`
- set `S = "${WORKDIR}/git"`
- use `LICENSE` / `LIC_FILES_CHKSUM` from the standalone repo
- keep runtime `RDEPENDS` / `RRECOMMENDS`
- if needed, set `PE` to avoid feed version rollback after migration
- remove now-obsolete layer patches/files

## 7) Validate

Build:

```bash
make bb-<name>
```

Box smoke test:
- install the new IPK
- `reloadplugins`
- `startplugin?name=<name>`
- verify expected runtime behavior and required files

## 8) Push sequence

1. Push `meta-neutrino/master`.
2. Update orchestrator submodule pointer.
3. Push orchestrator `master`.

This keeps upstream layer changes and orchestrator pin updates cleanly separated.
