# Relax warnings that break build with hardening flags
TARGET_CFLAGS:append = " -Wno-format-security -Wno-format-overflow -Wno-sign-compare -Wno-pointer-sign"
