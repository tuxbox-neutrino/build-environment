# PIC can't be enabled for arm
INSANE_SKIP_${PN}:append_arm = " textrel"
