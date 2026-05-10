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
  python3-jinja2 python3-subunit zstd lz4 file locales libacl1 curl \
  luajit
```

For 32-bit target builds on a 64-bit host (for example `armhf` machines such as
HD60/HD61):

```bash
sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386
```

`make check` verifies this with a real `gcc -m32` and `g++ -m32` compile test.

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

Default STB flash workflows back up settings via Neutrino's `backup.sh` and
`/etc/neutrino/config/tobackup.conf`. `etckeeper` is kept as an optional extra
tool for feed installation and is no longer part of the default image payload.
The default runtime set also includes the Neutrino `mediathek` plugin.

## 4. Verify Host And Sync Safe Defaults

```bash
make check
make update
```

What `make update` does:

- Pulls top-level repository changes without recursively fetching submodules.
- Syncs submodule URLs from `.gitmodules`.
- Checks out pinned submodule commits (safe/reproducible).

Why this matters:

- The top-level pull no longer tries to recurse into submodules mid-update, so
  transient pin changes from another host are handled more reliably.
- If `make update` still stops, check for local commits or uncommitted changes
  inside a submodule. The safe sync will not overwrite that local state.

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

Fastboot/multiboot machines such as HD60 install the STB Lua plugin bundle by
default in the image. That includes `stb-startup` together with the related
flash, backup, and restore plugins. All images also install `logoupdater`
with its required runtime helper tools by default. The default runtime also
ships the yWeb helpers for OSD screenshots and AutoMount (`grab`, `fbshot`,
and `autofs`/`automount`).

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

# Show the local feed URL embedded in new images
make feed-server-url MACHINE=hd51

# Clean build artifacts (keeps caches)
make clean
```

Optional sync variant:

```bash
make sync SYNC_EXCLUDE="meta-coolstream meta-tuxbox-toolchain"
```

## 9. Local IPK Feed

By default, `make image` and `make feeds` publish the generated IPK feed and
start a static HTTP server below `feed-server/`.

Default feed URL:

```text
http://<host-ip>:33333/<MACHINE>/ipk
```

The image gets this URL through `/etc/opkg/base-feeds.conf`, so a freshly
flashed box can use the packages immediately:

```bash
opkg update
opkg install <package>
```

Useful host commands:

```bash
make feed-server-url MACHINE=hd60
make feed-server-urls
make feed-server-start-all
make feed-server-status
make feed-server-stop
```

`lighttpd` is optional. If it is not installed, the builder uses
`python3 -m http.server`. Open TCP port `33333` in the host firewall if the
box should reach the feed from the LAN.

Override the feed URL for public feeds in `builds/conf/local.conf.user.inc`:

```conf
IPK_FEED_SERVER = "https://feeds.example.org/tuxbox/${MACHINE}/ipk"
```

Disable the automatic local feed default when needed:

```bash
make image MACHINE=hd60 LOCAL_FEED=0
```

## 10. Optional: Toaster Web Frontend

This integration is currently experimental.

Use the dedicated guide:

- [Toaster (Experimental)](TOASTER_EXPERIMENTAL.md)

For existing builds, you can import your current build dir into Toaster:

```bash
make toaster-import-build
```

Defaults:
- `TOASTER_IMPORT_NAME=$(DISTRO)-build`
- `TOASTER_IMPORT_PATH=$(TOASTER_BUILD_DIR)`

## 11. Updating: Users Vs Developers

### For users: stay on `make update`

`make update` always checks out the **pinned submodule commits** — a tested,
stable combination. It updates the top-level repo first and then applies the
pinned submodule state explicitly, which is more robust when multiple hosts
or workstations sync at different times. Your build is
reproducible. This is the only update command you need as a user.

### For developers: `make update-upstream`

```bash
make update-upstream
```

This moves all submodules to the **latest commit** on their tracking branch
(e.g. `kirkstone` for Poky/meta-openembedded, `5.1` for OE-Alliance,
`master` for meta-neutrino/meta-tuxbox). You stay on the same Yocto release,
but get the newest upstream patches.

**Warning:** This can break your build because the new combination has not
been tested. Only use this if you intend to test and update the pins.

After a successful build, pin the new state:

```bash
git add poky oe-alliance meta-openembedded meta-neutrino meta-tuxbox
git commit -m "chore (deps): pin submodules to latest tracked branches"
```

General pin policy:
- During active development, it is acceptable to work locally on the current
  upstream tracking heads of the active Yocto line.
- Update the recorded pins only when you have a validated shared state,
  maintenance fix set, or release candidate.
- Once a Kirkstone release is cut, keep those pins stable and move them only
  through deliberate, validated maintenance updates.

To return to the safe pinned state at any time:

```bash
make update
```

### Contributing

If you find a bug or want to propose a change:

- Open an [Issue](https://github.com/tuxbox-neutrino/build-environment/issues)
  to report problems or suggest improvements.
- Submit a [Pull Request](https://github.com/tuxbox-neutrino/build-environment/pulls)
  for code changes. Please test your changes before submitting.
- Do not push untested submodule pins to `master`.

## 12. Troubleshooting (Quick)

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

If that does not fix it, inspect the submodules for local commits or
uncommitted changes:

```bash
git submodule foreach --recursive 'git status --short --branch'
```

### basehash mismatch in `do_image_hdfastboot8gb`

```bash
bitbake hdf-toolbox-image -c cleanall
make image MACHINE=hdfastboot8gb MACHINEBUILD=hdfastboot8gb
```

## 13. Where To Go Next

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
- [Toaster (DE, Experimental)](de/TOASTER_EXPERIMENTAL.md)
