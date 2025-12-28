# Ensure libpng is available for freetype with uClibc toolchain

PR:append = ".2"

# libpng is needed for pixmap PACKAGECONFIG (enabled by default)
DEPENDS:append = " libpng"

# freetype configure looks for libpng-config (deprecated) or pkg-config
# Ensure PKG_CONFIG finds libpng16
EXTRA_OECONF:append = " --with-png=yes LIBPNG_CFLAGS='-I${STAGING_INCDIR}' LIBPNG_LIBS='-L${STAGING_LIBDIR} -lpng16'"
