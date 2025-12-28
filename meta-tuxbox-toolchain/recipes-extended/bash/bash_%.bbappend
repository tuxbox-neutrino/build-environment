# Fix getrandom function name conflict with uClibc

PR:append = ".1"

# uClibc provides getrandom() in sys/random.h which conflicts with bash's internal function
# Apply patch to rename bash's getrandom to sh_getrandom for external uClibc toolchain
# Note: Can't use :libc-uclibc override as it's not in OVERRIDES for external toolchain
SRC_URI:append = "${@' file://0001-rename-getrandom-to-avoid-uclibc-conflict.patch' if d.getVar('TCMODE') == 'external-coolstream' else ''}"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
