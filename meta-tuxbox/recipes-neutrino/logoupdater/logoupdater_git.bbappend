# Use fetched splash asset from WORKDIR and avoid runtime download in do_install
SPLASH_FILE = "${WORKDIR}/${SPLASH_PNG}"

do_install() {
    INSTALLDIR=${D}${N_LUAPLUGIN_DIR}
    install -d ${INSTALLDIR}

    if [ -f "${SPLASH_FILE}" ]; then
        install -m 644 ${SPLASH_FILE} ${INSTALLDIR}/${SRC_NAME}.png
    else
        bbwarn "logoupdater: splash file ${SPLASH_FILE} missing; skipping image install"
    fi

    install -m 755 ${S}/${SRC_NAME}.lua ${INSTALLDIR}/${SRC_NAME}.lua
    install -m 644 ${S}/${SRC_NAME}.cfg ${INSTALLDIR}/${SRC_NAME}.cfg
}
