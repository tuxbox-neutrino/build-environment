DESCRIPTION = "GNU libiconv provides an iconv() implementation for use on systems which don't have one, or whose implementation cannot convert from/to Unicode."
HOMEPAGE = "https://www.gnu.org/software/libiconv/"
SECTION = "libs"
LICENSE = "LGPLv2.1"
LIC_FILES_CHKSUM = "file://COPYING.LIB;md5=9f604d8a4f8e74f4f5140845a21b6674"

PV = "1.16"

SRC_URI = "https://ftp.gnu.org/pub/gnu/libiconv/libiconv-${PV}.tar.gz"
SRC_URI[md5sum] = "7d2a800b952942bb2880efb00cfd524c"
SRC_URI[sha256sum] = "e6a1b1b589654277ee790cce3734f07876ac4ccfaecbee8afa0b649cf529cc04"

S = "${WORKDIR}/libiconv-${PV}"

inherit autotools gettext lib_package

# For native use.
BBCLASSEXTEND = "native nativesdk"

PROVIDES += "libcharset"

EXTRA_OECONF = "--enable-shared"

do_install:append() {
  chrpath -d ${D}${bindir}/iconv
}
