PR:append:linux-uclibcgnueabi = ".1"

# Avoid executing target-built stage1flex during cross compilation.
EXTRA_OECONF:append:linux-uclibcgnueabi = " --disable-bootstrap"
