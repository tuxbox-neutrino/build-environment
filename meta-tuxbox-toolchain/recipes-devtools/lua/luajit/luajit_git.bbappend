# Fix for external uClibc toolchain - kernel headers location

PR:append = ".1"

# For external toolchain, kernel headers are in the toolchain sysroot
do_configure:prepend() {
    if [ -d "${EXTERNAL_TOOLCHAIN_SYSROOT}/usr/include/asm" ]; then
        # Copy kernel headers from external toolchain sysroot
        mkdir -p ${STAGING_INCDIR_NATIVE}/asm
        cp -r ${EXTERNAL_TOOLCHAIN_SYSROOT}/usr/include/asm/* ${STAGING_INCDIR_NATIVE}/asm/ || true
    fi
}
