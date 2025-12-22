PR:append:linux-uclibcgnueabi = ".2"

PROVIDES:append:linux-uclibcgnueabi = " virtual/libiconv"

do_configure:prepend:linux-uclibcgnueabi() {
    find ${S} -type f \( -name 'libtool.m4' -o -name 'lt*.m4' \) -delete
}
