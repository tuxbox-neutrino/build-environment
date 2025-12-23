PR:append = ".2"
DEPENDS:append = " gnu-config-native"
EXTRA_OECONF:append = " --sysroot=${EXTERNAL_TOOLCHAIN_SYSROOT}"
