FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

INHERIT:append = " ccache"
CCACHE_DIR:pn-samba = "${TMPDIR}/ccache/${PN}"

PR:append = ".1"

# Fix samba-common postinst to be POSIX-compatible (dash) and ensure /tmp exists
SRC_URI += "file://0001-fix-samba-common-postinst-posix-syntax.patch"
