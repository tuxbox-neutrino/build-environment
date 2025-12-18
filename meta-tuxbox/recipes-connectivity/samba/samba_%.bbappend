# Samba waf configure does not support --disable-static
DISABLE_STATIC = ""
EXTRA_OECONF:remove = "--disable-static"
CONFIGUREOPTS:remove = "--disable-static"
