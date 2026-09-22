import pytest
from datetime import date
from tuxbox_release.publish import release_tag, gh_create_draft_command, gh_upload_command


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
