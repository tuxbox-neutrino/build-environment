SUMMARY = "Tvheadend TV streaming server"
HOMEPAGE = "https://tvheadend.org"

DEPENDS = "avahi cmake-native dvb-apps libdvbcsa libopus libpcre2 openssl uriparser zlib ffmpeg nasm"

LICENSE = "GPLv3+"
LIC_FILES_CHKSUM = "file://LICENSE.md;md5=4d88651adbf587ba207e620d5e271672"


inherit gettext autotools-brokensep pkgconfig gitpkgv
#USED_TAG = "4.3"
SRCREV = "${AUTOREV}"
PR = "r1"
#PV = "4.3.${SRCPV}"
PKGV = "${GITPKGVTAG}"

# We have more than one repository and it is sure that the second repository contains no tags, so we
# must suppress warnings for that.
GITPKGVTAG_NO_WARN_ON_NO_TAG = "1"

SRCREV:tvheadend = "${AUTOREV}"
SRCREV:tvheadend-packaging = "${AUTOREV}"
SRCREV_FORMAT = "tvheadend"

S = "${WORKDIR}/${PN}"

SRC_URI = "git://github.com/tvheadend/tvheadend.git;name=tvheadend;protocol=https;destsuffix=${BPN};branch=master \
	   git://github.com/tuxbox-fork-migrations/recycled-tvheadend-packaging.git;name=tvheadend-packaging;protocol=https;destsuffix=${BPN}-packaging;branch=master \
	   file://0001-tvheadend.service_adjustments_for_stb_environment.patch \
"

do_patch() {
    service_patch="${WORKDIR}/0001-tvheadend.service_adjustments_for_stb_environment.patch"
    service_repo="${WORKDIR}/tvheadend-packaging"
    if git -C "$service_repo" apply --check "$service_patch"; then
        git -C "$service_repo" apply "$service_patch"
    fi
    sed -i -e 's/0.0.0-unknown/${PKGV}-${PR}/g' -e 's/0.0.0~unknown/${PKGV}-${PR}/g' "${WORKDIR}/tvheadend/support/version"
}

EXTRA_OECONF += "--arch=${TARGET_ARCH} \
		--enable-nvenc \
		--enable-cardclient \
		--enable-mmal \
		--enable-ffmpeg \
		--disable-ffmpeg_static \
		--enable-inotify \
		--enable-pcre2 \
		--enable-uriparser \
		--enable-tvhcsa \
		--enable-bundle \
		--enable-dvbcsa \
		--enable-kqueue \
		--enable-libvpx \
		--enable-libopus \
		--enable-ddci \
		--python=python3 \
                 "


do_install:append() {
	install -d ${D}${systemd_unitdir}/system
	install -m 0644 ${WORKDIR}/${PN}-packaging/systemd/${PN}.service ${D}${systemd_unitdir}/system/${PN}.service
}

FILES:${PN} += "${systemd_unitdir}"

CLEANBROKEN = "1"


pkg_preinst_${PN} () {
    #!/bin/sh
    # Check if running
    if [ -z "$D" ]; then
        # stop tvheadend service if running
        systemctl stop tvheadend || true
    fi
}


pkg_postinst_${PN} () {
    #!/bin/sh
    # When installed on an actual device (not during the build process)
    if [ -n "$D" ]; then
        exit 1
    fi
    
    systemctl daemon-reload
}
