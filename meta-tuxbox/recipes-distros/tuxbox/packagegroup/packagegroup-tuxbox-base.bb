# Packagegroup: Tuxbox Base System
#
# Essential system packages for Tuxbox-OS (no GUI)

DESCRIPTION = "Tuxbox-OS base system packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    busybox \
    systemd \
    systemd-analyze \
    util-linux \
    util-linux-blkid \
    util-linux-fdisk \
    util-linux-mkfs \
    util-linux-mount \
    e2fsprogs \
    e2fsprogs-e2fsck \
    e2fsprogs-mke2fs \
    e2fsprogs-tune2fs \
    dosfstools \
    parted \
    openssh \
    openssh-sftp-server \
    opkg \
    curl \
    wget \
    ca-certificates \
    tzdata \
"

# Optional recommendations
RRECOMMENDS:${PN} = " \
    kernel-modules \
    udev-extraconf \
"
