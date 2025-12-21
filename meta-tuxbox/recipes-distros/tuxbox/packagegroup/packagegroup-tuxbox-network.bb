# Packagegroup: Tuxbox Network
#
# Network services and tools

DESCRIPTION = "Tuxbox-OS network packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    openssh \
    openssh-sftp-server \
    samba \
    nfs-utils \
    nfs-utils-client \
    avahi-daemon \
    avahi-utils \
    ethtool \
    iputils-ping \
    iproute2 \
    iptables \
    tcpdump \
"
#    samba \  # Temporarily disabled due to postinst bash syntax issues

RRECOMMENDS:${PN} = " \
    wget \
    curl \
    rsync \
"
