# Tuxbox-OS Image Recipe
#
# Main image recipe for Tuxbox-OS with Neutrino

require tuxbox-image.inc

DESCRIPTION = "Tuxbox-OS Neutrino Image"
LICENSE = "MIT"

PV = "${DISTRO_VERSION}"
PR = "r1"

# Conditional large image packages (excluded on small flash devices)
# Placeholder for optional large-image extras (add real packagegroups later)
BIG_IMAGE_PACKAGES = ""

# Add big packages only if not small flash
IMAGE_INSTALL += "${@bb.utils.contains('IMAGESIZE', 'small', '', '${BIG_IMAGE_PACKAGES}', d)}"

# Image variant
IMAGE_BASENAME = "tuxbox-image"

# Avoid update-alternatives failure on /etc/resolv.conf during rootfs
rootfs_preprocess_resolvconf() {
    rm -f ${IMAGE_ROOTFS}/etc/resolv.conf || true
}
ROOTFS_PREPROCESS_COMMAND += " rootfs_preprocess_resolvconf;"
