# Packagegroup: Tuxbox Network
#
# Network services and tools

DESCRIPTION = "Tuxbox-OS network packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    openssh \
    openssh-sftp-server \
    nfs-utils \
    nfs-utils-client \
    samba \
    avahi-daemon \
    avahi-utils \
    ethtool \
    iputils-ping \
    iproute2 \
    iptables \
    tcpdump \
"

RRECOMMENDS:${PN} = " \
    wget \
    curl \
    rsync \
"
