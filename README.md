# Tuxbox-OS Builder

Deutsch: [README.de.md](README.de.md)

Production-ready build system for Tuxbox-Neutrino based on OE-Alliance infrastructure.

## Quick Start

### 1. Prerequisites

```bash
# Debian/Ubuntu
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales \
  libacl1 curl
```

For 32-bit targets on a 64-bit host (e.g. armhf machines like HD60/HD61), also
install multilib headers:

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

Tip: Use SSH instead of HTTPS for GitHub submodules (avoid login prompts).

If Git tries to update or clone GitHub repositories/submodules via **HTTPS**
(`https://github.com/...`) it may prompt for credentials (typically a **token**
rather than a password). Switching to **SSH** (`git@github.com:...`) lets Git use
your **SSH key**, which usually avoids repeated prompts and works better for
automated builds/CI.

Rewrite all GitHub HTTPS URLs to SSH (recommended):
This makes Git automatically replace `https://github.com/` with `git@github.com:` for all repositories on your machine:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

Ensure an SSH agent is running:
```bash
eval "$(ssh-agent -s)"
```

Then add your key:
```bash
ssh-add ~/.ssh/id_rsa
```

### 2. Initialize or Update

### 2.1. Clone for 1st Initialize
```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
make init
```

### 2.2. Update and Sync
If you already cloned without submodules or want to resync later (safe/pinned):
```bash
make sync
```

... or, raw git (pinned submodules only, no top-level pull):
```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### 2.3 Sync with Upstreams

Use this only when you intentionally want to move submodules to upstream HEAD
(unpinned):

```bash
make update
# Or
./cli.py sync
```

Warning: `make update` and `./cli.py sync` move submodules to upstream HEAD
(unpinned). This can put layers on branches/REVs that do not match the pinned
build and will leave your working tree dirty unless you commit the new
submodule pointers. Use those only when you intend to update layer pins.
If you run them by mistake, use `make sync` to return to the pinned state:

```bash
make sync
```

### 3. Build an Image

First build: always pass `MACHINE` (and `MACHINEBUILD` if required) or run
`make config` first. `make image` without `MACHINE` only works after a config
already exists.

```bash
# First build (recommended): pass MACHINE (and MACHINEBUILD if needed).
# This auto-generates config if it does not exist yet.
make image MACHINE=hd51 MACHINEBUILD=mutant51

# If a config already exists, you can just run:
make image

# Prepare config only (no build)
make config MACHINE=hd51
make show-config MACHINE=hd51   # shows values + source file
make edit-conf MACHINE=hd51     # opens the include files

# If configs already exist, make image reuses them.
# Force regeneration when needed:
make image MACHINE=hd51 FORCE_CONFIG=1

# OEM/brand variants (use MACHINEBUILD when it differs from MACHINE)
make image MACHINE=hd60 MACHINEBUILD=ax60

# Find valid MACHINEBUILD values
make list-machines
make machine-info MACHINE=hd51

# Or using Python CLI
./cli.py build --machine hd51
MACHINEBUILD=mutant51 ./cli.py build --machine hd51
```

Image target: `tuxbox-image` is the canonical image recipe. Legacy targets
`neutrino-image` and `noneutrino-image` are aliases to the same recipe.

`make show-config` reports where values come from (local.conf vs include
files) and lists layers with their source file.

Built images will be in `build/tmp/deploy/images/<machine>/` (e.g. `hd51/`).

### Neutrino Flavour (tuxbox only)

The main tree supports only the `tuxbox` flavour. If you need a fork (NI/Tango),
use `devtool modify` to work in a local workspace and point `SRC_URI` to your
fork (or move the changes into a private layer).

### Image Metadata Contract

`/etc/image-version` is the canonical flash/update metadata file used by
`flash-script` and STB Lua plugins. Contract and override variables:
`docs/IMAGE_VERSION_CONTRACT.md`.

Flash backend capability is modeled via `TUXBOX_FLASH_BACKEND`
(`script` or `ofgwrite`).

Runtime preflight command from `flash-script`:

```bash
flash-backend-preflight
flash-backend-preflight --backend ofgwrite --image-dir /path/to/unpacked/image
```

Host-side smoke check for the no-write invocation path:

```bash
make flash-preflight-smoke
```

### QEMU Smoke Tests (qemux86-64)

Full guide: [docs/QEMU.md](docs/QEMU.md) (EN) / [docs/de/QEMU.md](docs/de/QEMU.md) (DE).

Quick start:

```bash
./cli.py build --machine qemux86-64 --target tuxbox-qemu-image
./scripts/qemu/run-qemu.sh slirp
./scripts/qemu/smoke-test.sh
```

Makefile shortcuts:

```bash
make qemu-run
make qemu-smoke
```

Examples:

```bash
make qemu-run QEMU_BUILD_DIR=build-qemu
SSH_PORT=2223 make qemu-smoke
```

### STB Lua Plugin Smoke Checks

Run a fast recipe smoke check for `stb-*` Lua plugins (`unpack` + `install`):

```bash
make stb-smoke MACHINE=qemux86-64
```

Useful overrides:

```bash
# Only unpack check
TASKS="unpack" make stb-smoke MACHINE=qemux86-64

