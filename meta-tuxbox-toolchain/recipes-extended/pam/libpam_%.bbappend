# Fix for uClibc builds - add missing header includes

PR:append = ".1"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
    file://0001-pam_namespace-add-missing-includes-for-uclibc.patch \
"
