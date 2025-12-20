# Override problematic OE-Alliance base-files bbappend (perl -i -pe errors)
# meta-tuxbox has BBFILE_PRIORITY=11 (neutrino=10, oe-alliance=7)
# so we can neutralize their append and apply a minimal, safe tweak set.

PR:append = ".8"

# Drop any upstream/prepend/append fragments to avoid the perl snippets
do_install:append = ""
do_install:prepend = ""

# Add coreutils dependency to provide /bin/false for useradd
RDEPENDS:${PN}:append = " coreutils"

# Simple do_install extension: keep default base-files output, then apply our layout
do_install:append() {
    # Create basic directory structure for media mounts
    rm -rf ${D}/autofs || true
    rm -rf ${D}/mnt || true
    rm -rf ${D}/hdd || true
    mkdir -p ${D}/media/net ${D}/media/hdd
    ln -sf media/hdd ${D}/hdd
    ln -sf media ${D}/mnt
}
