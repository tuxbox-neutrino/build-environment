"""Phase orchestration for one monthly run."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

from .build import build_machine, cleanup_tmpdir, free_gb
from .collect import (archive_release, collect_machine, scan_build_log,
                      write_sha256sums)
from .config import Config
from .notes import (package_diff, previous_package_list, read_package_list,
                    render_notes, write_package_list)
from .notify import issue_fingerprint, open_issue, send_mail
from .publish import publish, release_tag
from .state import BuildState, acquire_lock, new_build_id

#: Phases in the order they run. Verification is not a phase of its own:
#: deploy-info refuses missing images or manifests and select_assets refuses
#: a missing artefact, so an incomplete build never reaches collect.
PHASES = ("preflight", "update", "build", "collect", "publish", "finish")

#: Below this, a machine build cannot finish - skip it instead of filling
#: the disk and failing hours later.
MIN_FREE_GB = 60

#: The idle check powers the host off once this marker exists and no build
#: is running. Waiting out the six idle hours would just burn electricity.
SHUTDOWN_MARKER = Path("/tmp/.shutdown")


def preflight(cfg: Config) -> list[str]:
    """Everything that must hold before a run may start."""
    problems = []
    if not cfg.work_root.is_dir():
        problems.append(f"work_root fehlt: {cfg.work_root}")
    if not cfg.tmp_root.is_dir():
        problems.append(f"tmp_root fehlt: {cfg.tmp_root}")
    if not cfg.archive_root.is_dir():
        problems.append(f"archive_root fehlt: {cfg.archive_root}")
    if not (cfg.checkout / ".git").is_dir():
        problems.append(f"build-environment-Checkout fehlt: {cfg.checkout}")
    for root in (cfg.tmp_root, cfg.work_root):
        if root.is_dir() and free_gb(root) < MIN_FREE_GB:
            problems.append(f"zu wenig Platz auf {root}: {free_gb(root)} GB frei")
    return problems


def _update(cfg: Config, run_dir: Path) -> str:
    """Pull the checkout and report the commit that will be built."""
    with (run_dir / "update.log").open("w") as log:
        subprocess.run(["git", "pull", "--rebase", "--recurse-submodules"],
                       cwd=cfg.checkout, check=False, stdout=log,
                       stderr=subprocess.STDOUT)
        subprocess.run(["git", "submodule", "update", "--init", "--recursive"],
                       cwd=cfg.checkout, check=False, stdout=log,
                       stderr=subprocess.STDOUT)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg.checkout,
                          capture_output=True, text=True,
                          check=False).stdout.strip()


def run(cfg: Config, today: date, dry_run: bool = False) -> int:
    """One complete monthly run. Returns a process exit code."""
    build_id = new_build_id()
    with acquire_lock(cfg.state_dir):
        state = BuildState(cfg.state_dir, build_id)
        run_dir = cfg.runs_dir / build_id
        run_dir.mkdir(parents=True, exist_ok=True)

        state.start("preflight")
        problems = preflight(cfg)
        if problems:
            state.finish("preflight", "failed", problems=problems)
            send_mail(cfg, "buildhost: Monatsbuild nicht gestartet", "\n".join(problems))
            return 1
        state.finish("preflight", "ok")

        state.start("update")
        commit = _update(cfg, run_dir)
        state.finish("update", "ok", commit=commit)

        # Build, collect and clean up one machine at a time. The SSD cannot
        # hold three TMPDIRs, so each tree goes as soon as its artefacts are
        # safely copied - and the next machine only starts if space allows.
        state.start("build")
        artefact_dir = cfg.artifacts_dir / build_id / "images"
        built, failed, results, diffs = [], [], [], {}

        for machine in cfg.machines:
            if dry_run:
                state.machine_result(machine.machine, "skipped (dry-run)")
                continue
            if free_gb(cfg.tmp_root) < MIN_FREE_GB:
                failed.append(machine)
                state.machine_result(machine.machine, "skipped",
                                     reason=f"nur {free_gb(cfg.tmp_root)} GB frei")
                continue

            log_path = run_dir / f"{machine.machine}.log"
            code = build_machine(cfg, machine, log_path)
            if code != 0:
                failed.append(machine)
                state.machine_result(machine.machine, "failed", returncode=code)
                reason = f"cli.py build endete mit {code}"
                open_issue(cfg, f"[build] {machine.machine} fehlgeschlagen",
                           f"Lauf `{build_id}`, Log `{log_path}`.\n\n{reason}",
                           issue_fingerprint(machine.machine, reason))
                cleanup_tmpdir(cfg, machine)
                continue

            result = collect_machine(cfg, machine, artefact_dir)
            report, criticals = scan_build_log(cfg, machine, artefact_dir)
            if report is not None:
                result.assets.append(report)
            if criticals:
                reason = f"{criticals} kritische Logfunde"
                open_issue(cfg, f"[build-log-critical] {machine.machine}",
                           f"Lauf `{build_id}`: {reason}. Bericht liegt dem "
                           f"Release bei.",
                           issue_fingerprint(machine.machine, reason))

            packages = read_package_list(result.package_manifest) \
                if result.package_manifest else {}
            if packages:
                write_package_list(packages, artefact_dir, machine.machine)
            diffs[machine.machine] = package_diff(
                previous_package_list(cfg.archive_root, machine.machine), packages)

            built.append(machine)
            results.append(result)
            state.machine_result(machine.machine, "ok",
                                 image_version=result.image_version,
                                 criticals=criticals)
            cleanup_tmpdir(cfg, machine)

        # A dry run builds nothing on purpose, so an empty result is not a
        # failure - otherwise every rehearsal would look like a broken month
        # and the dead man's switch would alarm on it.
        state.finish("build", "ok" if (built or dry_run) else "failed",
                     built=[m.machine for m in built],
                     failed=[m.machine for m in failed],
                     dry_run=dry_run)
        if not built and not dry_run:
            send_mail(cfg, "buildhost: Monatsbuild komplett fehlgeschlagen",
                      f"Kein Image gebaut. Lauf {build_id}, Logs in {run_dir}.")
            return 1

        state.start("collect")
        assets: list[Path] = []
        if results:
            assets = [a for r in results for a in r.assets]
            assets.append(write_sha256sums(assets, artefact_dir))
        state.finish("collect", "ok", artefacts=str(artefact_dir),
                     asset_count=len(assets))

        state.start("publish")
        version = results[0].image_version if results else "0.0.0.0"
        tag = release_tag(version, today) if results else f"dry-{today:%Y.%m}"
        notes = render_notes(results, tag, diffs,
                             failed=[m.machine for m in failed])
        url = publish(cfg, tag, notes, assets, commit, dry_run=dry_run)
        if results and not dry_run:
            archive_release(cfg, build_id, artefact_dir)
        state.finish("publish", "ok", tag=tag, url=url)

        state.start("finish")
        summary = (f"Lauf {build_id}\nTag: {tag}\nRelease: {url}\n"
                   f"Gebaut: {[m.machine for m in built]}\n"
                   f"Fehlgeschlagen: {[m.machine for m in failed]}\n")
        send_mail(cfg, f"buildhost: Monatsbuild {tag}", summary)
        if not dry_run:
            SHUTDOWN_MARKER.touch()
        state.finish("finish", "ok")
        return 0 if not failed else 2
