# uClibc builds need an OpenSSL target that Configure understands.
# Map HOST_OS to a gnueabi variant so the recipe selects linux-armv4.
HOST_OS:pn-openssl:linux-uclibcgnueabi = "linux-gnueabi"

# Avoid double-prefixing the compiler in OpenSSL builds.
CROSS_COMPILE:pn-openssl:linux-uclibcgnueabi = ""

do_configure:prepend:linux-uclibcgnueabi() {
    unset CROSS_COMPILE
}

# uClibc lacks ucontext, disable async.
EXTRA_OECONF:append:linux-uclibcgnueabi = " no-async"

PR:append = ".6"
