import subprocess
import sys
from datetime import date
from pathlib import Path

from tuxbox_release.runner import (should_power_off, preflight, PHASES,
                                   MIN_FREE_GB, commit_is_published, run,
                                   install_signal_handlers)
from tuxbox_release.config import Config, Machine
from tuxbox_release.state import last_state


def make_config(tmp_path: Path) -> Config:
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
    )


def test_phases_are_in_the_documented_order():
    # No separate "verify": deploy-info --require-images --require-manifest
    # and select_assets already refuse an incomplete build.
    assert PHASES == ("preflight", "update", "build", "collect", "publish", "finish")


def test_preflight_complains_about_missing_work_root(tmp_path):
    assert any("work_root" in p for p in preflight(make_config(tmp_path)))


def test_preflight_complains_about_a_missing_checkout(tmp_path):
    cfg = make_config(tmp_path)
    cfg.work_root.mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    assert any("build-environment" in p for p in preflight(cfg))


def test_preflight_is_silent_when_everything_is_in_place(tmp_path, monkeypatch):
    # Free space is patched: the test dirs live under /tmp, which is a
    # 16 GB tmpfs here and would trip the threshold for reasons that have
    # nothing to do with what this test checks.
    monkeypatch.setattr("tuxbox_release.runner.free_gb", lambda path: 500)
    cfg = make_config(tmp_path)
    (cfg.checkout / ".git").mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    assert preflight(cfg) == []


def test_preflight_refuses_to_start_without_space(tmp_path, monkeypatch):
    monkeypatch.setattr("tuxbox_release.runner.free_gb", lambda path: MIN_FREE_GB - 1)
    cfg = make_config(tmp_path)
    (cfg.checkout / ".git").mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    problems = preflight(cfg)
    assert problems and all("zu wenig Platz" in p for p in problems)


def test_free_space_threshold_is_stated_not_implied():
    assert MIN_FREE_GB >= 60


def test_a_real_run_powers_the_host_off():
    assert should_power_off(dry_run=False, keep_draft=False) is True


def test_a_dry_run_does_not_power_the_host_off():
    assert should_power_off(dry_run=True, keep_draft=False) is False


def test_a_rehearsal_does_not_power_the_host_off():
    # A rehearsal is run by hand, usually while someone is still working on
    # the host. Powering it off underneath them would be a rude surprise.
    assert should_power_off(dry_run=False, keep_draft=True) is False


# --- the commit has to exist on the remote before a release can point at it ---

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=t@example.org",
                    *args], cwd=repo, check=True, capture_output=True)


def _checkout_with_remote(tmp_path: Path) -> Path:
    """A real clone with a real origin - git's own answer is the one that counts."""
    origin, work = tmp_path / "origin.git", tmp_path / "clone"
    subprocess.run(["git", "init", "--bare", "-b", "master", str(origin)],
                   check=True, capture_output=True)
    subprocess.run(["git", "clone", str(origin), str(work)],
                   check=True, capture_output=True)
    (work / "a.txt").write_text("1")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "erster")
    _git(work, "push", "origin", "master")
    return work


def _head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_a_pushed_commit_counts_as_published(tmp_path):
    work = _checkout_with_remote(tmp_path)
    assert commit_is_published(work, _head(work)) is True


def test_a_local_only_commit_does_not_count_as_published(tmp_path):
    # This is exactly what killed the rehearsal: HEAD was 92f3866, which
    # existed only on the build host, and GitHub answered
    # "No commit found for SHA".
    work = _checkout_with_remote(tmp_path)
    (work / "a.txt").write_text("2")
    _git(work, "commit", "-am", "nur lokal")
    assert commit_is_published(work, _head(work)) is False


# --- run() must survive a phase blowing up, and must not build in vain ---

def _prepared_config(tmp_path: Path, monkeypatch) -> Config:
    cfg = make_config(tmp_path)
    (cfg.checkout / ".git").mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    monkeypatch.setattr("tuxbox_release.runner.free_gb", lambda path: 500)
    monkeypatch.setattr("tuxbox_release.runner._update",
                        lambda cfg, run_dir: "deadbeef")
    return cfg


def test_an_unpushed_commit_stops_the_run_before_the_build(tmp_path, monkeypatch):
    # Hours of build time for a release that GitHub will refuse anyway.
    cfg = _prepared_config(tmp_path, monkeypatch)
    monkeypatch.setattr("tuxbox_release.runner.commit_is_published",
                        lambda checkout, commit: False)
    built = []
    monkeypatch.setattr("tuxbox_release.runner.build_machine",
                        lambda *a, **k: built.append(a) or 0)
    mails = []
    monkeypatch.setattr("tuxbox_release.runner.send_mail",
                        lambda cfg, subject, body: mails.append((subject, body)))

    code = run(cfg, date(2026, 10, 1))

    assert code == 1
    assert built == [], "the build started although the commit is unpublished"
    assert mails and "deadbeef" in mails[0][1]


