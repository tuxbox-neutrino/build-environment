# Samba waf configure does not support --disable-static
DISABLE_STATIC = ""
EXTRA_OECONF:remove = "--disable-static"
CONFIGUREOPTS:remove = "--disable-static"

python __anonymous() {
    extra = d.getVar("EXTRA_OECONF") or ""
    if "--disable-static" in extra:
        extra = " ".join([x for x in extra.split() if x != "--disable-static"])
        d.setVar("EXTRA_OECONF", extra)
}
