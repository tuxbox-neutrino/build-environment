FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Fix samba-common postinst to be POSIX-compatible (dash) and ensure /tmp exists
SRC_URI += "file://0001-fix-samba-common-postinst-posix-syntax.patch"
