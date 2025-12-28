# uClibc does not support NETGROUP functions (like musl)

PR:append = ".2"

# Disable NETGROUP for uClibc builds (similar to musl)
# Note: Can't use :libc-uclibc override as it's not in OVERRIDES for external toolchain
EXTRA_OEMAKE_NETGROUP = "${@'-DUSE_GETDOMAIN' if d.getVar('TCLIBC') == 'uclibc' else '-DNETGROUP -DUSE_GETDOMAIN'}"
