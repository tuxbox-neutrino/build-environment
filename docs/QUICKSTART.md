# Tuxbox-OS Quickstart (Detailed)

Deutsch: [de/QUICKSTART.md](de/QUICKSTART.md)

This guide is for your first successful build with safe defaults.
If you want the shortest path, start in [../README.md](../README.md) and come
back here for details.

Key terms in this page are explained in the
[Glossary](GLOSSARY.md) (for example:
[submodule](GLOSSARY.md#submodule),
[pinning](GLOSSARY.md#pinning),
[MACHINE](GLOSSARY.md#machine),
[MACHINEBUILD](GLOSSARY.md#machinebuild)).

## 1. Host Requirements

Supported host systems:

- Debian 11/12
- Ubuntu 20.04/22.04 LTS

Minimum tools:

- `bash`, `git`, `python3`
- Build toolchain packages from the next section

## 2. Install Dependencies

### Debian/Ubuntu

```bash
sudo apt update
sudo apt install -y gawk wget git diffstat unzip texinfo \
  gcc g++ build-essential chrpath socat cpio python3 python3-pip \
  python3-pexpect xz-utils debianutils iputils-ping python3-git \
  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 curl
```

For 32-bit target builds on a 64-bit host (for example `armhf` machines such as
HD60/HD61):

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

Optional but recommended locale check:

```bash
locale | grep -E 'LANG=|LC_ALL='
```

If needed:

```bash
sudo dpkg-reconfigure locales
```

## 3. Clone And Prepare Sources

Fresh clone (recommended):

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/build-environment.git
cd build-environment
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

If you have access to private GitHub submodules and want SSH instead of HTTPS:

```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

## 4. Verify Host And Sync Safe Defaults

```bash
make check
make update
```

What `make update` does:

- Pulls top-level repository changes.
- Checks out pinned submodule commits (safe/reproducible).

## 5. Choose Machine Values

List available machines:

```bash
make list-machines
```

Inspect one machine:

```bash
make machine-info MACHINE=hd51
```

If your machine needs a specific `MACHINEBUILD`, `make machine-info` will show
it. On many machines, `MACHINEBUILD` equals `MACHINE`.

## 6. Build Your First Image

### Known-good starter examples

```bash
# GFutures HD51
make image MACHINE=hd51 MACHINEBUILD=mutant51

# GFutures HD60
make image MACHINE=hd60 MACHINEBUILD=mutant60

# Zgemma H7
make image MACHINE=zgemmah7 MACHINEBUILD=zgemmah7
```

If you only want to generate configuration first:

```bash
make config MACHINE=hd51 MACHINEBUILD=mutant51
make show-config MACHINE=hd51
```

## 7. Find Build Artifacts

Image artifacts are typically here:

- `builds/build/tmp/deploy/images/<machine>/`
- `build/build/tmp/deploy/images/<machine>/`

Example:

```bash
ls -lah builds/build/tmp/deploy/images/hd51 2>/dev/null || \
ls -lah build/build/tmp/deploy/images/hd51
```

## 8. Daily Workflow (Safe)

```bash
# Update top-level repo + pinned submodules
make update

# Build image
make image MACHINE=hd51 MACHINEBUILD=mutant51

# Build package feeds
make feeds MACHINE=hd51 MACHINEBUILD=mutant51

# Clean build artifacts (keeps caches)
make clean
```

Optional sync variant:

```bash
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

## 9. Advanced Updates (Maintainers Only)

These commands move submodules to upstream HEAD (unpinned):

```bash
make update-upstream
# Or
./cli.py sync
```

Use this only when you intentionally update layer pins.
If you did this by mistake, return to pinned state:

```bash
make update
```

## 10. Troubleshooting (Quick)

### "No space left on device"

```bash
df -h
make clean
```

### Missing host package or tool

```bash
make check
```

### Submodule state looks wrong

```bash
make update
```

### basehash mismatch in `do_image_hdfastboot8gb`

```bash
bitbake hdf-toolbox-image -c cleanall
make image MACHINE=hdfastboot8gb MACHINEBUILD=hdfastboot8gb
```

## 11. Where To Go Next

- [Layers and Submodules](SUBMODULES.md)
- [Architecture](ARCHITECTURE.md)
- [QEMU](QEMU.md)
- [Hardware Integration](HARDWARE_INTEGRATION.md)
- [Image Version Contract](IMAGE_VERSION_CONTRACT.md)
- [Glossary](GLOSSARY.md)

German docs:

- [Quickstart (DE)](de/QUICKSTART.md)
- [Submodules (DE)](de/SUBMODULES.md)
- [Glossary (DE)](de/GLOSSARY.md)
