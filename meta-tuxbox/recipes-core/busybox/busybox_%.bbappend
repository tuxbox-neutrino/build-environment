# Drop the default /etc/resolv.conf shipped by busybox to let systemd
# manage the symlink without update-alternatives errors.
do_install:append() {
    rm -f ${D}${sysconfdir}/resolv.conf
    # Drop unused systemd unit files to silence installed-vs-shipped QA
    rm -f ${D}${systemd_unitdir}/system/ftpd.service
    rm -f ${D}${systemd_unitdir}/system/telnet.service
    rm -rf ${D}${systemd_unitdir}/system/multi-user.target.wants
}
