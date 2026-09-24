import subprocess
from pathlib import Path

from tuxbox_release.build import (container_command, cleanup_tmpdir,
                                  build_machine, mirror_is_usable,
                                  mounted_types)
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
    monkeypatch.setattr("tuxbox_release.build.mirror_is_usable",
                        lambda path: True)
    joined = " ".join(container_command(make_config(), Machine("hd51", "mutant51")))
    assert "/mnt/sstate-mirror:/mnt/sstate-mirror:ro" in joined
    assert "/mnt/downloads-mirror:/mnt/downloads-mirror:ro" in joined


def test_absent_mirrors_are_simply_left_out(monkeypatch):
    # h7 died on 2026-09-23 with "error mounting /mnt/downloads-mirror ... no
    # such device", because red was off and the automount trigger was all
    # that was left. A missing mirror must cost cache hits, not the build.
    monkeypatch.setattr("tuxbox_release.build.mirror_is_usable",
                        lambda path: False)
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



def test_a_directory_that_is_not_mounted_is_not_usable(tmp_path):
    # The mirrors arrive over NFS with x-systemd.automount, so the directory
    # exists even while nothing is mounted on it. Path.is_dir() cannot tell
    # the difference; os.path.ismount can.
    plain = tmp_path / "looks-like-a-mirror"
    plain.mkdir()
    assert mirror_is_usable(plain) is False


def test_a_missing_directory_is_not_usable(tmp_path):
    assert mirror_is_usable(tmp_path / "gone") is False


PROC_MOUNTS = """\
/dev/sda1 /mnt/C ext4 rw,noatime 0 0
systemd-1 /mnt/downloads-mirror autofs rw,relatime,fd=54 0 0
mirror-host:/srv/export/sstate-cache /mnt/sstate-mirror nfs4 ro,relatime 0 0
"""


def test_an_idle_automount_trigger_does_not_count_as_mounted():
    # While the server is down, /proc/mounts still lists the trigger - with
    # fstype autofs. Docker cannot bind-mount that: "no such device".
    assert mounted_types(PROC_MOUNTS).get("/mnt/downloads-mirror") == "autofs"


def test_a_real_nfs_mount_is_reported_with_its_type():
    assert mounted_types(PROC_MOUNTS).get("/mnt/sstate-mirror") == "nfs4"


def test_an_unlisted_path_is_absent():
    assert mounted_types(PROC_MOUNTS).get("/mnt/nowhere") is None


# What /proc/mounts really looks like once the automount has fired: the
# trigger stays listed and the actual mount is stacked on top of it.
PROC_MOUNTS_MOUNTED = """\
systemd-1 /mnt/sstate-mirror autofs rw,relatime,fd=57,timeout=600 0 0
mirror-host:/srv/export/sstate-cache /mnt/sstate-mirror nfs4 ro,relatime,vers=4.2 0 0
"""


def test_a_mount_stacked_on_its_trigger_counts_as_mounted():
    # Both lines name the same mount point. The later one is the one that
    # is actually visible, so it has to win - otherwise a perfectly good
    # mirror would be dropped as "still just a trigger".
    assert mounted_types(PROC_MOUNTS_MOUNTED).get("/mnt/sstate-mirror") == "nfs4"
