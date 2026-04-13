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
If you want short definitions for terms like submodule/pinning, see the
[Glossary](GLOSSARY.md).

Repository policy note:
- `build-environment` itself is intended to use only the official `master`
  branch on the remote.
- This does not change the existing branch workflow of layer repos such as
  `meta-neutrino` or `meta-tuxbox`.
- It also does not change the behavior of `make update` / `make up` and
  `make update-upstream` / `make up-upstream`: those continue to use the
  pinned submodule commits or the tracking branches from `.gitmodules`.

## Contents

- [1. Clone with submodules](#1-clone-with-submodules)
- [2. SSH for private submodules](#2-ssh-for-private-submodules)
- [3. Fix empty layer folders](#3-fix-empty-layer-folders)
- [4. Update to the recorded (safe) versions](#4-update-to-the-recorded-safe-versions)
- [5. make update vs make update-upstream (important)](#5-make-update-vs-make-update-upstream-important)
- [6. Align layer repos and submodule pointers (advanced)](#6-align-layer-repos-and-submodule-pointers-advanced)
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

Use this for normal work. It updates the top-level repo and checks out the exact
pinned submodule commits recorded by the builder:

```bash
make update
# Equivalent:
make sync
# Or, raw git (no top-level pull):
git submodule sync --recursive
git submodule update --init --recursive
```

## 5. make update vs make update-upstream (important)

- `make update`: safe default for daily work (pinned).
- `make sync`: same safe behavior as `make update` (pinned); use this when you
  want `SYNC_EXCLUDE=...`.
- `make update-upstream` / `./cli.py sync`: moves submodules to upstream HEAD
  (as set in `.gitmodules`), leaves the tree dirty unless you commit new
  pointers, and can put layers on branches/REVs that do not match the pinned
  build.
- Current tracking is `master` for `meta-neutrino`/`meta-tuxbox`, `kirkstone`
  for `poky`/`meta-openembedded`, and `5.1` for `oe-alliance`.

If you ran `make update-upstream` by mistake, run `make update` (or `make sync`)
to return to the pinned state.

## 6. Align layer repos and submodule pointers (advanced)

Only do this if you intentionally want to move a layer away from the currently
pinned builder state.

Important:
- The layer commit lives in the layer repo such as `meta-tuxbox`.
- The pinned reference to that layer commit lives in the top-level
  `build-environment` repo.
- For normal daily work, do **not** `git pull` inside submodules manually. Use
  `make update` / `make sync` to return to the recorded pinned state.

Typical flow when you really want to advance a layer:

```bash
# 1. Move the layer repo itself to the desired upstream state.
cd meta-tuxbox
git switch master
git pull --ff-only

# 2. Make and test your layer changes in the layer repo.
git status
# edit files
git commit -am "..."
git push

# 3. Record the new pinned layer commit in the builder repo.
cd ..
git add meta-tuxbox
git commit -m "Update meta-tuxbox submodule pointer"
```

Verification after the pointer update:

```bash
git status
git submodule status
```

Expected result:
- the layer repo contains the actual code commit,
- the top-level repo contains only the submodule pointer update,
- `git submodule status` shows the recorded commit for `meta-tuxbox`.

Repeat the same pattern for `meta-neutrino` if needed.

## 7. Branch and tag policy

- `build-environment`: official remote branch is `master`
- Default branch: `master` (current Yocto line)
- Maintenance branches: `gatesgarth`, `kirkstone`, etc.
- Tags: `<codename>-<yocto_version>` (example: `kirkstone-4.0.12`)

This makes it easy to see which layer version matches a specific Yocto release.

## Related Docs

- [QUICKSTART.md](QUICKSTART.md) - First build steps
- [GLOSSARY.md](GLOSSARY.md) - Short term definitions
- [ARCHITECTURE.md](ARCHITECTURE.md) - System overview
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Add new hardware
- [README.md](../README.md) - Project overview and commands
