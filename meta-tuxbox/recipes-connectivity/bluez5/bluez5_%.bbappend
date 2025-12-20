FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://bluetooth-poweron.service"

RDEPENDS:${PN} = "firmware-rtl8761b"

PACKAGECONFIG:append = " sixaxis"

do_install:append() {
	install -d ${D}${systemd_unitdir}/system/multi-user.target.wants
	install -m644 ${WORKDIR}/bluetooth-poweron.service ${D}${systemd_unitdir}/system
	ln -sf ${systemd_unitdir}/system/bluetooth-poweron.service ${D}${systemd_unitdir}/system/multi-user.target.wants
}
