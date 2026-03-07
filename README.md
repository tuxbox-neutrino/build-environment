# Tuxbox-OS Builder

Deutsch: [README.de.md](README.de.md)

Build Tuxbox-Neutrino images with a Yocto/OpenEmbedded based workflow.
This repository is the orchestrator around pinned layer submodules.
Default commands are safe and reproducible.

## Start Here (First Build)

If you want the fastest path, copy/paste this block:

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
make check
make update
make image MACHINE=hd51 MACHINEBUILD=mutant51
```

What this does:

1. Clones the repository including submodules.
2. Checks host dependencies.
3. Syncs the repository and pinned submodule commits (`make update`, safe default).
4. Builds your first image.

If `make check` reports missing packages, use the dependency section in
[docs/QUICKSTART.md](docs/QUICKSTART.md).

## Daily Workflow (Safe Default)

```bash
# Get latest top-level changes and pinned submodules
make update

# Build image (reuses existing config)
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Optional: clean build artifacts but keep shared caches
make clean
```

Useful variants:

```bash
# Same safe behavior as make update
make sync

# Skip large submodules when syncing
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

## Choose A Machine

```bash
make list-machines
make machine-info MACHINE=hd51
```

For many devices `MACHINEBUILD` equals `MACHINE`.
Use `make machine-info` to confirm machine-specific values.

## Where Build Outputs Appear

Default image output paths are:

- `builds/build/tmp/deploy/images/<machine>/`
- `build/build/tmp/deploy/images/<machine>/`

Example for `hd51`:

- `builds/build/tmp/deploy/images/hd51/`

## Updating: Users Vs Developers

### For users: `make update` (safe default)

```bash
make update
```

This checks out the **pinned submodule commits** that have been tested together.
Your build is reproducible and will not break unexpectedly. Always use this
unless you know what you are doing.

### For developers: `make update-upstream`

```bash
make update-upstream
```

This moves all submodules to the **latest commit** on their tracking branch
(e.g. `kirkstone`, `5.1`). The code is still on the same Yocto release, but
you get the newest patches and changes from upstream. **This can break your
build** because the combination has not been tested yet.

After `update-upstream`, test your build. If everything works, pin the new
state for other users:

```bash
git add poky oe-alliance meta-openembedded meta-neutrino meta-tuxbox
git commit -m "chore (deps): pin submodules to latest kirkstone/5.1"
```

**Important for developers:**
- If you find a bug or want to propose a change, please open an
  [Issue](https://github.com/tuxbox-neutrino/build-environment/issues) or
  submit a [Pull Request](https://github.com/tuxbox-neutrino/build-environment/pulls).
- Do not push untested submodule pins to `master`.

If you ran `update-upstream` by mistake, return to the safe pinned state:

```bash
make update
```

## Experimental: Toaster Frontend

Toaster support is available, but currently marked experimental and not part of
the default recommended workflow.

Use the dedicated guide:

- [Toaster (Experimental)](docs/TOASTER_EXPERIMENTAL.md)

Import an existing local build directory into Toaster:

```bash
make toaster-import-build
```

Defaults:
- `TOASTER_IMPORT_NAME=$(DISTRO)-build`
- `TOASTER_IMPORT_PATH=$(TOASTER_BUILD_DIR)`

## Documentation Map

Read in this order:

1. [Detailed Quickstart](docs/QUICKSTART.md)
2. [Layers and Submodules](docs/SUBMODULES.md)
3. [Glossary (Yocto/OE terms)](docs/GLOSSARY.md)

Then continue with topic docs:

- [Architecture](docs/ARCHITECTURE.md)
- [QEMU usage](docs/QEMU.md)
- [Hardware integration](docs/HARDWARE_INTEGRATION.md)
- [Image version contract](docs/IMAGE_VERSION_CONTRACT.md)
- [Toaster (Experimental)](docs/TOASTER_EXPERIMENTAL.md)

## Need The German Version?

- [README.de.md](README.de.md)
- [QUICKSTART (DE)](docs/de/QUICKSTART.md)
- [SUBMODULES (DE)](docs/de/SUBMODULES.md)
- [GLOSSARY (DE)](docs/de/GLOSSARY.md)
- [IMAGE VERSION CONTRACT (DE)](docs/de/IMAGE_VERSION_CONTRACT.md)
- [TOASTER (DE, Experimental)](docs/de/TOASTER_EXPERIMENTAL.md)
