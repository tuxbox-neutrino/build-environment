# Layers and Submodules (Beginner Guide)

Deutsch: [de/SUBMODULES.md](de/SUBMODULES.md)

This project keeps the build layers in their own Git repositories:

- `meta-neutrino`
- `meta-tuxbox`
- `oe-alliance`
- `poky`
- `meta-openembedded`

The `build-environment` repo only orchestrates the build.
Submodules let us pin exact versions while keeping each layer independent.

## Contents

- [1. Clone with submodules](#1-clone-with-submodules)
- [2. SSH for private submodules](#2-ssh-for-private-submodules)
- [3. Fix empty layer folders](#3-fix-empty-layer-folders)
- [4. Update to the recorded (safe) versions](#4-update-to-the-recorded-safe-versions)
- [5. make sync vs make update (important)](#5-make-sync-vs-make-update-important)
- [6. Update a layer to the latest upstream (advanced)](#6-update-a-layer-to-the-latest-upstream-advanced)
- [7. Branch and tag policy](#7-branch-and-tag-policy)
- [Related Docs](#related-docs)

## 1. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

## 2. SSH for private submodules

If you have access to private GitHub submodules, use SSH instead of HTTPS:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

If you get repeated passphrase prompts, load your SSH key once:

```bash
ssh-add ~/.ssh/id_rsa
```

## 3. Fix empty layer folders

If a layer folder is empty after clone:

```bash
git submodule update --init --recursive
```

## 4. Update to the recorded (safe) versions

This will update all submodules to the exact commits recorded by the builder:

```bash
make sync
# Or, raw git (no top-level pull):
git submodule sync --recursive
git submodule update --init --recursive
```

## 5. make sync vs make update (important)

- `make sync`: pulls the top-level repo and checks out pinned submodule commits
  (safe for builds).
- `make update` / `./cli.py sync`: moves submodules to upstream HEAD (as set in
  `.gitmodules`), leaves the tree dirty unless you commit new pointers, and can
  put layers on branches/REVs that do not match the pinned build.

If you ran `make update` by mistake, run `make sync` to return to the pinned
state.

## 6. Update a layer to the latest upstream (advanced)

Only do this if you know why you need newer layer commits.

```bash
cd meta-tuxbox
git checkout master
git pull
cd ..
git add meta-tuxbox
git commit -m "Update meta-tuxbox"
```

Repeat for `meta-neutrino` if needed.

## 7. Branch and tag policy

- Default branch: `master` (current Yocto line)
- Maintenance branches: `gatesgarth`, `kirkstone`, etc.
- Tags: `<codename>-<yocto_version>` (example: `kirkstone-4.0.12`)

This makes it easy to see which layer version matches a specific Yocto release.

## Related Docs

- [QUICKSTART.md](QUICKSTART.md) - First build steps
- [ARCHITECTURE.md](ARCHITECTURE.md) - System overview
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Add new hardware
- [README.md](../README.md) - Project overview and commands
