# Ensure systemd unit directory exists before install
do_install:prepend() {
    install -d ${D}${systemd_unitdir}/system
}
