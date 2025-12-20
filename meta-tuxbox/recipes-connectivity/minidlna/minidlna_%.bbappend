FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
    file://minidlna.conf \
    file://minidlna.service \
"

PR:append = ".1"

CFLAGS:append = " -fcommon"

do_configure:prepend() {
    sed -i "s|Coolstream|${MACHINE}|" ${WORKDIR}/minidlna.conf
}

do_install:append() {
    install -m 0644 ${WORKDIR}/minidlna.conf ${D}${sysconfdir}/minidlna.conf
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/minidlna.service \
        ${D}${systemd_unitdir}/system/minidlna.service
}

FILES:${PN} += "${systemd_unitdir}/system/minidlna.service"
