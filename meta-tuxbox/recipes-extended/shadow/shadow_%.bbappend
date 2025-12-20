do_install:append() {
    # Remove deprecated syslog options from login.defs that cause warnings in systemd environments.
    # SYSLOG_SU_ENAB and SYSLOG_SG_ENAB are no longer supported by shadow-utils when built
    # with systemd support, and their presence causes "configuration error" messages during
    # package installation (useradd/usermod calls in postinsts), leading to opkg returning
    # exit code 255 even though the installation succeeds.
    if [ -f ${D}${sysconfdir}/login.defs ]; then
        sed -i '/^SYSLOG_SU_ENAB/d' ${D}${sysconfdir}/login.defs
        sed -i '/^SYSLOG_SG_ENAB/d' ${D}${sysconfdir}/login.defs
    fi
}
