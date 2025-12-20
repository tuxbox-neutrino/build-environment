# PIC can't be enabled for arm
INSANE_SKIP:${PN}:append:arm = " textrel"
