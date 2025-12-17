# Packagegroup: Tuxbox WiFi
#
# WiFi support and wireless drivers

DESCRIPTION = "Tuxbox-OS WiFi support packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    wpa-supplicant \
    iw \
    wireless-tools \
    bluez5 \
"

# Common WiFi drivers
RRECOMMENDS:${PN} = " \
    kernel-module-carl9170 \
    kernel-module-rt2800usb \
    kernel-module-rtl8192cu \
    kernel-module-zd1211rw \
    linux-firmware-rtl8192cu \
    linux-firmware-rt2870 \
    linux-firmware-zd1211 \
"
