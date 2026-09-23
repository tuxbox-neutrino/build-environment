import subprocess
from pathlib import Path

from tuxbox_release.build import (container_command, cleanup_tmpdir,
                                  build_machine)
from tuxbox_release.config import Config, Machine


def make_config() -> Config:
    return Config(
        work_root=Path("/mnt/C/tuxbox-build"),
        tmp_root=Path("/mnt/build"),
        archive_root=Path("/mnt/archiv/releases"),
        image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment",
        channel="release",
        mail_to="ops@example.org",
        token="secret",
    )


def test_command_is_a_throwaway_container():
    cmd = container_command(make_config(), Machine("hd51", "mutant51"))
    assert cmd[:3] == ["docker", "run", "--rm"]


def test_machine_tmpdir_is_mounted_from_the_ssd():
    cmd = container_command(make_config(), Machine("hd51", "mutant51"))
    joined = " ".join(cmd)
    assert "/mnt/build/tmp-hd51:/work/builds/hd51/tmp" in joined


def test_caches_are_shared_across_machines():
    joined = " ".join(container_command(make_config(), Machine("hd60", "ax60")))
    assert "/mnt/C/tuxbox-build/sstate-cache:/work/sstate-cache" in joined
    assert "/mnt/C/tuxbox-build/downloads:/work/downloads" in joined


def test_build_call_carries_machine_and_machinebuild():
    cmd = container_command(make_config(), Machine("h7", "zgemmah7"))
    inner = cmd[-1]
    assert "--machine h7" in inner
    assert "--machinebuild zgemmah7" in inner
    assert "--distro-type release" in inner


def test_no_token_is_passed_into_the_container():
    assert "secret" not in " ".join(
        container_command(make_config(), Machine("hd51", "mutant51")))


def test_mirrors_are_mounted_at_the_same_path_as_outside(monkeypatch):
    # local.conf.user.inc names them by absolute path; a different path
    # inside the container would turn every mirror hit into a silent miss.
    monkeypatch.setattr("tuxbox_release.build.Path.is_dir", lambda self: True)
    joined = " ".join(container_command(make_config(), Machine("hd51", "mutant51")))
    assert "/mnt/sstate-mirror:/mnt/sstate-mirror:ro" in joined
    assert "/mnt/downloads-mirror:/mnt/downloads-mirror:ro" in joined


def test_absent_mirrors_are_simply_left_out(monkeypatch):
    monkeypatch.setattr("tuxbox_release.build.Path.is_dir", lambda self: False)
    joined = " ".join(container_command(make_config(), Machine("hd51", "mutant51")))
    assert "sstate-mirror" not in joined


def test_cleanup_removes_only_this_machines_tmpdir(tmp_path):
    cfg = make_config()
    object.__setattr__(cfg, "tmp_root", tmp_path)
    (tmp_path / "tmp-hd51" / "work").mkdir(parents=True)
    (tmp_path / "tmp-hd60" / "work").mkdir(parents=True)
    cleanup_tmpdir(cfg, Machine("hd51", "mutant51"))
    assert not (tmp_path / "tmp-hd51").exists()
    assert (tmp_path / "tmp-hd60").exists()


def test_cleanup_is_harmless_when_nothing_is_there(tmp_path):
    cfg = make_config()
    object.__setattr__(cfg, "tmp_root", tmp_path)
    cleanup_tmpdir(cfg, Machine("hd51", "mutant51"))



def _local_config(tmp_path: Path) -> Config:
    """Same shape as make_config, but rooted in tmp_path so it may be written."""
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
    )


def test_the_mount_parent_exists_before_the_container_starts(tmp_path, monkeypatch):
    # Docker creates a missing bind-mount target itself, and the daemon runs
    # as root - so builds/<machine> ends up root-owned and cli.py cannot
    # create builds/<machine>/conf inside it. That is how hd60 and h7 died on
    # 2026-09-23 with EACCES, while hd51 went through: its directory already
    # existed from an earlier build.
    cfg = _local_config(tmp_path)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["exists"] = (cfg.checkout / "builds" / "hd60").is_dir()
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("tuxbox_release.build.subprocess.run", fake_run)
    build_machine(cfg, Machine("hd60", "ax60"), tmp_path / "runs" / "hd60.log")

    assert seen["exists"], \
        "builds/hd60 did not exist, so docker would create it as root"
