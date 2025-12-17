# Packagegroup: Coolstream Tank specific packages

DESCRIPTION = "Coolstream Tank hardware support packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    firmware-coolstream \
    coolstream-drivers \
    libstb-hal-coolstream \
"

# Optional Coolstream tools
RRECOMMENDS:${PN} = " \
    coolstream-tools \
    coolstream-utils \
"
