PR:append:linux-uclibcgnueabi = ".1"

do_compile:linux-uclibcgnueabi() {
    ${CC} ${CFLAGS} ${CPPFLAGS} -I${WORKDIR}/include \
        -c ${WORKDIR}/src/proxy-libintl/libintl.c -o ${B}/libintl.o
    ${AR} rcs ${B}/libintl.a ${B}/libintl.o
}

do_install:linux-uclibcgnueabi() {
    install -d ${D}${includedir} ${D}${libdir}
    install -m 0644 ${WORKDIR}/include/libintl.h ${D}${includedir}
    install -m 0644 ${B}/libintl.a ${D}${libdir}
}
