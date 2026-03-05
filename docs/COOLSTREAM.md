# Coolstream (uClibc) Builds

Deutsch: [de/COOLSTREAM.md](de/COOLSTREAM.md)

This guide explains the current Coolstream build path.
It is an advanced workflow and currently **experimental**.

If you are new to the project, start with [QUICKSTART.md](QUICKSTART.md) first.

## 1. Scope

Coolstream images differ from the regular glibc flow:

- They use an external uClibc toolchain.
- They require Coolstream-specific machine definitions.
- They are intended for bring-up/testing, not general newcomer builds.

Known machine mapping (NI box naming):

- `coolstream-nevis` (HD1, glibc): HD1/BSE/NEO/NEO2/NEO2 Twin/ZEE
- `coolstream-apollo` (HD2, uClibc): Tank
- `coolstream-shiner` (HD2, uClibc): Trinity V1
- `coolstream-kronos` (HD2, uClibc): Zee2 / Trinity V2
- `coolstream-kronos-v2` (HD2, uClibc): Link / Trinity Duo

## 2. Required Layers And Components

- `meta-coolstream` (machines/BSP)
- `meta-tuxbox-toolchain` (external toolchain integration)
- external toolchain tarball `toolchain-coolstream-uclibc-armv7.tar.bz2`

Related terms are in the [Glossary](GLOSSARY.md).

## 3. Toolchain Source

Reference values:

- URL: `https://sourceforge.net/projects/n4k/files/toolchains/`
- File: `toolchain-coolstream-uclibc-armv7.tar.bz2`
- SHA256: `b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

Quick integrity check:

```bash
sha256sum toolchain-coolstream-uclibc-armv7.tar.bz2
```

## 4. Configure Build

### 4.1 Generate base config

```bash
make config MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 4.2 Ensure layer and libc/toolchain settings

Add or verify these values in your active build config files:

```conf
# local.conf (or local include)
MACHINE = "coolstream-apollo"
MACHINEBUILD = "coolstream-apollo"
TCMODE = "external-coolstream"
TCLIBC = "uclibc"
```

```conf
# bblayers.conf
BBLAYERS += "${TOPDIR}/../meta-coolstream"
```

If needed, use:

```bash
make show-config MACHINE=coolstream-apollo
make edit-conf MACHINE=coolstream-apollo
```

## 5. Build Workflow

### 5.1 Full build

```bash
make update
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 5.2 Incremental work

```bash
# Rebuild image after recipe/config changes
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo

# Clean and rebuild if state is inconsistent
make clean
make image MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo
```

### 5.3 Low-level BitBake path (optional)

```bash
make bb MACHINE=coolstream-apollo MACHINEBUILD=coolstream-apollo TARGET=tuxbox-image
```

## 6. Validation

After build, check artifacts:

```bash
ls -lah builds/build/tmp/deploy/images/coolstream-apollo 2>/dev/null || \
ls -lah build/build/tmp/deploy/images/coolstream-apollo
```

Recommended before hardware flash:

- verify generated kernel/rootfs artifacts
- review flash scripts and machine profile values
- test generic package/update paths on QEMU first where possible

## 7. Troubleshooting

### Toolchain download/checksum mismatch

```bash
sha256sum toolchain-coolstream-uclibc-armv7.tar.bz2
```

Expected SHA256:

`b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

### Compiler not found

```bash
find . -type f -name 'arm-cortex-linux-uclibcgnueabi-gcc' | head
```

If no compiler is found, verify toolchain extraction path and
`EXTERNAL_TOOLCHAIN_BIN` settings in the toolchain integration class.

### Library/runtime compatibility issues

- Confirm `TCLIBC = "uclibc"` is active for the current build.
- Recheck package compatibility against uClibc.
- Rebuild affected recipes cleanly.

### Kernel/driver mismatch

- Verify machine-specific kernel recipe alignment.
- Recheck Coolstream BSP layer contents and branch.

## 8. References

- [QUICKSTART.md](QUICKSTART.md)
- [SUBMODULES.md](SUBMODULES.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [GLOSSARY.md](GLOSSARY.md)
- [README.md](../README.md)
