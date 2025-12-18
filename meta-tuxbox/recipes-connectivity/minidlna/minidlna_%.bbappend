FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
    file://minidlna.conf \
    file://minidlna.service \
"

CFLAGS:append = " -fcommon"

do_configure:prepend() {
    sed -i "s|Coolstream|${MACHINE}|" ${WORKDIR}/minidlna.conf
}

do_install:append() {
    install -m 0644 ${WORKDIR}/minidlna.conf ${D}${sysconfdir}/minidlna.conf
    install -m 0644 ${WORKDIR}/minidlna.service \
        ${D}${nonarch_base_libdir}/systemd/system/minidlna.service
}
