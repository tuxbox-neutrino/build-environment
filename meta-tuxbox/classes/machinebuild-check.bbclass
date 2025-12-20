# Ensure that MACHINE and MACHINEBUILD are set; both are mandatory.
python __anonymous () {
    mach = (d.getVar('MACHINE') or "").strip()
    if not mach:
        bb.fatal("MACHINE ist nicht gesetzt. Bitte in local.conf (oder per Umgebung) setzen.")

    mb = (d.getVar('MACHINEBUILD') or "").strip()
    if not mb:
        bb.fatal("MACHINEBUILD ist nicht gesetzt. Bitte in local.conf (oder per Umgebung) "
                 "auf den OEM/Brand-Identifier setzen (z.B. mutant51, mutant60, mutant61, ...).")
}
