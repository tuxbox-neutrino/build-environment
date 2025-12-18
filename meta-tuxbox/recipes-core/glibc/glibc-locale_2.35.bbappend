# Make glibc-locale robust when the binary locale stash is absent
# (ENABLE_BINARY_LOCALE_GENERATION=0). Ensure target dirs exist and
# fall back to a stub SUPPORTED file instead of failing.
do_install() {
    install -d ${D}${libdir} ${D}${datadir}/locale

    copy_locale_files ${bindir} 0755
    copy_locale_files ${localedir} 0644
    if [ ${PACKAGE_NO_GCONV} -eq 0 ]; then
        copy_locale_files ${libdir}/gconv 0755
        copy_locale_files ${datadir}/i18n 0644
    fi
    # Remove empty dirs in libdir when gconv or locales are not copied
    find ${D}${libdir} -type d -empty -delete || true
    copy_locale_files ${datadir}/locale 0644

    if [ -f ${LOCALETREESRC}/SUPPORTED ]; then
        install -m 0644 ${LOCALETREESRC}/SUPPORTED ${WORKDIR}/SUPPORTED
    else
        bbwarn "glibc-locale: ${LOCALETREESRC}/SUPPORTED missing; installing stub"
        install -d ${WORKDIR}
        echo "# stub SUPPORTED; binary locale stash missing" > ${WORKDIR}/SUPPORTED
    fi
}

# Skip binary-locale staging cleanly when the stash is absent to avoid tar errors
do_prep_locale_tree() {
    if [ ! -d "${LOCALETREESRC}/usr/share" ]; then
        bbwarn "glibc-locale: skipping prep_locale_tree; ${LOCALETREESRC}/usr/share missing"
        return 0
    fi

    rm -rf ${WORKDIR}/locale-tree
    mkdir -p ${WORKDIR}/locale-tree
    tar -C ${LOCALETREESRC} -cf - usr/share | tar -C ${WORKDIR}/locale-tree -xf -
}
