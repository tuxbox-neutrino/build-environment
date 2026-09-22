"""Collect and verify the artefacts of one machine build."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, Machine

#: The three files a user actually flashes. The raw .ext4 is ~580 MB and has
#: no audience, so it stays out of the release.
ASSET_SUFFIXES = ("_recovery_emmc.zip", "_multi.zip", ".tuxbox.tar.bz2")


@dataclass
class MachineArtifacts:
    machine: str
    image_version: str
    assets: list[Path] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    #: Yocto image manifest ("<image>.tuxbox.manifest") - the package list.
    package_manifest: Path | None = None


def _to_host_path(cfg: Config, machine: Machine, container_path: str) -> Path:
    """Translate a /work/... path reported inside the container to the host.

    TMPDIR is bind-mounted from the SSD, so everything below
    /work/builds/<machine>/tmp lives somewhere else on the host than the
    container reports.
    """
    tmp_prefix = f"/work/builds/{machine.machine}/tmp"
    if container_path.startswith(tmp_prefix):
        rest = container_path[len(tmp_prefix):].lstrip("/")
        return cfg.tmp_root / f"tmp-{machine.machine}" / rest if rest \
            else cfg.tmp_root / f"tmp-{machine.machine}"
    if container_path.startswith("/work"):
        rest = container_path[len("/work"):].lstrip("/")
        return cfg.checkout / rest if rest else cfg.checkout
    return Path(container_path)


def deploy_info(cfg: Config, machine: Machine) -> dict:
    """Ask cli.py where this machine's artefacts are. Never guess paths.

    This must run inside the container: on the host, cli.py resolves the
    layer paths wrongly and reports FAIL with "missing brand layer
    /oe-alliance/...". The paths it returns are container paths and are
    translated back afterwards.
    """
    result = subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{cfg.checkout}:/work",
         "-v", f"{cfg.tmp_root / f'tmp-{machine.machine}'}:"
               f"/work/builds/{machine.machine}/tmp",
         "-w", "/work", cfg.image,
         "./cli.py", "deploy-info",
         "--machine", machine.machine,
         "--machinebuild", machine.machinebuild,
         "--json", "--require-images", "--require-manifest"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"deploy-info failed for {machine.machine}: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    if info.get("status") == "FAIL":
        raise RuntimeError(
            f"deploy-info reports FAIL for {machine.machine}: {info.get('reason')}")
    for key in ("builddir", "confdir", "tmpdir", "deploy_ipk",
                "deploy_images", "manifest"):
        if info.get(key):
            info[key] = str(_to_host_path(cfg, machine, info[key]))
    return info


def select_assets(deploy_images: Path, manifest: dict) -> list[Path]:
    """Pick the three flash artefacts belonging to the built image.

    Identified through image_name from the manifest, so leftovers from an
    earlier build in the same directory cannot slip into a release.
    """
    image_name = manifest["image_name"]
    assets = []
    for suffix in ASSET_SUFFIXES:
        candidate = deploy_images / f"{image_name}{suffix}"
        if not candidate.exists():
            raise FileNotFoundError(
                f"expected artefact is missing: {candidate.name}")
        assets.append(candidate)
    return assets


def write_sha256sums(files: list[Path], dest: Path) -> Path:
    """One checksum file with bare names, so sha256sum -c works after download."""
    lines = []
    for path in sorted(files, key=lambda p: p.name):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    target = dest / "SHA256SUMS"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def collect_machine(cfg: Config, machine: Machine, dest: Path) -> MachineArtifacts:
    """Copy one machine's release artefacts into the run's artefact dir."""
    info = deploy_info(cfg, machine)
    deploy_images = Path(info["deploy_images"])
    manifest = json.loads(Path(info["manifest"]).read_text(encoding="utf-8"))

    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in select_assets(deploy_images, manifest):
        target = dest / source.name
        shutil.copy2(source, target)
        copied.append(target)
    shutil.copy2(Path(info["manifest"]), dest / f"manifest-{machine.machine}.json")

    # The Yocto image manifest carries the package list the release notes
    # diff against. It is written by every build, unlike buildhistory.
    package_manifest = None
    source = deploy_images / f"{manifest['image_name']}.tuxbox.manifest"
    if source.exists():
        package_manifest = dest / source.name
        shutil.copy2(source, package_manifest)

    return MachineArtifacts(
        machine=machine.machine,
        image_version=manifest["image_version"],
        assets=copied,
        manifest=manifest,
        package_manifest=package_manifest,
    )


def scan_build_log(cfg: Config, machine: Machine, dest: Path) -> tuple[Path | None, int]:
    """Run the repo's log scanner; keep its report and the critical count.

    A build can succeed and still log something alarming. The scanner
    already exists in the repo and is used by the GitHub workflow.
    """
    script = cfg.checkout / "scripts" / "scan-build-log.sh"
    if not script.exists():
        return None, 0
    report = dest / f"build-log-scan-{machine.machine}.md"
    metrics = dest / f"build-log-scan-{machine.machine}.env"
    subprocess.run(
        [str(script),
         "--glob", f"builds/{machine.machine}/tmp/log/cooker/*/*.log",
         "--report", str(report), "--metrics", str(metrics),
         "--allow-missing", "--no-fail-on-critical"],
        cwd=cfg.checkout, capture_output=True, text=True, check=False)

    count = 0
    if metrics.exists():
        for line in metrics.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "critical_count":
                count = int(value.strip() or 0)
    return (report if report.exists() else None), count


def archive_release(cfg: Config, build_id: str, artefact_dir: Path) -> Path:
    """Keep a copy of what was published, outside the build volumes."""
    target = cfg.archive_root / build_id
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(artefact_dir, target)
    return target
