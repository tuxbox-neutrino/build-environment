# Toolchain mode include for Coolstream external uClibc toolchain

require conf/distro/include/coolstream-external-toolchain.inc

# Pull in toolchain setup
INHERIT += "external-toolchain-coolstream"

# Avoid Yocto musl and cross-canadian SDK toolchains that conflict with the
# prebuilt uClibc toolchain.
BBMASK:append = "|.*/musl/.*|.*/cross-canadian/.*|.*/nativesdk-.*|.*/go-cross-.*|.*/rust-.*"
