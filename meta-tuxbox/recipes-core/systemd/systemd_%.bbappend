FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
		file://0001-avoid-race-between-systemd-udevd-and-systemd-modules.patch \
		file://service \
		"
		
do_patch[postfuncs] = ""

do_install:append() {
	install -d ${D}${sbindir}
	install -m 0755 ${WORKDIR}/service ${D}${sbindir}/
}

FILES:${PN} += "\
	${sbindir} \
"