def test_a_failing_phase_is_recorded_as_failed_and_mailed(tmp_path, monkeypatch):
    # The rehearsal died in publish; the state file claimed "running" for
    # the next 22 hours and nobody was told.
    cfg = _prepared_config(tmp_path, monkeypatch)
    monkeypatch.setattr("tuxbox_release.runner.publish",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("gh release create failed: nope")))
    mails = []
    monkeypatch.setattr("tuxbox_release.runner.send_mail",
                        lambda cfg, subject, body: mails.append((subject, body)))

    code = run(cfg, date(2026, 10, 1), dry_run=True)

    assert code == 1
    phases = {p["phase"]: p for p in last_state(cfg.state_dir)["phases"]}
    assert phases["publish"]["status"] == "failed"
    assert "nope" in phases["publish"]["error"]
    assert mails, "the run died silently"


def test_a_failing_phase_leaves_the_traceback_on_disk(tmp_path, monkeypatch):
    # /tmp is a tmpfs here, so a traceback that only goes to the console
    # is gone after the next reboot - which is how the first evidence was lost.
    cfg = _prepared_config(tmp_path, monkeypatch)
    monkeypatch.setattr("tuxbox_release.runner.publish",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("gh release create failed: nope")))
    monkeypatch.setattr("tuxbox_release.runner.send_mail",
                        lambda cfg, subject, body: None)

    run(cfg, date(2026, 10, 1), dry_run=True)

    logs = list(cfg.runs_dir.glob("*/error.log"))
    assert logs, "no traceback was kept"
    assert "RuntimeError" in logs[0].read_text(encoding="utf-8")



# --- SIGTERM must not leave the lock behind -------------------------------
# These run in a child process on purpose: sending the signal to the test
# process would take pytest down whenever the handler is missing - precisely
# the case the suite has to survive and report on.

SIGTERM_CHILD = """
import os, signal, sys
sys.path.insert(0, {automation!r})
from tuxbox_release.runner import install_signal_handlers
from tuxbox_release.state import acquire_lock

install_signal_handlers()
try:
    with acquire_lock({state_dir!r}):
        os.kill(os.getpid(), signal.SIGTERM)
except RuntimeError as exc:
    print("RAISED:" + str(exc))
"""


def _run_child(tmp_path: Path) -> subprocess.CompletedProcess:
    automation = str(Path(__file__).resolve().parent.parent)
    script = SIGTERM_CHILD.format(automation=automation, state_dir=str(tmp_path))
    return subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=30)


def test_sigterm_is_turned_into_an_exception(tmp_path):
    result = _run_child(tmp_path)
    assert "RAISED:" in result.stdout and "SIGTERM" in result.stdout, \
        f"signal killed the process instead of raising: {result!r}"


def test_the_lock_is_released_when_sigterm_arrives(tmp_path):
    # The point of the exercise: a run stopped with systemctl must not leave
    # run.lock behind. It did on 2026-09-23, and idle-poweroff-check then
    # refused to ever power the host off again.
    _run_child(tmp_path)
    assert not (tmp_path / "run.lock").exists(), "run.lock survived the signal"


# --- what a run puts into the release --------------------------------------

def _publishing_run(tmp_path: Path, monkeypatch) -> dict:
    """A rehearsal through every phase with the outside world stubbed out."""
    return _publishing_run_with(_prepared_config(tmp_path, monkeypatch),
                                tmp_path, monkeypatch)


def _publishing_run_with(cfg: Config, tmp_path: Path, monkeypatch) -> dict:
    from tuxbox_release.collect import MachineArtifacts
    out = tmp_path / "out"
    out.mkdir()
    image = out / "tuxbox-image-hd51_multi.zip"
    image.write_bytes(b"image")
    report = out / "build-log-scan-hd51.md"
    report.write_text("# Build Log Scan\n")

    monkeypatch.setattr("tuxbox_release.runner.SHUTDOWN_MARKER",
                        tmp_path / "shutdown")
    monkeypatch.setattr("tuxbox_release.runner.commit_is_published",
                        lambda checkout, commit: True)
    monkeypatch.setattr("tuxbox_release.runner.build_machine",
                        lambda *a, **k: 0)
    monkeypatch.setattr("tuxbox_release.runner.cleanup_tmpdir",
                        lambda *a, **k: None)

    def fake_collect(cfg, machine, dest):
        dest.mkdir(parents=True, exist_ok=True)
        return MachineArtifacts(machine="hd51", image_version="4.0.35.501",
                                assets=[image], manifest={"git_hash": "deadbee"})
    monkeypatch.setattr("tuxbox_release.runner.collect_machine", fake_collect)
    monkeypatch.setattr("tuxbox_release.runner.scan_build_log",
                        lambda cfg, machine, dest: (report, 0))
    monkeypatch.setattr("tuxbox_release.runner.fetch_appimage",
                        lambda repo, token: None)
    monkeypatch.setattr("tuxbox_release.runner.send_mail",
                        lambda cfg, subject, body: None)
    published = {}

    def fake_publish(cfg, tag, notes, assets, commit, **kw):
        published.update(notes=notes, assets=assets, commit=commit)
        return "https://github.invalid/release"
    monkeypatch.setattr("tuxbox_release.runner.publish", fake_publish)

    code = run(cfg, date(2026, 10, 1), keep_draft=True)
    errors = [e.read_text() for e in cfg.runs_dir.glob("*/error.log")]
    assert code == 0, errors
    return published


