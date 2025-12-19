PACKAGE_ARCH = "${MACHINE_ARCH}"

do_install:prepend() {
    # The oe-alliance mountboot helper uses 'echo -e' which dash treats
    # as a literal string. Avoid aborting the task if that snippet fails;
    # we re-enable errexit below.
    set +e
}

# Drop the static /etc/resolv.conf from base-files so systemd's
# update-alternatives can create its own symlink without failing.
do_install:append() {
    set -e
    rm -f ${D}${sysconfdir}/resolv.conf
}
