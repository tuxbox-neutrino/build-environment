import pytest
from datetime import date
from pathlib import Path

from tuxbox_release import publish as publish_mod
from tuxbox_release.config import Config, Machine
from tuxbox_release.publish import (release_tag, gh_create_draft_command,
                                    gh_upload_command, publish)


def test_tag_combines_image_version_and_month():
    assert release_tag("4.0.35.501", date(2026, 10, 1)) == "v4.0.35.501-2026.10"


def test_tag_pads_single_digit_months():
    assert release_tag("4.0.35.501", date(2026, 3, 1)) == "v4.0.35.501-2026.03"


def test_tag_rejects_a_missing_version():
    with pytest.raises(ValueError, match="image_version"):
        release_tag("", date(2026, 10, 1))


def test_tag_rejects_the_distro_version_by_mistake():
    # DISTRO_VERSION has three parts, TUXBOX_IMAGE_VERSION has four.
    with pytest.raises(ValueError, match="image_version"):
        release_tag("4.0.32", date(2026, 10, 1))


def test_draft_is_created_as_draft_and_pinned_to_a_commit():
    cmd = gh_create_draft_command("tuxbox-neutrino/build-environment",
                                  "v4.0.35.501-2026.10", "notes.md", "277d6b8")
    assert "--draft" in cmd
    assert "--target" in cmd and "277d6b8" in cmd
    assert "--notes-file" in cmd


def test_upload_uses_clobber_so_a_retry_is_safe():
    cmd = gh_upload_command("tuxbox-neutrino/build-environment",
                            "v4.0.35.501-2026.10", ["/tmp/a.zip"])
    assert "--clobber" in cmd


def make_config(tmp_path: Path) -> Config:
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
    )


def _recording_run(calls: list, asset: Path):
    """Stand-in for _run that answers the asset listing plausibly."""
    def fake_run(cmd, cfg):
        calls.append(cmd)
        if "view" in cmd and "assets" in " ".join(cmd):
            return f"{asset.name} {asset.stat().st_size}"
        return "https://github.invalid/releases/tag/v4.0.35.501-2026.10"
    return fake_run


def test_keep_draft_stops_before_publishing(tmp_path, monkeypatch):
    # A draft is invisible to anyone without write access. That is what makes
    # it safe to rehearse the whole chain against the production repository.
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert not any("--draft=false" in cmd for cmd in calls), \
        f"draft was published despite keep_draft: {calls}"


def test_keep_draft_still_uploads_and_verifies(tmp_path, monkeypatch):
    # Otherwise keep_draft would just be a second dry run and would prove
    # nothing about the upload, which is the part that actually breaks.
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert any(cmd[:3] == ["gh", "release", "upload"] for cmd in calls), \
        f"nothing was uploaded: {calls}"
    assert any("--json" in cmd and "assets" in cmd for cmd in calls), \
        f"upload was not verified: {calls}"


def test_a_normal_run_still_publishes(tmp_path, monkeypatch):
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    assert any("--draft=false" in cmd for cmd in calls), \
        f"the release was never published: {calls}"



def test_a_rerun_does_not_trip_over_its_own_release(tmp_path, monkeypatch):
    # After a partial failure (hd60 and h7 died on 2026-09-23, hd51 went
    # through and was published) the obvious next step is to build the rest
    # and upload into the same release. gh release create refuses a tag that
    # already exists, so the rerun would fail in publish for no good reason.
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: True)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert not any(cmd[:3] == ["gh", "release", "create"] for cmd in calls), \
        f"the existing release was created a second time: {calls}"
    assert any(cmd[:3] == ["gh", "release", "upload"] for cmd in calls), \
        f"the rerun uploaded nothing: {calls}"


def test_a_rerun_refreshes_the_notes(tmp_path, monkeypatch):
    # The rerun's notes list more machines than the first attempt's did.
    # Leaving the old ones would describe a release that no longer matches
    # its own assets.
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: True)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert any(cmd[:3] == ["gh", "release", "edit"] and "--notes-file" in cmd
               for cmd in calls), f"the notes were never refreshed: {calls}"


def test_a_first_run_still_creates_the_release(tmp_path, monkeypatch):
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert any(cmd[:3] == ["gh", "release", "create"] for cmd in calls), \
        f"no release was created: {calls}"



def _rerun_run(calls: list, remote: list, asset: Path):
    """Stand-in for _run that answers both asset queries plausibly."""
    def fake_run(cmd, cfg):
        calls.append(cmd)
        joined = " ".join(cmd)
        if "view" in cmd and ".assets[].name" in joined:
            return "\n".join(remote)
        if "view" in cmd and "assets" in joined:
            return f"{asset.name} {asset.stat().st_size}"
        return "https://github.invalid/releases/tag/v4.0.35.501-2026.10"
    return fake_run


