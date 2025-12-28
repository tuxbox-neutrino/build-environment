# Fix obsolete LICENSE identifier (upstream already uses SPDX format)

PR:append = ".4"

LICENSE = "LGPL-2.1-only"

# Ensure virtual/libiconv is provided
PROVIDES += "virtual/libiconv"

# Need gettext-native for AM_LANGINFO_CODESET macro during autoreconf
DEPENDS:append = " gettext-native"

# Regenerate build files with current libtool to fix version mismatch
# External toolchain has libtool 2.4.6, OE native has 2.4.7
inherit autotools-brokensep

EXTRA_AUTORECONF = "-I ${STAGING_DATADIR_NATIVE}/aclocal"
