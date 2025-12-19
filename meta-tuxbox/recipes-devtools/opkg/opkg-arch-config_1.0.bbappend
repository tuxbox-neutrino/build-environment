# Make opkg-arch-config arch-independent to avoid machine-specific sstate gaps
inherit allarch
PACKAGE_ARCH = "allarch"
