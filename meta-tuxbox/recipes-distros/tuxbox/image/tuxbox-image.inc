# Tuxbox-OS Image Base Include
#
# Common image configuration for all Tuxbox-OS image variants

require recipes-core/images/core-image-minimal.bb

LICENSE = "MIT"

# Image features
IMAGE_FEATURES += " \
    package-management \
    ssh-server-openssh \
    allow-empty-password \
    empty-root-password \
"

# Base packages from packagegroups
IMAGE_INSTALL:append = " \
    packagegroup-tuxbox-base \
    packagegroup-tuxbox-neutrino \
    ${@bb.utils.contains('MACHINE_FEATURES', 'wifi', 'packagegroup-tuxbox-wifi', '', d)} \
"

# Neutrino core stack
IMAGE_INSTALL:append = " \
    neutrino \
    libstb-hal \
    neutrino-plugins \
    neutrino-lua-plugins \
    neutrino-webif \
"

# Multimedia stack
IMAGE_INSTALL:append = " \
    packagegroup-tuxbox-multimedia \
"

# System tools
IMAGE_INSTALL:append = " \
    bash \
    htop \
    nano \
    vim-tiny \
    curl \
    wget \
    openssh \
    opkg \
    less \
    findutils \
    grep \
    procps \
"

# Networking
IMAGE_INSTALL:append = " \
    packagegroup-tuxbox-network \
"

# Filesystem support
IMAGE_INSTALL:append = " \
    e2fsprogs \
    e2fsprogs-mke2fs \
    e2fsprogs-tune2fs \
    dosfstools \
    ntfs-3g \
    ntfs-3g-ntfsprogs \
    exfat-utils \
    parted \
"

# Version file generation
inherit tuxbox-version

# Image size calculation
IMAGE_OVERHEAD_FACTOR ?= "1.3"
IMAGE_ROOTFS_SIZE ?= "262144"
IMAGE_ROOTFS_EXTRA_SPACE ?= "10240"

# Image rootfs post-processing
ROOTFS_POSTPROCESS_COMMAND += "tuxbox_rootfs_postprocess; "

tuxbox_rootfs_postprocess() {
    # Set default timezone
    if [ -e ${IMAGE_ROOTFS}${sysconfdir}/timezone ]; then
        echo "${DEFAULT_TIMEZONE}" > ${IMAGE_ROOTFS}${sysconfdir}/timezone
    fi

    # Create standard directories
    install -d ${IMAGE_ROOTFS}/media
    install -d ${IMAGE_ROOTFS}/media/usb
    install -d ${IMAGE_ROOTFS}/media/hdd
    install -d ${IMAGE_ROOTFS}/mnt

    # Set permissions
    chmod 755 ${IMAGE_ROOTFS}/media
    chmod 755 ${IMAGE_ROOTFS}/mnt
}

# Image type
IMAGE_FSTYPES += "tar.bz2"

# Optionally create ext4 image for eMMC devices
IMAGE_FSTYPES += "${@bb.utils.contains('MACHINE_FEATURES', 'emmc', 'ext4', '', d)}"
