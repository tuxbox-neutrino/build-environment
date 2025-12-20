do_install:append() {
    install -d ${D}${systemd_unitdir}/system/sockets.target.wants \
               ${D}${systemd_unitdir}/system/multi-user.target.wants
    ln -sf ${systemd_unitdir}/system/rpcbind.socket ${D}${systemd_unitdir}/system/sockets.target.wants/rpcbind.socket
    ln -sf ${systemd_unitdir}/system/rpcbind.service ${D}${systemd_unitdir}/system/multi-user.target.wants/rpcbind.service
}
