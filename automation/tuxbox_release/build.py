"""Run one Yocto build per machine inside a throwaway container."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Config, Machine

#: Mirrors served from another host. They are referenced by absolute path
#: from builds/conf/local.conf.user.inc, so the container must see them
#: under the very same path.
MIRRORS = ("/mnt/sstate-mirror", "/mnt/downloads-mirror")


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
    for mirror in MIRRORS:
        if Path(mirror).is_dir():
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
