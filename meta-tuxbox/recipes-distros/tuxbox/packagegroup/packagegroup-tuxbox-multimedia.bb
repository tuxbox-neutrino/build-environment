# Packagegroup: Tuxbox Multimedia
#
# Multimedia framework and codecs

DESCRIPTION = "Tuxbox-OS multimedia packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    ffmpeg \
    gstreamer1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    alsa-utils \
    alsa-plugins \
"

# Optional multimedia tools
RRECOMMENDS:${PN} = " \
    minidlna \
    xupnpd \
"
