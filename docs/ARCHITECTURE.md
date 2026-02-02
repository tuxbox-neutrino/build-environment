# Tuxbox-OS Architecture

Understanding the build system architecture and design decisions.

## Contents

- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Directory Structure](#directory-structure)
- [Key Design Decisions](#key-design-decisions)
- [Build Optimization](#build-optimization)
- [Security Considerations](#security-considerations)
- [Extensibility](#extensibility)

## Overview

Tuxbox-OS Builder is a **parasitic integration** system that leverages OE-Alliance's mature build infrastructure while providing a Neutrino-focused distribution.

```
┌─────────────────────────────────────────────────────────────┐
│ User Interface                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ Makefile │  │ cli.py   │  │ Scripts  │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
└───────┼─────────────┼─────────────┼────────────────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
┌─────────────────────┼─────────────────────────────────────┐
│ Orchestrator Layer  │                                     │
│                     ▼                                     │
│  ┌─────────────────────────────────────────────────┐     │
│  │  Config Generator                               │     │
│  │   • bblayers.conf (layer composition)           │     │
│  │   • local.conf (build settings)                 │     │
│  │   • State tracking (.tuxbox/state.json)         │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
                      │
┌─────────────────────┼─────────────────────────────────────┐
│ Build System        ▼                                     │
│  ┌────────────────────────────────────────────────┐      │
│  │ OE-Alliance (Submodule - Unmodified)           │      │
│  │  • oe-alliance-core (meta-oe + meta-brands)    │      │
│  │  • Yocto Kirkstone (Whinlasser)                │      │
│  │  • 300+ hardware definitions                   │      │
│  │  • DVB drivers, kernels, bootloaders           │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ meta-neutrino (Submodule - Kirkstone branch)   │      │
│  │  • neutrino-mp recipes                         │      │
│  │  • libstb-hal                                  │      │
│  │  • Plugins (standard + Lua)                    │      │
│  │  • Themes                                      │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ meta-tuxbox (Submodule - Tuxbox layer)         │      │
│  │  • conf/distro/tuxbox.conf                     │      │
│  │  • recipes-distros/tuxbox/                     │      │
│  │    ├── image/tuxbox-image.bb                   │      │
│  │    ├── packagegroup/packagegroup-tuxbox-*.bb   │      │
│  │    └── bootlogo/                               │      │
│  │  • bbappends for OE-Alliance integration       │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ meta-tuxbox-toolchain (Optional)               │      │
│  │  • External toolchain support (Coolstream)      │      │
│  │  • conf/distro/tuxbox-uclibc.conf              │      │
│  │  • recipes-core/external-toolchain/            │      │
│  └────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│ Build Artifacts                                          │
│  • Images: build/tmp/deploy/images/<machine>/            │
│  • Packages: build/tmp/deploy/ipk/                       │
│  • SDK: build/tmp/deploy/sdk/                            │
└──────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Parasitic Integration

**Philosophy**: Don't reinvent the wheel. Use OE-Alliance as-is.

**Benefits**:
- ✅ Low maintenance for hardware definitions (Neutrino integration still required)
- ✅ Automatic upstream updates
- ✅ Proven, production-ready infrastructure
- ✅ 300+ machine definitions available (Neutrino integration varies by boxmodel)

**Implementation**:
- OE-Alliance as **unmodified git submodule** (pinned SHA)
- Only add our distribution layer on top
- Use bbappends to remove E2 dependencies from shared recipes

### 2. Layer Hierarchy

Layers are stacked with priority ordering (higher = more important):

```
Priority 15: meta-local          (User customizations)
Priority 10: meta-tuxbox         (Tuxbox distribution)
Priority  9: meta-tuxbox-toolchain (External toolchains)
Priority  7: meta-brands         (Hardware support from OE-A)
Priority  7: meta-oe             (OE-Alliance base)
Priority  7: meta-neutrino       (Neutrino recipes)
Priority  6: meta-openembedded   (Extended recipes)
Priority  5: meta                (Yocto core - lowest)
```

Higher priority layers can **override** recipes from lower layers.

### 3. Distribution Model

**Tuxbox** is a **distribution** (like OpenATV, OpenVix are for E2).

**Distribution defines**:
- conf/distro/tuxbox.conf - Core settings
- Preferred providers (Neutrino instead of Enigma2)
- DISTRO_FEATURES (systemd, no E2-specific features)
- Optimization flags
- Image naming and versioning

**Machines are separate** from distribution:
- Same Tuxbox distribution can build for any OE-Alliance machine
- `MACHINE=hd51 DISTRO=tuxbox` → Tuxbox on HD51
- `MACHINE=hd60 DISTRO=tuxbox` → Tuxbox on HD60

### 4. Hardware Coverage and Neutrino Integration

OE-Alliance provides 300+ machine definitions, but not all of them are tested
or integrated for Neutrino. Neutrino requires `libstb-hal` support, and that
library only lists a subset of `boxmodel` values. For machines outside that
subset, you will need to extend `libstb-hal` and the hardware backend.

For a precise bring-up workflow, see:
`docs/HARDWARE_INTEGRATION.md`.

### 5. Image Composition

Images are built from **packagegroups**:

```
tuxbox-image.bb
  └─ requires: packagegroup-tuxbox-base
       ├─ systemd
       ├─ busybox
       ├─ e2fsprogs
       └─ ... (system essentials)

  └─ requires: packagegroup-tuxbox-neutrino
       ├─ neutrino-mp
       ├─ libstb-hal
       ├─ neutrino-plugins
       ├─ neutrino-webif
       └─ ... (Neutrino stack)

  └─ conditionally:
       ├─ packagegroup-tuxbox-wifi (if MACHINE_FEATURES += "wifi")
       ├─ packagegroup-tuxbox-dvb-c (if dvb-c support)
       └─ ... (hardware-dependent)
```

### 6. Configuration Generation

Build configurations are **generated dynamically**:

**bblayers.conf** (Layer composition):
```
BBLAYERS = " \
    ${TOPDIR}/oe-alliance/openembedded-core/meta \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-oe \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-python \
    ${TOPDIR}/oe-alliance/meta-openembedded/meta-networking \
    ${TOPDIR}/oe-alliance/meta-oe \
    ${TOPDIR}/oe-alliance/meta-brands/meta-gfutures \  # For HD51/60/61
    ${TOPDIR}/meta-neutrino \
    ${TOPDIR}/meta-tuxbox \
    ${TOPDIR}/meta-local \
"
```

**local.conf** (Build settings):
```
MACHINE = "hd51"
DISTRO = "tuxbox"
DL_DIR = "${TOPDIR}/downloads"
SSTATE_DIR = "${TOPDIR}/sstate-cache"
# Parallelism defaults: leave unset to use BitBake auto CPU count
# BB_NUMBER_THREADS ?= "${@oe.utils.cpu_count()}"
# PARALLEL_MAKE ?= "-j ${@oe.utils.cpu_count()}"
# Optional: switch Lua provider if needed
# PREFERRED_PROVIDER_virtual/lua = "lua"
```

Configurations are **hash-tracked** - regenerated only when variables change.

### 7. Build Flow

```
1. User runs: make image MACHINE=hd51
              └→ cli.py build --machine hd51

2. Check prerequisites
   ├─ Verify required tools installed
   ├─ Check disk space (100GB+)
   └─ Validate Python version

3. Initialize submodules
   ├─ git submodule init
   └─ git submodule update --recursive

4. Generate configuration
   ├─ Detect machine brand → load correct meta-brand layer
   ├─ Generate bblayers.conf (layer composition)
   ├─ Generate local.conf (build variables)
   └─ Hash config → skip if unchanged

5. Invoke BitBake
   ├─ source oe-init-build-env
   └─ bitbake tuxbox-image

6. BitBake processing
   ├─ Parse recipes from all layers
   ├─ Resolve dependencies
   ├─ Download sources (to downloads/)
   ├─ Compile packages
   ├─ Cache build state (to sstate-cache/)
   └─ Assemble image

7. Deploy artifacts
   └─ build/tmp/deploy/images/hd51/
       ├─ tuxbox-image-hd51.zip
       ├─ bzImage (kernel)
       └─ rootfs.tar.bz2
```

## Directory Structure

```
build-environment/               # Orchestrator repository
├── Makefile                     # Simple build interface
├── cli.py                       # Advanced Python CLI
├── scripts/                     # Helper scripts
│   ├── check-prerequisites.sh
│   ├── init.sh
│   ├── machine-info.sh
│   ├── migration/               # Kirkstone migration tools
│   └── qemu/                    # QEMU testing scripts
├── templates/                   # Configuration templates
│   ├── bblayers.conf.template
│   └── local.conf.template
├── .tuxbox/                     # State tracking
│   └── state.json               # Build state
├── build/                       # Build output (generated)
│   ├── conf/                    # Generated configs
│   └── tmp/                     # Build artifacts
├── downloads/                   # Source downloads (shared)
├── sstate-cache/                # Shared state cache (shared)
├── docs/                        # Documentation
└── .github/workflows/           # CI/CD

Submodules (Git submodules):
├── oe-alliance/                 # OE-Alliance (unmodified)
│   ├── meta-oe/                 # Base recipes
│   ├── meta-brands/             # Hardware support
│   │   ├── meta-gfutures/
│   │   ├── meta-airdigital/
│   │   └── ... (30+ brands)
│   └── openembedded-core/       # Yocto core
├── meta-neutrino/               # Neutrino recipes (Kirkstone branch)
│   ├── recipes-neutrino/
│   │   ├── neutrino/
│   │   ├── libstb-hal/
│   │   └── neutrino-plugins/
│   └── conf/
├── meta-tuxbox/                 # Tuxbox distribution layer
│   ├── conf/
│   │   ├── distro/tuxbox.conf
│   │   └── layer.conf
│   ├── recipes-distros/tuxbox/
│   │   ├── image/
│   │   ├── packagegroup/
│   │   └── bootlogo/
│   └── recipes-bsp/             # bbappends for drivers
└── meta-tuxbox-toolchain/       # External toolchains (Coolstream)
    ├── conf/distro/tuxbox-uclibc.conf
    └── recipes-core/external-toolchain/
```

## Key Design Decisions

### Why Submodules?

**Pros**:
- ✅ Upstream changes tracked explicitly (pinned SHA)
- ✅ Easy to update: `git submodule update --remote`
- ✅ Clear separation of our code vs. upstream
- ✅ No merge conflicts with upstream

**Cons**:
- ❌ Users must remember `--recursive` when cloning
- ❌ Submodule updates require explicit commit

**Mitigation**: Our init scripts handle submodules automatically.

### Why Python CLI + Makefile?

**Makefile**: Simple interface for beginners
- `make image MACHINE=hd51` - Just works™

**Python CLI**: Power for developers
- State tracking (JSON)
- Better error handling
- Advanced features (offline, devshell, sync)
- Extensible

**Best of both worlds**: Makefile delegates to CLI when available.

### Why Kirkstone (Not Latest Yocto)?

**Kirkstone (4.0)**:
- ✅ LTS release (support until May 2026)
- ✅ Stable, well-tested
- ✅ Good balance of modern + proven

**Not Scarthgap (5.0)**:
- ❌ OE-Alliance not yet on Whinlasser everywhere
- ❌ Newer = more churn, less stable
- ❌ Migration effort for meta-neutrino

**Strategy**: Kirkstone now, upgrade to next LTS when OE-A ready.

### Why Separate Toolchain Layer?

**Coolstream Tank requires uClibc** (not glibc):
- Different ABI, different toolchain
- Can't mix glibc and uClibc in same layer
- Clean separation via `meta-tuxbox-toolchain`

**Status**: Coolstream support is experimental/PoC and not production-ready.

**Benefits**:
- ✅ Doesn't pollute main layer
- ✅ Optional (only loaded for tank builds)
- ✅ Easy to add more external toolchains

## Build Optimization

### Shared State Cache (sstate)

**What**: Pre-built package cache
**Where**: `sstate-cache/`
**Benefit**: Rebuilds 10-20x faster

**First build**: 2-4 hours (everything from source)
**Incremental build**: 20-40 minutes (90% from cache)

**Share between machines**:
```bash
# Same sstate for all builds
SSTATE_DIR = "/opt/tuxbox-os/sstate-cache"
```

### Download Cache

**What**: Source tarballs cache
**Where**: `downloads/`
**Benefit**: No re-download on rebuilds

**Size**: ~10GB after full build

**Share between machines**:
```bash
DL_DIR = "/opt/tuxbox-os/downloads"
```

### Parallel Builds

**Default**: BitBake already sets parallelism to CPU count when variables are
unset (see `poky/meta/conf/bitbake.conf`).

**Optional override** (in `local.conf.user.inc`):
```
BB_NUMBER_THREADS = "8"  # Run 8 recipes in parallel
PARALLEL_MAKE = "-j 8"   # Run 8 gcc jobs in parallel
```

**Recommendation**: use `nproc - 1` if you want to leave one core for the system.

## Security Considerations

### Submodule Pinning

**Always pin submodules to specific SHA**:
```bash
cd oe-alliance
git checkout <specific-sha>
cd ..
git add oe-alliance
git commit -m "Pin OE-Alliance to <sha>"
```

**Why**: Prevent surprise upstream changes breaking builds.

### Source Verification

**BitBake verifies sources**:
- SRC_URI with checksums (MD5, SHA256)
- Signature verification for critical packages

**Example**:
```
SRC_URI[sha256sum] = "abc123..."
```

If checksum mismatches → build fails (prevents MITM).

## Extensibility

### Adding a New Machine

1. Ensure meta-brand layer included in bblayers.conf
2. Set MACHINE variable
3. Build

**Example for Vu+ Ultimo 4K**:
```bash
# Add meta-vuplus to bblayers.conf (if not already)
make image MACHINE=ultimo4k
```

### Adding a New Distribution

1. Create `conf/distro/mydistro.conf` in meta-tuxbox
2. Define DISTRO features
3. Build with `DISTRO=mydistro`

### Custom Packages

1. Create recipe in `meta-tuxbox/recipes-custom/`
2. Add to image via packagegroup
3. Rebuild

---

**For more details, see:**
- [QUICKSTART.md](QUICKSTART.md) - First build steps
- [SUBMODULES.md](SUBMODULES.md) - Layers and pinning
- [HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md) - Add new hardware
- [COOLSTREAM.md](COOLSTREAM.md) - External toolchain details
- [README.md](../README.md) - Project overview and commands
