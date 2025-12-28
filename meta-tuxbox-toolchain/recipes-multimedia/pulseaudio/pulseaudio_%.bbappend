# Remove systemd dependency for uClibc builds

PR:append = ".1"

# Make systemd dependency conditional
DEPENDS:remove = "${@bb.utils.contains('DISTRO_FEATURES', 'systemd', '', 'systemd', d)}"
PACKAGECONFIG:remove = "${@bb.utils.contains('DISTRO_FEATURES', 'systemd', '', 'systemd', d)}"
