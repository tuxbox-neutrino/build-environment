# Coolstream HD2 (uClibc): drop GStreamer stack (no libgles2 provider)
RDEPENDS:${PN}:remove:coolstream-hd2 = "gstreamer1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav"

PR:append = ".2"
