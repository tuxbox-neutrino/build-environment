# Ensure required user/group parameters are defined for pulseaudio-server
USERADD_PACKAGES = "pulseaudio-server"
USERADD_PARAM:pulseaudio-server = "--system --home /var/run/pulse --no-create-home --shell /bin/false pulse"
GROUPADD_PARAM:pulseaudio-server = "--system pulse"
