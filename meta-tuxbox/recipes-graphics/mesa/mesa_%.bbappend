# Ensure native/nativesdk provide libgbm for SDK helper builds
PROVIDES:append:class-native = " virtual/libgbm-native"
PROVIDES:append:class-nativesdk = " virtual/libgbm-nativesdk"

# Limit egl-native providers to native/nativesdk to avoid provider warnings
PROVIDES:remove:class-target = "virtual/egl-native virtual/nativesdk-egl"
PROVIDES:append:class-native = " virtual/egl-native"
PROVIDES:append:class-nativesdk = " virtual/nativesdk-egl"
