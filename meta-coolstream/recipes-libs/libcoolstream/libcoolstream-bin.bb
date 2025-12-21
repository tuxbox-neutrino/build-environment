SUMMARY = "Prebuilt libcoolstream/libnxp binaries for Coolstream targets"
DESCRIPTION = "Closed-source runtime libraries for Coolstream STBs (no sources)."
LICENSE = "CLOSED"
LIC_FILES_CHKSUM = ""

SRC_URI = "git://github.com/tuxbox-neutrino/drivers-bin-cst.git;protocol=https;branch=master"
SRCREV = "146403d83abf7bf996845f14da22142081994e65"

S = "${WORKDIR}/git"

PV = "3.2.16+git${SRCPV}"
PACKAGE_ARCH = "${MACHINE_ARCH}"
COMPATIBLE_MACHINE = "(coolstream-nevis|coolstream-apollo|coolstream-shiner|coolstream-kronos|coolstream-kronos-v2)"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

python __anonymous() {
    m = d.getVar("MACHINE") or ""
    if m in ("coolstream-apollo", "coolstream-shiner"):
        d.setVar("CST_SUBDIR", "apollo-3.x")
        d.setVar("CST_LIBC", "uclibc")
    elif m in ("coolstream-kronos", "coolstream-kronos-v2"):
        d.setVar("CST_SUBDIR", "kronos-3.x")
        d.setVar("CST_LIBC", "uclibc")
    elif m == "coolstream-nevis":
        d.setVar("CST_SUBDIR", "nevis")
        d.setVar("CST_LIBC", "glibc")
    else:
        bb.fatal("Unsupported MACHINE for libcoolstream-bin: %s" % m)
}

do_install() {
    install -d ${D}${libdir}

    # Core libs (uClibc or glibc, depending on subdir)
    if [ -d ${S}/${CST_SUBDIR}/libs ]; then
        cp -a ${S}/${CST_SUBDIR}/libs/*.so* ${D}${libdir}/
    fi

    # Optional glibc variants (libs-eglibc) if present
    if [ "${CST_LIBC}" = "glibc" ] && [ -d ${S}/${CST_SUBDIR}/libs-eglibc ]; then
        cp -a ${S}/${CST_SUBDIR}/libs-eglibc/*.so* ${D}${libdir}/
    fi

    # libcoolstream from ffmpeg 5.1 build (latest provided)
    if [ -d ${S}/${CST_SUBDIR}/libs-ffmpeg-5.1 ]; then
        cp -a ${S}/${CST_SUBDIR}/libs-ffmpeg-5.1/libcoolstream.so* ${D}${libdir}/
    fi
}

FILES:${PN} = "${libdir}/*"

# Binaries are pre-stripped and link against uClibc/glibc as delivered
INSANE_SKIP:${PN} += "ldflags already-stripped dev-so textrel"
