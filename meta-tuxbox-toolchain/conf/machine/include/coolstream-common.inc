# Common Coolstream machine configuration

# SOC Family
SOC_FAMILY = "coolstream"

# Machine class
MACHINE_CLASS = "stb"

# External toolchain
require conf/distro/include/coolstream-external-toolchain.inc

# Preferred providers
PREFERRED_PROVIDER_virtual/kernel = "linux-coolstream"
PREFERRED_PROVIDER_virtual/libstb-hal = "libstb-hal-coolstream"

# MTD support
MACHINE_FEATURES += "mtd"

# Kernel modules
MACHINE_ESSENTIAL_EXTRA_RRECOMMENDS = " \
    kernel-module-dvb-core \
    kernel-module-coolstream-dvb \
"

# Build configuration
MACHINE_FEATURES_BACKFILL_CONSIDERED += "rtc"
