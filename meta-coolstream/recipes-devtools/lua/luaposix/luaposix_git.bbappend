# Coolstream HD2 (uClibc) uses external toolchain crypto
DEPENDS:remove:coolstream-hd2 = "libxcrypt"
DEPENDS:append:coolstream-hd2 = " virtual/crypt"

PR:append = ".3"
