# Add missing gnu-config-native dependency

PR:append = ".3"

DEPENDS += "gnu-config-native"

# x264's configure doesn't understand --disable-static
# The recipe already has --enable-static in EXTRA_OECONF
DISABLE_STATIC = ""

# Fix obsolete LICENSE identifier
LICENSE = "GPL-2.0-only"
