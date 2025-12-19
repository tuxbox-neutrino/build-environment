# Ensure libubox is available and help the ad-hoc CMake call find it
DEPENDS += "libubox"

# Recipe calls cmake manually; hint include/lib paths explicitly.
do_configure:prepend() {
    export CMAKE_INCLUDE_PATH="${STAGING_DIR_HOST}${includedir}:${CMAKE_INCLUDE_PATH}"
    export CMAKE_LIBRARY_PATH="${STAGING_DIR_HOST}${libdir}:${CMAKE_LIBRARY_PATH}"
}
