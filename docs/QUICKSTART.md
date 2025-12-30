# Tuxbox-OS Quick Start Guide

Get started building Neutrino images in under 10 minutes.

## Prerequisites

### Hardware Requirements
- **CPU**: Modern multi-core processor (4+ cores recommended)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Disk**: 100GB+ free space (SSD recommended)
- **Network**: Broadband connection for downloading sources

### Software Requirements
- **OS**: Debian 11/12, Ubuntu 20.04/22.04 LTS (or similar)
- **Python**: 3.6 or higher
- **Git**: 1.8.3.1 or higher

## Step 1: Install Dependencies

### Debian 11/12 or Ubuntu 20.04/22.04

```bash
sudo apt update
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 curl
```

### Configure Locale

```bash
sudo dpkg-reconfigure locales
# Select: en_US.UTF-8
```

### Configure Git

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Step 2: Clone Repository

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/tuxbox-os-builder.git
cd tuxbox-os-builder
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

If you have access to private GitHub submodules, use SSH instead of HTTPS:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

If you get repeated passphrase prompts, load your SSH key once:

```bash
ssh-add ~/.ssh/id_rsa
```

### What are submodules (in simple terms)?

This project keeps the build layers in their own Git repositories.
Those repositories are linked as "submodules" so we can pin exact versions
and still keep the layers clean and independent.

## Step 3: Initialize Build Environment

### Option A: Using Python CLI (Recommended)

```bash
./cli.py check   # Verify prerequisites
./cli.py init    # Initialize environment
```

### Option B: Using Makefile

```bash
make check  # Verify prerequisites
make init   # Initialize environment
```

## Step 4: Build Your First Image

### For GFutures (Mut@nt/AX) HD51

```bash
# Using Python CLI
./cli.py build --machine hd51

# Or using Makefile (use MACHINEBUILD when it differs from MACHINE)
make image MACHINE=hd51 MACHINEBUILD=mutant51
```

### OEM variants (use MACHINEBUILD when it differs)

```bash
# Example: OEM variant for hd51
make image MACHINE=hd51 MACHINEBUILD=mutant51
MACHINEBUILD=mutant51 ./cli.py build --machine hd51

# Find valid MACHINEBUILD values
make list-machines
make machine-info MACHINE=hd51
```

### For GFutures (Mut@nt/AX) HD60/HD61

```bash
make image MACHINE=hd60
# or
make image MACHINE=hd61
```

### For Zgemma H7

```bash
make image MACHINE=zgemmah7
```

### Prepare Configuration Only

Use the same parameters as `make image`, but it will only generate config files:

```bash
make config MACHINE=hd51
make show-config MACHINE=hd51   # shows values + source file
make edit-conf MACHINE=hd51     # opens the include files
```

`make show-config` lists where each value comes from (local.conf vs include
files) and lists layers from `bblayers.conf` plus the user include file.

If configs already exist, `make image` reuses them. To force regeneration:

```bash
make image MACHINE=hd51 FORCE_CONFIG=1
```

### Persistent Local Overrides (Recommended)

Avoid editing `build/conf/local.conf` directly. Use the include files instead:

- `build/conf/local.conf.user.inc` (personal defaults)
- `build/conf/local.conf.<machine>.inc` (machine-specific tweaks)
- `build/conf/bblayers.conf.user.inc` (extra layers/masks)

These files are created automatically by `make config` and are safe from regeneration.

**Build time**: 2-4 hours on first build (downloads ~10GB sources)

**Subsequent builds**: 20-40 minutes (using cache)

## Step 5: Find Your Image

Built images are in:

```
build/tmp/deploy/images/<machine>/
```

Example for HD51:
```
build/tmp/deploy/images/hd51/tuxbox-image-hd51-20231217120000.zip
```

## Step 6: Flash Image

### USB Flash Method (Recommended)

1. **Extract** the image ZIP file
2. **Copy** contents to FAT32-formatted USB stick
3. **Insert** USB stick into receiver
4. **Power on** receiver
5. Follow on-screen flash instructions

### WebIF Flash Method

1. Access receiver WebIF: `http://<receiver-ip>`
2. Navigate to **System** → **Software Update**
3. Upload image file
4. Confirm and wait for flash to complete
5. Receiver will reboot automatically

## Common Tasks

### Update Sources

```bash
./cli.py sync
# Or
make update
```

### Update Layers (Submodules)

```bash
git submodule update --init --recursive
```

### Clean Build

```bash
./cli.py clean --machine hd51
# Or
make clean
```

### Build Package Feeds

```bash
./cli.py build --machine hd51 --target feeds
# Or
make feeds MACHINE=hd51
```

### Offline Build

First, download all sources:
```bash
./cli.py fetch-only --machine hd51
```

Then build offline:
```bash
./cli.py build --machine hd51 --offline
```

### Development Shell

```bash
./cli.py build --machine hd51 --devshell
```

## Troubleshooting

### Build Fails: "No space left on device"

```bash
# Check free space
df -h .

# Clean old builds
make clean

# Or remove downloads (will re-download)
rm -rf downloads/
```

### Build Fails: Missing packages

```bash
# Re-run dependency installation
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1
```

### Submodule Issues

```bash
git submodule update --init --recursive --force
```

### Reset Everything

```bash
make distclean  # Removes all builds and caches
./cli.py init   # Re-initialize
```

## Next Steps

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand how it works
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Customize and extend
- **[COOLSTREAM.md](COOLSTREAM.md)** - Build for Coolstream Tank
- **[FAQ.md](FAQ.md)** - Common questions

## Getting Help

- **Issues**: https://github.com/tuxbox-neutrino/tuxbox-os-builder/issues
- **Forum**: https://forum.tuxbox-neutrino.org
- **IRC**: #tuxbox-neutrino on libera.chat

---

Happy Building! 🎉
