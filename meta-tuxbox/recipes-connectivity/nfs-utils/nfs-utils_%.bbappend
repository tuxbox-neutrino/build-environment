FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://exports \
" 

RDEPENDS:${PN} = "${PN}-client"

do_install:append() {
	install -m 644 ${WORKDIR}/exports ${D}${sysconfdir}
	chgrp 0 ${D}/var/lib/nfs/statd/state
}
        
INSANE_SKIP:${PN} = "file-rdeps"
