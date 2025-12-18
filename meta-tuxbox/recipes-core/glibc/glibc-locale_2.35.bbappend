# Ensure locale install step has required libdir path available
do_install:prepend() {
    install -d ${D}${libdir}
}
