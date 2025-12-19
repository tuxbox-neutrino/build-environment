# Packagegroup: Tuxbox Neutrino Stack
#
# Neutrino GUI and related packages

DESCRIPTION = "Tuxbox-OS Neutrino GUI packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = " \
    neutrino \
    libstb-hal \
    neutrino-plugins \
"

# Themes
RRECOMMENDS:${PN} = " \
    neutrino-themes \
    neutrino-logos \
    neutrino-fonts-extra \
"
