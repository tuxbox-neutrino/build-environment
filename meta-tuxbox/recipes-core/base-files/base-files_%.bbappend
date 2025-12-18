# OE-Alliance base-files uses `echo -e` in do_install; dash prints "-e" literally.
do_install:prepend() {
    echo() {
        if [ "$1" = "-e" ]; then
            shift
        fi
        if [ "$1" = "-n" ]; then
            shift
            printf '%s' "$*"
            return
        fi
        printf '%s\n' "$*"
    }
}

# Base-files should follow the MACHINE arch for Tuxbox builds, not MACHINEBUILD.
PACKAGE_ARCH:tuxbox = "${MACHINE_ARCH}"