def test_a_rerun_removes_the_previous_attempts_assets(tmp_path, monkeypatch):
    # Asset names carry the build timestamp, so --clobber never matches an
    # earlier attempt's files. After the 2026-09-24 rerun the release held
    # hd51 ten times over, and nobody downloading could tell which was
    # current.
    asset = tmp_path / "image-20260924.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run",
                        _rerun_run(calls, ["image-20260923.zip", asset.name], asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: True)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    deleted = [cmd for cmd in calls if "delete-asset" in cmd]
    assert any("image-20260923.zip" in cmd for cmd in deleted), \
        f"the stale asset survived: {calls}"


def test_a_rerun_keeps_what_it_uploads_itself(tmp_path, monkeypatch):
    asset = tmp_path / "image-20260924.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run",
                        _rerun_run(calls, ["image-20260923.zip", asset.name], asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: True)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    deleted = [cmd for cmd in calls if "delete-asset" in cmd]
    assert not any(asset.name in cmd for cmd in deleted), \
        f"this run deleted its own asset: {deleted}"


def test_a_first_run_deletes_nothing(tmp_path, monkeypatch):
    asset = tmp_path / "image-20260924.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _rerun_run(calls, [], asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8", keep_draft=True)

    assert not any("delete-asset" in cmd for cmd in calls), \
        f"a fresh release had assets deleted: {calls}"


# --- a separate release repository ------------------------------------------

def test_a_draft_without_a_commit_has_no_target():
    cmd = gh_create_draft_command("tuxbox-neutrino/tuxbox-os-images",
                                  "v4.0.35.501-2026.10", "notes.md", None)
    assert "--target" not in cmd


def _split_config(tmp_path: Path) -> Config:
    cfg = make_config(tmp_path)
    return Config(**{**cfg.__dict__,
                     "release_repo": "tuxbox-neutrino/tuxbox-os-images"})


def test_a_separate_release_repo_receives_every_release_call(tmp_path, monkeypatch):
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(_split_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    repos = {cmd[cmd.index("--repo") + 1] for cmd in calls if "--repo" in cmd}
    assert repos == {"tuxbox-neutrino/tuxbox-os-images"}, calls


def test_a_separate_release_repo_is_not_pinned_to_a_foreign_commit(tmp_path, monkeypatch):
    # The built commit exists only in the build system's repository;
    # gh release create --target would answer "No commit found for SHA".
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(_split_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    create = next(cmd for cmd in calls if cmd[:3] == ["gh", "release", "create"])
    assert "--target" not in create and "277d6b8" not in create


def test_the_build_system_repo_still_pins_the_built_commit(tmp_path, monkeypatch):
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    monkeypatch.setattr(publish_mod, "_run", _recording_run(calls, asset))
    monkeypatch.setattr(publish_mod, "release_exists", lambda cfg, tag: False)

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    create = next(cmd for cmd in calls if cmd[:3] == ["gh", "release", "create"])
    assert create[create.index("--target") + 1] == "277d6b8"


def test_a_rerun_stays_in_the_separate_release_repo(tmp_path, monkeypatch):
    # The second attempt of a month asks, edits and prunes - all of it has
    # to happen where the first attempt published, not in the source repo.
    asset = tmp_path / "image.zip"
    asset.write_bytes(b"payload")
    calls: list = []
    asked: list = []
    monkeypatch.setattr(publish_mod, "_run",
                        _rerun_run(calls, ["old.zip", asset.name], asset))

    def exists(cfg, tag):
        asked.append(cfg.publish_repo)
        return True
    monkeypatch.setattr(publish_mod, "release_exists", exists)

    publish(_split_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    repos = {cmd[cmd.index("--repo") + 1] for cmd in calls if "--repo" in cmd}
    assert repos == {"tuxbox-neutrino/tuxbox-os-images"}, calls
    assert asked == ["tuxbox-neutrino/tuxbox-os-images"]
    assert any(cmd[:3] == ["gh", "release", "delete-asset"] and "old.zip" in cmd
               for cmd in calls), calls


def test_release_exists_asks_the_release_repo(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(publish_mod.subprocess, "run",
                        lambda cmd, **kw: seen.append(cmd) or
                        type("R", (), {"returncode": 1})())
    publish_mod.release_exists(_split_config(tmp_path), "v4.0.35.501-2026.10")
    assert seen[0][seen[0].index("--repo") + 1] == "tuxbox-neutrino/tuxbox-os-images"
