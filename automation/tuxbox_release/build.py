"""Run one Yocto build per machine inside a throwaway container."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Config, Machine

def mounted_types(proc_mounts: str) -> dict[str, str]:
    """Mount point -> filesystem type, as /proc/mounts spells it."""
    types = {}
    for line in proc_mounts.splitlines():
        fields = line.split(" ")
        if len(fields) >= 3:
            types[fields[1]] = fields[2]
    return types


def mirror_is_usable(path: Path) -> bool:
    """True only when the mirror is really mounted right now.

    Two traps sit here, and h7 walked into both on 2026-09-23 while red was
    switched off. The mirrors arrive over NFS with x-systemd.automount, so
    the directory exists whether or not anything is mounted - Path.is_dir()
    says yes either way, docker then refuses the bind mount with "no such
    device" and takes the whole build with it. And an idle trigger whose
    server is gone still appears in /proc/mounts, just with fstype autofs.

    Reading /proc/mounts answers both without ever touching the directory.
    That last part matters: any stat on a dead trigger blocks for as long
    as the mount attempt runs, which was minutes, not the configured ten
    seconds.
    """
    try:
        proc_mounts = Path("/proc/mounts").read_text(encoding="utf-8")
    except OSError:
        return False
    return mounted_types(proc_mounts).get(str(path)) not in (None, "autofs")


def container_command(cfg: Config, machine: Machine) -> list[str]:
    """Assemble the docker invocation for one machine.

    The build tree is mounted read-write; TMPDIR lives on the SSD while
    downloads and sstate stay shared so the second and third machine of a
    run are much cheaper than the first. No secret is passed in - the
    container never talks to GitHub.

    The TMPDIR target path is not a guess: "bitbake -e" reports
    TMPDIR="/work/builds/<machine>/tmp" for this build layout. Mounting
    anywhere else would leave the SSD unused and quietly put the heaviest
    I/O back onto a spinning disk.
    """
    tmpdir = cfg.tmp_root / f"tmp-{machine.machine}"
    distro_type = "release" if cfg.channel == "release" else "development"
    inner = (
        "./cli.py build "
        f"--machine {machine.machine} "
        f"--machinebuild {machine.machinebuild} "
        "--distro tuxbox "
        f"--distro-type {distro_type}"
    )

    mounts = [
        f"{cfg.checkout}:/work",
        f"{cfg.work_root / 'downloads'}:/work/downloads",
        f"{cfg.work_root / 'sstate-cache'}:/work/sstate-cache",
        f"{tmpdir}:/work/builds/{machine.machine}/tmp",
    ]
    # A mirror that is not mounted on the host is simply left out: a missing
    # mirror is a cache miss, but a bind mount of a missing path would make
    # docker refuse to start at all.
    # Mirrors are referenced by absolute path from the build configuration,
    # so the container has to see them under the very same path.
    for mirror in cfg.mirrors:
        if mirror_is_usable(Path(mirror)):
            mounts.append(f"{mirror}:{mirror}:ro")

    command = ["docker", "run", "--rm"]
    for mount in mounts:
        command += ["-v", mount]
    command += ["-w", "/work", cfg.image, "/bin/bash", "-lc", inner]
    return command


def build_machine(cfg: Config, machine: Machine, log_path: Path) -> int:
    """Build one machine, streaming everything into log_path."""
    (cfg.tmp_root / f"tmp-{machine.machine}").mkdir(parents=True, exist_ok=True)
    # Create the bind-mount target ourselves. Docker would create a missing
    # one too, but the daemon runs as root - and cli.py, running as the build
    # user, then cannot create builds/<machine>/conf next to the mount.
    (cfg.checkout / "builds" / machine.machine).mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        process = subprocess.run(
            container_command(cfg, machine),
            stdout=log, stderr=subprocess.STDOUT, check=False,
        )
    return process.returncode


def cleanup_tmpdir(cfg: Config, machine: Machine) -> None:
    """Drop one machine's TMPDIR once its artefacts are safely collected.

    The SSD holds 109 GB and cannot carry three full TMPDIRs at once, so
    each machine's tree goes as soon as it is no longer needed. This is
    cheap to undo: everything worth keeping is in the shared sstate cache,
    so a later rebuild of the same machine reuses it instead of starting
    over.
    """
    shutil.rmtree(cfg.tmp_root / f"tmp-{machine.machine}", ignore_errors=True)


def free_gb(path: Path) -> int:
    """Free space in GB, for the decision whether the next machine fits."""
    return shutil.disk_usage(path).free // (1024 ** 3)
