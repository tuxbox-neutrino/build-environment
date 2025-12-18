LICENSE = "LGPL-2.1-or-later & MIT & BSD-3-Clause"

# Ensure required user/group parameters are defined for pulseaudio-server
USERADD_PACKAGES = "pulseaudio-server"
USERADD_PARAM:pulseaudio-server = "--system --home /var/run/pulse --no-create-home --shell /bin/false --groups audio,pulse --gid pulse pulse"
GROUPADD_PARAM:pulseaudio-server = "--system pulse"

FILES:${PN} = ""
ALLOW_EMPTY:${PN} = "1"

FILES:${PN}-pa-info = "${bindir}/pa-info"
RDEPENDS:${PN}-pa-info += "bash"

FILES:${PN}-server += "${systemd_system_unitdir}/* ${systemd_system_unitdir}/multi-user.target.wants/* ${systemd_user_unitdir}/*"
FILES:${PN}-misc += "${bindir}/* ${libdir}/pulseaudio/libpulsedsp.so ${datadir}/GConf"
FILES:${PN}-dev += "${datadir}/vala"
