DESCRIPTION = "Firmware for rtl8761b"

SRC_URI = "file://rtl8761b_config.bin \
	   file://rtl8761b_fw.bin \
	   file://license \
"

LICENSE = "CLOSED"
LIC_FILES_CHKSUM = "file://${LAYERDIR}/files/custom-licenses/LICENSE-CLOSE;md5=2d5b03b35d4612637d67724b35738dd7"


do_install() {
	install -d ${D}${nonarch_base_libdir}/firmware/rtl_bt
	install -m 644 ${WORKDIR}/rtl8761b_config.bin ${D}${nonarch_base_libdir}/firmware/rtl_bt
	install -m 644 ${WORKDIR}/rtl8761b_fw.bin ${D}${nonarch_base_libdir}/firmware/rtl_bt
}

FILES:${PN} = "${nonarch_base_libdir}/firmware/rtl_bt"
