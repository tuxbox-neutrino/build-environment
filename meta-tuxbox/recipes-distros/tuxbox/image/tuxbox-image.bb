# Tuxbox-OS Image Recipe
#
# Main image recipe for Tuxbox-OS with Neutrino

require tuxbox-image.inc

DESCRIPTION = "Tuxbox-OS Neutrino Image"
LICENSE = "MIT"

PV = "${DISTRO_VERSION}"
PR = "r1"

# Conditional large image packages (excluded on small flash devices)
BIG_IMAGE_PACKAGES = " \
    neutrino-plugins-extra \
    packagegroup-tuxbox-multimedia-extra \
    packagegroup-tuxbox-tools \
    packagegroup-tuxbox-dev \
"

# Add big packages only if not small flash
IMAGE_INSTALL += "${@bb.utils.contains('IMAGESIZE', 'small', '', '${BIG_IMAGE_PACKAGES}', d)}"

# Image variant
IMAGE_BASENAME = "tuxbox-image"
