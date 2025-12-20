SUMMARY = "Shared library optimisation tool"
DESCRIPTION = "mklibs produces cut-down shared libraries that contain only the routines required by a particular set of executables."
HOMEPAGE = "https://launchpad.net/mklibs"
SECTION = "devel"
LICENSE = "GPLv2+"
LIC_FILES_CHKSUM = "file://debian/copyright;md5=98d31037b13d896e33890738ef01af64"

SRC_URI = " \
		http://deb.debian.org/debian/pool/main/m/mklibs/mklibs_${PV}.tar.xz \
		file://ac_init_fix.patch \
		file://fix_STT_GNU_IFUNC.patch \
		file://sysrooted-ldso.patch \
		file://avoid-failure-on-symbol-provided-by-application.patch \
		file://show-GNU-unique-symbols-as-provided-symbols.patch \
"

SRC_URI[md5sum] = "e3a8e51167d14aff4fbcf787370e3292"
SRC_URI[sha256sum] = "dd92a904b3942566f713fe536cd77dd1a5cfc62243c0e0bc6bb5d866e37422f3"

UPSTREAM_CHECK_URI = "${DEBIAN_MIRROR}/main/m/mklibs/"

inherit autotools gettext native


