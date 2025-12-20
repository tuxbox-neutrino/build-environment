FILESEXTRAPATHS:prepend := "${THISDIR}/files:${THISDIR}/samba/tuxbox:"

INHERIT:append = " ccache"
CCACHE_DIR:pn-samba = "${TMPDIR}/ccache/${PN}"

PR:append = ".1"

# Package private Samba libraries to avoid QA "installed-vs-shipped"
PACKAGES += "${PN}-private-libs"
FILES:${PN}-private-libs = "${libdir}/samba/*.so*"
RDEPENDS:${PN} += "${PN}-private-libs"
INSANE_SKIP:${PN}-private-libs += "dev-so"

# Replace samba-common postinst/prerm/postrm with POSIX-safe versions
pkg_postinst:${BPN}-common = "\
#!/bin/sh\n\
set +e\n\
mkdir -p $D/tmp\n\
grep -v 'pam_smbpass.so' $D/etc/pam.d/common-password > $D/tmp/common-password\n\
if [ -e $D/tmp/common-password ]; then\n\
    mv $D/tmp/common-password $D/etc/pam.d/common-password\n\
fi\n\
echo \"password\\toptional\\t\\t\\tpam_smbpass.so use_authtok use_first_pass\" >> $D/etc/pam.d/common-password\n\
\n\
grep -qE '^kids:' $D/etc/passwd\n\
if [ $? -ne 0 ]; then\n\
    echo 'kids:x:500:500:Linux User,,,:/media:/bin/false' >> $D/etc/passwd\n\
    echo 'kids:!:16560:0:99999:7:::' >> $D/etc/shadow\n\
fi\n\
\n\
if [ -e $D/etc/samba/distro/smb-vmc.vmc ]; then\n\
    rm $D/etc/samba/distro/smb-vmc.conf 2>/dev/null || true\n\
    ln -s smb-vmc.vmc $D/etc/samba/distro/smb-vmc.conf\n\
else\n\
    rm $D/etc/samba/distro/smb-vmc.conf 2>/dev/null || true\n\
    ln -s smb-vmc.samba $D/etc/samba/distro/smb-vmc.conf\n\
fi\n\
\n\
if [ -z \"$D\" ]; then\n\
    set +e\n\
    [ -e /etc/samba/private/smbpasswd ] || touch /etc/samba/private/smbpasswd\n\
\n\
    grep -qE '^root:' /etc/samba/private/smbpasswd\n\
    if [ $? -ne 0 ]; then\n\
        smbpasswd -Ln root >/dev/null\n\
    fi\n\
\n\
    grep -qE '^kids:' /etc/passwd\n\
    if [ $? -ne 0 ]; then\n\
        adduser -h /media -s /bin/false -H -D -u 500 kids 2>/dev/null || adduser -h /media -s /bin/false -H -D kids\n\
    fi\n\
\n\
    grep -qE '^kids:' /etc/samba/private/smbpasswd\n\
    if [ $? -ne 0 ]; then\n\
        smbpasswd -Ln kids >/dev/null\n\
    fi\n\
fi\n\
"

pkg_prerm:${BPN}-common = "\
#!/bin/sh\n\
mkdir -p $D/tmp\n\
grep -v 'pam_smbpass.so' $D/etc/pam.d/common-password > $D/tmp/common-password\n\
mv $D/tmp/common-password $D/etc/pam.d/common-password\n\
"

pkg_postrm:${BPN}-common = "\
#!/bin/sh\n\
rm $D/etc/samba/distro/smb-vmc.conf 2>/dev/null || true\n\
"
