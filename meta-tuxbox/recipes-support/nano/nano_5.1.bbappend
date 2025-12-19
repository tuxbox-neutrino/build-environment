# SPDX and QA tweaks for nano
LICENSE = "GPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://COPYING;md5=f27defe1e96c2e1ecd4e0c9be8967949"

# Disable alternatives to /bin/editor (we only ship /usr/bin/nano)
ALTERNATIVE_${PN} = ""

# Avoid installing unused /home tree
do_install:append() {
    rm -rf ${D}/home
}
