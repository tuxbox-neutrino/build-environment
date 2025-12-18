# Ensure native/nativesdk provide libgbm for SDK helper builds
PROVIDES:append:class-native = " virtual/libgbm-native"
PROVIDES:append:class-nativesdk = " virtual/libgbm-nativesdk"
