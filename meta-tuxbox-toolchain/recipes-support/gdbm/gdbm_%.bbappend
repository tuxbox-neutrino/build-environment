# Fix for uClibc builds - define blksize_t if not available

PR:append = ".1"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
    file://0001-gdbmopen-define-blksize_t-for-uclibc.patch \
"
