FILESEXTRAPATHS:prepend := "${THISDIR}/files:${THISDIR}/samba/tuxbox:"

INHERIT:append = " ccache"
CCACHE_DIR:pn-samba = "${TMPDIR}/ccache/${PN}"

PR:append = ".1"

# Fix samba-common postinst to be POSIX-compatible (dash) and ensure /tmp exists
SRC_URI += "file://0001-fix-samba-common-postinst-posix-syntax.patch"

# Package private Samba libraries to avoid QA "installed-vs-shipped"
PACKAGES += "${PN}-private-libs"
FILES:${PN}-private-libs = "${libdir}/samba/*.so*"
RDEPENDS:${PN} += "${PN}-private-libs"
INSANE_SKIP:${PN}-private-libs += "dev-so"
