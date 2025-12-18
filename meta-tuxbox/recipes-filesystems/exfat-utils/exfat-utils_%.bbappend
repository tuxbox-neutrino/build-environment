do_install:append() {
    install -d ${D}/sbin
    ln -s /usr/sbin/mkfs.exfat ${D}/sbin/mkfs.exfat
    ln -s /usr/sbin/fsck.exfat ${D}/sbin/fsck.exfat
}
