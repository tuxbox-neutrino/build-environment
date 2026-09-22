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

    publish(make_config(tmp_path), "v4.0.35.501-2026.10", "notes",
            [asset], "277d6b8")

    assert any("--draft=false" in cmd for cmd in calls), \
        f"the release was never published: {calls}"
