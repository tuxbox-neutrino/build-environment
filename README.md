# Tuxbox-OS Builder

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

### 2. Clone & Initialize

```bash
git clone --recurse-submodules https://github.com/tuxbox-neutrino/tuxbox-os-builder.git
cd tuxbox-os-builder
./cli.py init
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

### 3. Build an Image

```bash
# Build for HD51
make image MACHINE=hd51

# Prepare config only (no build)
make config MACHINE=hd51
make show-config MACHINE=hd51
make edit-conf MACHINE=hd51

# If configs already exist, make image reuses them.
# Force regeneration when needed:
make image MACHINE=hd51 FORCE_CONFIG=1

# OEM/brand variants (both MACHINE and MACHINEBUILD required)
make image MACHINE=inihde2 MACHINEBUILD=atemio6000

# Or using Python CLI
./cli.py build --machine hd51
MACHINEBUILD=atemio6000 ./cli.py build --machine inihde2
```

Built images will be in `build/tmp/deploy/images/hd51/`

## Supported Platforms

### Priority Platforms (Tested)
- **GFutures (Mut@nt/AX)**: HD51, HD60, HD61
- **AirDigital**: ZgemmaH7, H7S, H7C
- **Coolstream**: Tank (uClibc toolchain)

### All OE-Alliance Platforms (300+ devices)
See `make list-machines` for complete list.

## Key Features

- **OE-Alliance Integration**: Uses unmodified OE-Alliance infrastructure
- **Neutrino-Only**: No Enigma2 dependencies
- **Yocto Kirkstone**: LTS support until May 2026
- **Hybrid Build System**: Simple for beginners, powerful for developers
- **External Toolchain**: Coolstream uClibc support
- **QEMU Testing**: Fast smoke tests without hardware

## Build Commands

### Makefile (Simple)
```bash
make image MACHINE=hd51           # Build image
make image MACHINE=hd51 FORCE_CONFIG=1  # Re-generate config
make config MACHINE=hd51          # Generate config only
make show-config MACHINE=hd51     # Show config + checks
make edit-conf MACHINE=hd51       # Edit config files
make feeds MACHINE=hd51           # Build package feeds
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
./cli.py sync --check             # Check upstream updates
./cli.py clean -m hd51            # Clean build directory
```

## Documentation

- [QUICKSTART.md](docs/QUICKSTART.md) - 5-minute quick start guide
- [SUBMODULES.md](docs/SUBMODULES.md) - Beginner guide to layers and submodules
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [COOLSTREAM.md](docs/COOLSTREAM.md) - Coolstream Tank uClibc builds

## Project Structure

```
tuxbox-os-builder/           # Orchestrator (this repo)
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

- Report issues: https://github.com/tuxbox-neutrino/tuxbox-os-builder/issues
- Submit PRs: https://github.com/tuxbox-neutrino/tuxbox-os-builder/pulls

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
