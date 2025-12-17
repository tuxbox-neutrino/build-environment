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
    neutrino-plugins-lua \
    neutrino-webif \
"

# Themes
RRECOMMENDS:${PN} = " \
    neutrino-theme-neutrino-hd \
    neutrino-logos-tuxbox \
"

# Optional plugins
RRECOMMENDS:${PN} += " \
    neutrino-plugin-epgscan \
    neutrino-plugin-imgbackup \
    neutrino-plugin-tuxcom \
    neutrino-plugin-tuxwetter \
"
