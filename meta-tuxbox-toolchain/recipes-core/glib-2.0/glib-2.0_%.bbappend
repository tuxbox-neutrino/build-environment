# Fix iconv linkage for external toolchain builds

PR:append = ".5"

# When using external toolchain, both target and native builds need explicit libiconv linkage
# Meson finds iconv during configure but doesn't add it to link flags
# Note: Can't use :libc-uclibc override as it's not in OVERRIDES for external toolchain
# Use LIBS instead of LDFLAGS for Meson builds
EXTRA_OEMESON:append = "${@' -Diconv=external' if d.getVar('TCMODE') == 'external-coolstream' else ''}"
LIBS:append = "${@' -liconv' if d.getVar('TCMODE') == 'external-coolstream' else ''}"

# Ensure libiconv is built before glib-2.0
DEPENDS:append = "${@' libiconv' if d.getVar('TCMODE') == 'external-coolstream' else ''}"
