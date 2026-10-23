import subprocess
from datetime import date
from pathlib import Path

import pytest

from tuxbox_release import feed as feed_mod
from tuxbox_release.config import Config, Machine
from tuxbox_release.feed import (collect_feed, image_feed_url, release_dir,
                                 upload_feed)


def make_config(tmp_path: Path, **extra) -> Config:
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
        feed_base_url="http://feed.example.org/ipk/", feed_dest="feed-host:", **extra)


def test_the_release_directory_is_the_month_of_the_release_tag():
    # Image and feed have to agree on it; release_tag() uses the same month.
    assert release_dir(date(2026, 11, 1)) == "2026.11"
    assert release_dir(date(2026, 3, 9)) == "2026.03"


def test_the_image_points_at_its_own_release_and_box(tmp_path):
    assert image_feed_url(make_config(tmp_path), "2026.11", "hd51") == \
        "http://feed.example.org/ipk/2026.11/hd51"


def _deploy_ipk(tmp_path: Path) -> Path:
    deploy = tmp_path / "deploy" / "ipk"
    for arch in ("all", "cortexa15hf-neon-vfpv4", "hd51"):
        (deploy / arch).mkdir(parents=True)
        (deploy / arch / f"pkg-{arch}_1.0_{arch}.ipk").write_bytes(b"ipk")
        (deploy / arch / "Packages").write_text("Package: x\n")
        (deploy / arch / "Packages.gz").write_bytes(b"gz")
        (deploy / arch / "Packages.stamps").write_text("stamp")
    (deploy / "Packages").write_text("")
    return deploy


def test_the_feed_is_copied_with_packages_and_indexes_only(tmp_path):
    dest = collect_feed(_deploy_ipk(tmp_path), tmp_path / "staging" / "hd51")
    names = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert names == [
        "all/Packages", "all/Packages.gz", "all/pkg-all_1.0_all.ipk",
        "cortexa15hf-neon-vfpv4/Packages", "cortexa15hf-neon-vfpv4/Packages.gz",
        "cortexa15hf-neon-vfpv4/pkg-cortexa15hf-neon-vfpv4_1.0_cortexa15hf-neon-vfpv4.ipk",
        "hd51/Packages", "hd51/Packages.gz", "hd51/pkg-hd51_1.0_hd51.ipk"]


def test_no_feed_means_nothing_to_copy(tmp_path):
    assert collect_feed(tmp_path / "nope", tmp_path / "staging" / "hd51") is None


def _recording(calls: list, rc: int = 0):
    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, rc, "", "rsync: boom")
    return fake_run


def test_packages_go_up_before_their_index(tmp_path, monkeypatch):
    # A box must never read an index that names a package not yet uploaded.
    calls: list = []
    monkeypatch.setattr(feed_mod.subprocess, "run", _recording(calls))
    source = collect_feed(_deploy_ipk(tmp_path), tmp_path / "staging" / "hd51")

    upload_feed(make_config(tmp_path), "2026.11", "hd51", source)

    first, second = (cmd for cmd, _ in calls)
    assert first[0] == second[0] == "rsync"
    assert "--exclude=Packages*" in first
    assert "--exclude=Packages*" not in second
    assert first[-1] == second[-1] == "feed-host:2026.11/hd51/"
    assert first[-2] == second[-2] == f"{source}/"


def test_the_upload_is_bounded_and_world_readable(tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(feed_mod.subprocess, "run", _recording(calls))
    source = collect_feed(_deploy_ipk(tmp_path), tmp_path / "staging" / "hd51")
    upload_feed(make_config(tmp_path), "2026.11", "hd51", source)
    for cmd, kw in calls:
        assert "--chmod=D755,F644" in cmd and "--mkpath" in cmd
        assert any(a.startswith("--timeout=") for a in cmd)
        assert kw.get("timeout")


def test_a_failed_upload_is_reported(tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(feed_mod.subprocess, "run", _recording(calls, rc=12))
    source = collect_feed(_deploy_ipk(tmp_path), tmp_path / "staging" / "hd51")
    with pytest.raises(RuntimeError, match="hd51"):
        upload_feed(make_config(tmp_path), "2026.11", "hd51", source)
    assert len(calls) == 1, "the index went up after its packages had failed"


def test_a_hanging_upload_is_reported(tmp_path, monkeypatch):
    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(feed_mod.subprocess, "run", hang)
    source = collect_feed(_deploy_ipk(tmp_path), tmp_path / "staging" / "hd51")
    with pytest.raises(RuntimeError, match="hd51"):
        upload_feed(make_config(tmp_path), "2026.11", "hd51", source)
