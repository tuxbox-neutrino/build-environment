PR:append:linux-uclibcgnueabi = ".2"

# libtirpc headers live under include/tirpc
CPPFLAGS:append:linux-uclibcgnueabi = " -I${RECIPE_SYSROOT}/usr/include/tirpc"
CFLAGS:append:linux-uclibcgnueabi = " -I${RECIPE_SYSROOT}/usr/include/tirpc"

# Disable NLS for uClibc toolchain builds.
EXTRA_OECONF:append:linux-uclibcgnueabi = " --disable-nls"

# Pull in libintl headers from the target provider.
DEPENDS:append:linux-uclibcgnueabi = " virtual/libintl"

# Link explicitly against libtirpc/libintl for uClibc builds.
EXTRA_OECONF:append:linux-uclibcgnueabi = " LIBS='-ltirpc -lintl'"
