# Relax logomask warnings that break with -Werror=format-security, -Wshadow etc.
# This mirrors existing upstream warning profile but avoids fatal builds on Kirkstone.
TARGET_CFLAGS:append = " -Wno-shadow -Wno-array-bounds -Wno-unused-parameter -Wno-unused-variable"
