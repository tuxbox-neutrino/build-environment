"""Phase orchestration for one monthly run."""
from __future__ import annotations

import shutil
import signal
import subprocess
import traceback
from datetime import date
from pathlib import Path

from .build import build_machine, cleanup_tmpdir, free_gb
from .collect import (archive_release, collect_machine, scan_build_log,
                      write_sha256sums)
from .config import Config
from .notes import (fetch_appimage, package_diff, previous_package_list,
                    read_package_list, render_notes, write_package_list)
from .notify import (issue_fingerprint, mail_subject, open_issue,
                     send_mail)
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


def commit_is_published(checkout: Path, commit: str) -> bool:
    """True when at least one remote branch contains the commit.

    gh release create --target refuses a SHA that GitHub has never seen,
    and it refuses it after the build rather than before it. Asking git
    first costs milliseconds and saves hours.
    """
    result = subprocess.run(["git", "branch", "-r", "--contains", commit],
                            cwd=checkout, capture_output=True, text=True,
                            check=False)
    return bool(result.stdout.strip())


def install_signal_handlers() -> None:
    """Turn SIGTERM and SIGINT into an ordinary exception.

    Python's default for SIGTERM is to die on the spot: no finally, no
    context manager exit, so acquire_lock never removes run.lock. The
    stale file then blocks idle-poweroff-check forever, because it tests
    for the file rather than for the lock. Raising instead lets the normal
    teardown run and the phase be recorded as failed.
    """
    def raise_on_signal(signum, _frame):
        raise RuntimeError(
            f"{signal.Signals(signum).name} erhalten, Lauf abgebrochen")

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, raise_on_signal)


def should_power_off(dry_run: bool, keep_draft: bool) -> bool:
    """Only a real, publishing run has earned the shutdown.

    A rehearsal is started by hand, usually while someone is still working
    on the host.
    """
    return not dry_run and not keep_draft


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


def _run_phases(cfg: Config, today: date, state: BuildState,
                run_dir: Path, build_id: str, dry_run: bool,
                keep_draft: bool) -> int:
    """Every phase of one run, in order.

    Raises on anything unexpected; run() turns that into a recorded and
    reported failure.
    """
    state.start("preflight")
    problems = preflight(cfg)
    if problems:
        state.finish("preflight", "failed", problems=problems)
        send_mail(cfg, mail_subject("Monatsbuild nicht gestartet"),
                  "\n".join(problems))
        return 1
    state.finish("preflight", "ok")

    state.start("update")
    commit = _update(cfg, run_dir)
    if not dry_run and not commit_is_published(cfg.checkout, commit):
        # A release points at a commit. If GitHub has never seen it,
        # gh release create --target refuses - after the build, not before.
        problem = (f"Commit {commit} liegt auf keinem Remote-Branch. "
                   f"gh release create --target wuerde ihn ablehnen. "
                   f"Erst pushen, dann den Lauf wiederholen.")
        state.finish("update", "failed", commit=commit, problem=problem)
        send_mail(cfg, mail_subject("Monatsbuild nicht gestartet"), problem)
        return 1
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
        send_mail(cfg, mail_subject("Monatsbuild komplett fehlgeschlagen"),
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
                         failed=[m.machine for m in failed],
                         appimage=fetch_appimage(cfg.appimage_repo, cfg.token))
    url = publish(cfg, tag, notes, assets, commit, dry_run=dry_run,
                  keep_draft=keep_draft)
    if results and not dry_run:
        archive_release(cfg, build_id, artefact_dir)
    state.finish("publish", "ok", tag=tag, url=url)

    state.start("finish")
    summary = (f"Lauf {build_id}\nTag: {tag}\nRelease: {url}\n"
               f"Gebaut: {[m.machine for m in built]}\n"
               f"Fehlgeschlagen: {[m.machine for m in failed]}\n")
    send_mail(cfg, mail_subject(f"Monatsbuild {tag}"), summary)
    if should_power_off(dry_run, keep_draft):
        SHUTDOWN_MARKER.touch()
    state.finish("finish", "ok")
    return 0 if not failed else 2


def run(cfg: Config, today: date, dry_run: bool = False,
        keep_draft: bool = False) -> int:
    """One complete monthly run. Returns a process exit code."""
    build_id = new_build_id()
    with acquire_lock(cfg.state_dir):
        state = BuildState(cfg.state_dir, build_id)
        run_dir = cfg.runs_dir / build_id
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            return _run_phases(cfg, today, state, run_dir, build_id,
                               dry_run, keep_draft)
        except Exception as exc:
            # Without this the run just dies: the state file keeps claiming
            # "running", nobody is told, and the traceback goes wherever
            # stdout happened to point, which was a tmpfs here.
            (run_dir / "error.log").write_text(traceback.format_exc(),
                                               encoding="utf-8")
            state.fail_running(str(exc))
            send_mail(cfg, mail_subject("Monatsbuild abgebrochen"),
                      f"Lauf {build_id} brach ab:\n\n{exc}\n\n"
                      f"Vollstaendiger Traceback: {run_dir / 'error.log'}")
            return 1
