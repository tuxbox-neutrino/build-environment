# Ensure libubox is available and help CMake find it
DEPENDS += "libubox"

EXTRA_OECMAKE += "-DUBOX_INCLUDE_DIR=${STAGING_INCDIR}"
