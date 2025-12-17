# meta-tuxbox

Yocto/OpenEmbedded layer for Tuxbox-OS distribution with Neutrino GUI.

## Description

This layer provides the Tuxbox-OS distribution configuration and image recipes for building Neutrino-based Set-Top-Box images on OE-Alliance hardware platforms.

## Layer Dependencies

- **meta** (openembedded-core)
- **meta-openembedded** (meta-oe, meta-networking, meta-python)
- **meta-oe-alliance** (from OE-Alliance)
- **meta-neutrino** (Neutrino recipes)

## Layer Compatibility

- **Yocto Release**: Kirkstone (4.0 LTS)
- **Layer Series**: kirkstone

## Contents

### Distribution Configuration
- `conf/distro/tuxbox.conf` - Tuxbox-OS distribution settings

### Image Recipes
- `recipes-distros/tuxbox/image/tuxbox-image.bb` - Main image recipe
- `recipes-distros/tuxbox/image/tuxbox-image.inc` - Common image configuration

### Package Groups
- `packagegroup-tuxbox-base` - Essential system packages
- `packagegroup-tuxbox-neutrino` - Neutrino GUI stack
- `packagegroup-tuxbox-multimedia` - Multimedia framework
- `packagegroup-tuxbox-network` - Network services
- `packagegroup-tuxbox-wifi` - WiFi support

### Classes
- `tuxbox-version.bbclass` - Image version information generation

## Usage

Add this layer to your `bblayers.conf`:

```
BBLAYERS += "/path/to/meta-tuxbox"
```

Set distribution in `local.conf`:

```
DISTRO = "tuxbox"
```

Build an image:

```bash
bitbake tuxbox-image
```

## Supported Machines

All machines supported by OE-Alliance meta-brands layers:
- Gigablue (hd51, hd60, hd61, uhd4k, etc.)
- AirDigital/Zgemma (zgemmah7, h7s, h7c, etc.)
- Vu+ (ultimo4k, uno4k, duo4k, etc.)
- And 300+ more...

## License

MIT License (for layer infrastructure)

Individual recipes may have different licenses - check each recipe.

## Maintainer

Tuxbox Neutrino Team
