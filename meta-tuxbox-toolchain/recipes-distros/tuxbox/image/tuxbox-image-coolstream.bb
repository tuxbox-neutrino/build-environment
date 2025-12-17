# Tuxbox-OS Image for Coolstream Tank (uClibc)

require recipes-distros/tuxbox/image/tuxbox-image.inc

DESCRIPTION = "Tuxbox-OS Neutrino Image for Coolstream Tank (uClibc)"
LICENSE = "MIT"

# Add Coolstream-specific packages
IMAGE_INSTALL:append = " \
    packagegroup-coolstream \
"

# Remove packages incompatible with uClibc
IMAGE_INSTALL:remove = " \
    systemd-resolved \
"

# Override image basename
IMAGE_BASENAME = "tuxbox-image-coolstream"

# Coolstream-specific image settings
IMAGE_FSTYPES = "tar.bz2 ext4"
