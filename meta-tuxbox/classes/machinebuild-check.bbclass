# Enforce presence of MACHINE and MACHINEBUILD early in parsing
python __anonymous () {
    mach = (d.getVar('MACHINE') or "").strip()
    if not mach:
        bb.fatal("MACHINE is not set. Please set MACHINE in local.conf or the environment.")

    mb = (d.getVar('MACHINEBUILD') or "").strip()
    if not mb:
        bb.fatal("MACHINEBUILD is not set. Please set MACHINEBUILD to the OEM/brand identifier "
                 "(e.g. mutant51, mutant60, mutant61) in local.conf or the environment.")
}