def test_the_log_scan_report_stays_off_the_release(tmp_path, monkeypatch):
    # An internal diagnostic, not something to download next to an image.
    published = _publishing_run(tmp_path, monkeypatch)
    names = [a.name for a in published["assets"]]
    assert not any(n.startswith("build-log-scan") for n in names), names
    sums = next(a for a in published["assets"] if a.name == "SHA256SUMS")
    assert "build-log-scan" not in sums.read_text(encoding="utf-8")
    assert "build-log-scan" not in published["notes"]


def test_the_notes_link_the_commit_that_was_built(tmp_path, monkeypatch):
    published = _publishing_run(tmp_path, monkeypatch)
    assert ("https://github.com/tuxbox-neutrino/build-environment/tree/deadbeef"
            in published["notes"])


def test_the_notes_count_package_changes_per_section(tmp_path, monkeypatch):
    from tuxbox_release.collect import MachineArtifacts
    from tuxbox_release.notes import write_package_list, write_package_sections
    cfg = _prepared_config(tmp_path, monkeypatch)
    previous = cfg.archive_root / "20261022T095021Z"
    previous.mkdir(parents=True)
    write_package_list({"neutrino": "1", "gone": "1"}, previous, "hd51")
    write_package_sections({"gone": "x11"}, previous, "hd51")
    manifest = tmp_path / "img.tuxbox.manifest"
    manifest.write_text("neutrino cortexa15hf 2\nnewbie all 1\n")
    image = tmp_path / "tuxbox-image-hd51_multi.zip"
    image.write_bytes(b"image")

    monkeypatch.setattr("tuxbox_release.runner.SHUTDOWN_MARKER", tmp_path / "shutdown")
    monkeypatch.setattr("tuxbox_release.runner.commit_is_published", lambda c, h: True)
    monkeypatch.setattr("tuxbox_release.runner.build_machine", lambda *a, **k: 0)
    monkeypatch.setattr("tuxbox_release.runner.cleanup_tmpdir", lambda *a, **k: None)
    monkeypatch.setattr("tuxbox_release.runner.scan_build_log",
                        lambda cfg, machine, dest: (None, 0))
    monkeypatch.setattr("tuxbox_release.runner.fetch_appimage", lambda r, t: None)
    monkeypatch.setattr("tuxbox_release.runner.send_mail", lambda c, s, b: None)
    monkeypatch.setattr("tuxbox_release.runner.archive_release", lambda *a: None)

    def fake_collect(cfg, machine, dest):
        dest.mkdir(parents=True, exist_ok=True)
        return MachineArtifacts(
            machine="hd51", image_version="4.0.35.501", assets=[image],
            manifest={"git_hash": "deadbee"}, package_manifest=manifest,
            package_sections={"neutrino": "libs", "newbie": "neutrino-plugin"})
    monkeypatch.setattr("tuxbox_release.runner.collect_machine", fake_collect)
    published = {}
    monkeypatch.setattr("tuxbox_release.runner.publish",
                        lambda cfg, tag, notes, assets, commit, **kw:
                        published.update(notes=notes) or "https://github.invalid")

    assert run(cfg, date(2026, 11, 1), keep_draft=True) == 0
    notes = published["notes"]
    assert "| hd51 | 1 | 1 | 1 | libs 1 · neutrino-plugin 1 · x11 1 |" in notes, \
        "the removed package lost its section"
    sections = next(cfg.artifacts_dir.glob("*/images/sections-hd51.txt"))
    assert "newbie\tneutrino-plugin" in sections.read_text(encoding="utf-8")


def test_the_notes_link_downloads_in_the_release_repo(tmp_path, monkeypatch):
    cfg = _prepared_config(tmp_path, monkeypatch)
    cfg = Config(**{**cfg.__dict__, "release_repo": "tuxbox-neutrino/images",
                    "machines": (Machine("hd51", "mutant51", "Mut@nt HD51"),)})
    published = _publishing_run_with(cfg, tmp_path, monkeypatch)
    assert ("| Mut@nt HD51 | [multi.zip](https://github.com/tuxbox-neutrino/images/"
            "releases/download/v4.0.35.501-2026.10/tuxbox-image-hd51_multi.zip)"
            in published["notes"])
