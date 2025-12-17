# Example recipe for meta-local
# This shows how to add custom recipes to your build

DESCRIPTION = "Example custom recipe"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# This is just an example - does not actually build anything
# Replace with your actual recipe content

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    # Example: install a configuration file
    # install -d ${D}${sysconfdir}
    # install -m 0644 ${WORKDIR}/myconfig.conf ${D}${sysconfdir}/
    :
}

# To use this recipe, copy and modify for your needs
# Then add to your image: IMAGE_INSTALL += "example"