# Custom recipe subset
STB_PLUGIN_RECIPES="stb-flash stb-startup" make stb-smoke MACHINE=qemux86-64
```

Flash backend preflight smoke check (mocked `ofgwrite -n` call):

```bash
make flash-preflight-smoke
```

### Persistent Local Overrides (Beginner Friendly)

`make config` generates `local.conf` and `bblayers.conf`. To keep personal changes
across updates, edit these files instead:

- `build/conf/local.conf.user.inc` (your personal defaults)
- `build/conf/local.conf.<machine>.inc` (per-machine tweaks)
- `build/conf/bblayers.conf.user.inc` (extra layers / masks)

These files are created automatically and are never overwritten by regeneration.

By default, `local.conf.<machine>.inc` sets a per-machine TMPDIR:

```
TMPDIR = "${TOPDIR}/build/tmp-${MACHINE}"
```

(Coolstream defaults to `build-${MACHINE}/tmp`.) Edit the file if you want a
single shared TMPDIR.

### Image Naming Overrides (Optional)

`build/conf/local.conf.user.inc` includes a commented template for image naming
variables and examples. Uncomment what you need.

Avoid these pitfalls:
- Do not add spaces to `IMAGE_VER_STRING` (some OA scripts break on spaces).
- Keep `vardepsexclude` when using `DATE`/`DATETIME` to avoid rebuild churn.
- Do not use slashes in `IMAGE_NAME` (must be a filename).
- Do not change `IMAGE_NAME_SUFFIX` unless your tooling expects it.

### Locale Defaults (Optional)

Default images ship only `en-us` to keep footprints small. The QEMU smoke image
keeps multiple locales for convenience. Override per build in
`build/conf/local.conf.user.inc`:

```conf
IMAGE_LINGUAS = "en-us"
```

### WiFi Packages (Optional)

WiFi user-space tools are included by default so USB WiFi sticks can be used
across machines. To disable the WiFi package group per build, set this in
`build/conf/local.conf.user.inc`:

```conf
TUXBOX_WIFI = "0"
```

Firmware packages are included by default as well. Kernel modules come from the
machine kernel (and its modules tarball), so if a stick needs a missing driver
you must enable it in the kernel config. For a minimal image or custom
selection, set `TUXBOX_WIFI = "0"` and add packages explicitly.

### Source Download Mirror (Optional)

You can use the public source mirror for faster downloads. Generated configs
enable it in `build/conf/local.conf.user.inc`. Remove the lines below if you
want upstream-only fetches:

```conf
INHERIT += "own-mirrors"
SOURCE_MIRROR_URL = "https://archiv.tuxbox-neutrino.org/"
# Optional: fail if the mirror misses a source (no upstream fetch)
# BB_FETCH_PREMIRRORONLY = "1"
```

### Troubleshooting: hdfastboot8gb basehash mismatch

On GFutures fastboot machines (hd60/hd61/hd66se), a basehash mismatch can
appear if `IMAGE_NAME` includes `DATETIME`. Ensure submodules are up to date;
recent `meta-tuxbox` excludes `IMAGE_NAME` from that task’s signature.

If you want a fresh timestamped image every run, force the task:

```bash
bitbake -f -c do_image_hdfastboot8gb tuxbox-image
```

## Documentation

- QUICKSTART: [EN](docs/QUICKSTART.md), [DE](docs/de/QUICKSTART.md) - 5-minute quick start guide
- QEMU: [EN](docs/QEMU.md), [DE](docs/de/QEMU.md) - QEMU smoke tests and dev workflow
- SUBMODULES: [EN](docs/SUBMODULES.md), [DE](docs/de/SUBMODULES.md) - Layers and submodules
- ARCHITECTURE: [EN](docs/ARCHITECTURE.md), [DE](docs/de/ARCHITECTURE.md) - System architecture
- HARDWARE: [EN](docs/HARDWARE_INTEGRATION.md), [DE](docs/de/HARDWARE_INTEGRATION.md) - Add new hardware
- COOLSTREAM: [EN](docs/COOLSTREAM.md), [DE](docs/de/COOLSTREAM.md) - uClibc builds (experimental/PoC)

## Supported Platforms

### Priority Platforms (Tested)
- **GFutures (Mut@nt/AX)**: HD51, HD60, HD61
- **AirDigital**: ZgemmaH7, H7S, H7C
- **Coolstream**: Tank (uClibc toolchain, experimental/PoC)

### All OE-Alliance Platforms (300+ devices)
See `make list-machines` for complete list. Not all machines are tested or
integrated for Neutrino; `libstb-hal` support is limited. See
`docs/HARDWARE_INTEGRATION.md` for the bring-up workflow.

## Key Features

- **OE-Alliance Integration**: Uses unmodified OE-Alliance infrastructure
- **Neutrino-Only**: No Enigma2 dependencies
- **Yocto Kirkstone**: LTS support until May 2026
- **Hybrid Build System**: Simple for beginners, powerful for developers
- **External Toolchain**: Coolstream uClibc support (experimental/PoC)
- **QEMU Testing**: Fast smoke tests without hardware

## Build Commands

### Makefile (Simple)
```bash
make image MACHINE=hd51           # Build image
make image MACHINE=hd51 FORCE_CONFIG=1  # Re-generate config
make config MACHINE=hd51          # Generate config only
make show-config MACHINE=hd51     # Show config + checks
make edit-conf MACHINE=hd51       # Edit config files
make feeds MACHINE=hd51           # Build package feeds (optional; image builds also generate indexes)
make clean                        # Clean build (keeps sstate)
make distclean                    # Clean everything
make list-machines                # Show all machines
make machine-info MACHINE=hd51    # Show hardware details
make help                         # Show all commands
```

### Python CLI (Advanced)
```bash
./cli.py init                     # Initialize build environment
./cli.py build -m hd51            # Build image
./cli.py config -m hd51           # Generate config only
./cli.py show-config -m hd51      # Show config + checks
./cli.py build -m hd51 --offline  # Offline build
./cli.py build -m hd51 --devshell # Drop to development shell
./cli.py fetch-only -m hd51       # Download sources only
./cli.py sync --check             # Check upstream updates (no changes)
./cli.py sync                     # Update submodules to upstream HEAD (unpinned)
./cli.py clean -m hd51            # Clean build directory
```

## GitHub Actions (Manual by Default)

Workflows are manual-only for now so private submodules can be used during
setup. Trigger runs from the Actions tab after configuring repository secrets
or SSH access for submodules. To automate, re-enable `push`/`schedule` in
`.github/workflows/*.yml` once submodule authentication is working.

## Project Structure

```
build-environment/           # Orchestrator (this repo)
├── Makefile                 # Simple build interface
├── cli.py                   # Advanced Python CLI
├── scripts/                 # Helper scripts
├── templates/               # Configuration templates
├── docs/                    # Documentation
└── .tuxbox/                 # State tracking

Submodules (auto-managed):
├── oe-alliance/             # OE-Alliance (unmodified)
├── meta-neutrino/           # Neutrino recipes (Kirkstone)
├── meta-tuxbox/             # Tuxbox distribution layer
└── meta-tuxbox-toolchain/   # External toolchains (Coolstream)
```

## Contributing

This is a Tuxbox-Neutrino community project. Contributions welcome!

- Report issues: https://github.com/tuxbox-neutrino/build-environment/issues
- Submit PRs: https://github.com/tuxbox-neutrino/build-environment/pulls

## License

- Orchestrator code: MIT License
- OE-Alliance: Various (see upstream)
- Neutrino: GPL-2.0

## Credits

- **Tuxbox-Neutrino Team**: GUI and integration
- **OE-Alliance**: Build infrastructure
- **Yocto Project**: OpenEmbedded core

---

**Built with ❤️ by the Tuxbox community**
