SUMMARY = "Dummy ldconfig for external uClibc toolchain"
DESCRIPTION = "Provides a no-op ldconfig to satisfy runtime dependencies."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835c07b0a5f90e55de8b801f4b93f6b"

S = "${WORKDIR}"

do_compile[noexec] = "1"

do_install() {
    install -d ${D}${sbindir}
    cat > ${D}${sbindir}/ldconfig <<'EOF'
#!/bin/sh
exit 0
EOF
    chmod 0755 ${D}${sbindir}/ldconfig
}

FILES:${PN} = "${sbindir}/ldconfig"
