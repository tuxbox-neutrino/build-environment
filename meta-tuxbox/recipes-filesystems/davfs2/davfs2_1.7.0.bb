DESCRIPTION = "A Linux file system driver that allows you to mount a WebDAV server as a disk drive."
SECTION = "network"
PRIORITY = "optional"
HOMEPAGE = "http://savannah.nongnu.org/projects/davfs2"
LICENSE = "GPL-3.0"
LIC_FILES_CHKSUM = "file://COPYING;md5=8f0e2cd40e05189ec81232da84bd6e1a"

RM_WORK_EXCLUDE += "${PN}"
PR = "r1"

DEPENDS = "gettext-native neon"
RDEPENDS:${PN} += "bash"
RRECOMMENDS:${PN} = "kernel-module-coda"

SRC_URI = "http://download.savannah.nongnu.org/releases/davfs2/${BP}.tar.gz \
		file://davfs2.mount.list \
		file://davfs2.service \
		file://mount.all.davfs \
		file://umount.all.davfs \
		\
		file://neon-config \
		file://volatiles \
"

SRC_URI[sha256sum] = "251db75a27380cca1330b1b971700c5e5dcc0c90e5a47622285f0140edfe3a2f"

inherit autotools pkgconfig useradd

USERADD_PACKAGES = "davfs2"
USERADD_PARAM:davfs2 = "--system --home /var/run/mount.davfs \
                        --no-create-home --shell /bin/false \
                        --user-group davfs2"

EXTRA_OECONF = "--with-neon \
                ac_cv_path_NEON_CONFIG=${WORKDIR}/neon-config"

CONFFILES:${PN} = "${sysconfdir}/davfs2/davfs2.conf ${sysconfdir}/davfs2/secrets ${sysconfdir}/davfs2/davfs2.mount.list"

do_install:prepend () {
	cp ${WORKDIR}/davfs2-${PV}/etc/davfs2.conf ${WORKDIR}/build/etc
	cp ${WORKDIR}/davfs2-${PV}/etc/secrets ${WORKDIR}/build/etc
}

do_install:append () {
        install -d ${D}${sysconfdir}/default/volatiles
        install -m 644 ${WORKDIR}/volatiles ${D}${sysconfdir}/default/volatiles/10_davfs2
        install -m 755 ${WORKDIR}/mount.all.davfs ${D}${sbindir}/mount.all.davfs
        install -m 755 ${WORKDIR}/umount.all.davfs ${D}${sbindir}/umount.all.davfs
        install -m 644 ${WORKDIR}/davfs2.mount.list ${D}${sysconfdir}/davfs2/davfs2.mount.list

        # system init
        install -d ${D}${sysconfdir}/systemd/system
        install -m 644 ${WORKDIR}/davfs2.service ${D}${sysconfdir}/systemd/system/davfs2.service
        local sbin_path=${sbindir}
	sed -i "s|@SBINPATH@|$sbin_path|" ${D}${sysconfdir}/systemd/system/davfs2.service

        rm -rf ${D}/usr/share/davfs2

	# modify configs
	sed -i 's/# backup_dir      lost+found/backup_dir      backup/' ${D}${sysconfdir}/davfs2/davfs2.conf
	sed -i 's/# use_compression 0/use_compression 1/' ${D}${sysconfdir}/davfs2/davfs2.conf
	sed -i 's/# use_locks       1/use_locks       0/' ${D}${sysconfdir}/davfs2/davfs2.conf
}


PACKAGE_NO_LOCALE = "1"

pkg_postinst_ontarget:${PN} () {
	if [ ! -d "/mnt/dav" ]; then
		echo "Directory /mnt/dav not exists. Create..."
		mkdir -pv /mnt/dav
	fi
}
