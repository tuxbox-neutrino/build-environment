from pathlib import Path
from tuxbox_release.notes import (parse_appimage_release, package_diff,
                                  fetch_appimage,
                                  render_notes, read_package_list,
                                  write_package_list, previous_package_list)
from tuxbox_release.collect import MachineArtifacts


def artifacts(machine="hd51", version="4.0.35.501") -> MachineArtifacts:
    return MachineArtifacts(
        machine=machine, image_version=version, assets=[],
        manifest={"image_version": version, "git_hash": "277d6b8",
                  "build_date": "2026-10-01", "channel": "release"},
    )


def test_reads_the_yocto_image_manifest(tmp_path):
    m = tmp_path / "img.tuxbox.manifest"
    m.write_text("alsa-conf cortexa15hf-neon-vfpv4 1.2.6.1-r0\n"
                 "alsa-topology-conf all 1.2.5.1-r0\n")
    assert read_package_list(m) == {"alsa-conf": "1.2.6.1-r0",
                                    "alsa-topology-conf": "1.2.5.1-r0"}


def test_missing_manifest_is_empty_not_an_error(tmp_path):
    assert read_package_list(tmp_path / "nope.manifest") == {}


def test_diff_reports_added_removed_and_changed():
    diff = package_diff({"a": "1.0", "b": "2.0"}, {"a": "1.1", "c": "3.0"})
    assert diff["changed"] == {"a": ("1.0", "1.1")}
    assert diff["added"] == {"c": "3.0"}
    assert diff["removed"] == {"b": "2.0"}


def test_identical_package_sets_produce_no_entries():
    assert package_diff({"a": "1.0"}, {"a": "1.0"}) == {"changed": {}, "added": {}, "removed": {}}


def test_notes_name_every_machine_and_the_commit():
    notes = render_notes([artifacts("hd51"), artifacts("hd60")], "v4.0.35.501-2026.10", {})
    assert "hd51" in notes and "hd60" in notes
    assert "277d6b8" in notes and "v4.0.35.501-2026.10" in notes


def test_failed_machine_is_named_in_the_notes():
    notes = render_notes([artifacts("hd51")], "v1-2026.10", {}, failed=["hd60"])
    assert "hd60" in notes and "nicht gebaut" in notes.lower()


def test_first_run_without_previous_data_says_so():
    notes = render_notes([artifacts()], "v1-2026.10",
                         {"hd51": {"changed": {}, "added": {}, "removed": {}}})
    assert "Keine Aenderungen" in notes


def test_notes_stay_within_github_release_limit():
    huge = {"changed": {f"pkg{i}": ("1.0", "1.1") for i in range(5000)},
            "added": {}, "removed": {}}
    notes = render_notes([artifacts()], "v1-2026.10", {"hd51": huge})
    assert len(notes) < 125000


def test_previous_list_is_empty_on_the_first_run(tmp_path):
    assert previous_package_list(tmp_path, "hd51") == {}


def test_previous_list_uses_the_newest_archived_run(tmp_path):
    for build_id, version in (("20260901T060000Z", "1.0"), ("20261001T060000Z", "2.0")):
        run = tmp_path / build_id
        run.mkdir()
        write_package_list({"neutrino": version}, run, "hd51")
    assert previous_package_list(tmp_path, "hd51") == {"neutrino": "2.0"}


# --- the PC build lives in its own repository and is only referenced ------

GH_ANSWER = """{
  "tagName": "build/2026.9.43.git20260920142802.g90f6850faa-bdc3e6e",
  "url": "https://github.invalid/org/pc-build/releases/tag/build%2F2026.9.43",
  "publishedAt": "2026-09-20T18:55:25Z",
  "assets": [
    {"name": "Neutrino_2026.9.43.git20260920142802.g90f6850faa_x86_64.AppImage"},
    {"name": "SHA256SUMS"}
  ]
}"""


def test_the_appimage_asset_is_picked_out_of_the_release():
    ref = parse_appimage_release(GH_ANSWER)
    assert ref["asset"].endswith(".AppImage")
    assert ref["url"].startswith("https://")
    assert ref["published"] == "2026-09-20"


def test_a_release_without_an_appimage_is_no_reference():
    assert parse_appimage_release('{"tagName":"x","url":"y","assets":[]}') is None


def test_garbage_is_no_reference():
    # The monthly build must not die because a side note could not be
    # fetched. Anything unparseable simply means: no section.
    assert parse_appimage_release("") is None
    assert parse_appimage_release("not json") is None


def test_the_notes_link_the_appimage_and_say_it_is_a_separate_build():
    ref = parse_appimage_release(GH_ANSWER)
    body = render_notes([], "v4.0.35.501-2026.10", {}, appimage=ref)
    assert ref["url"] in body
    assert "PC" in body or "Rechner" in body, \
        "the notes do not say this is not a box image"
    assert "2026-09-20" in body, "the reader cannot see it is a different build"


def test_without_a_reference_there_is_no_empty_section():
    body = render_notes([], "v4.0.35.501-2026.10", {}, appimage=None)
    assert "AppImage" not in body


def test_no_configured_repo_means_no_lookup(monkeypatch):
    # Not every installation has a PC build to point at, and an
    # unconfigured one must not cost a network call.
    called = []
    monkeypatch.setattr("tuxbox_release.notes.subprocess.run",
                        lambda *a, **k: called.append(a))
    assert fetch_appimage("", "token") is None
    assert called == [], "a lookup happened without a configured repository"


def test_a_failing_lookup_is_no_reference(monkeypatch):
    # gh not installed, no network, repo gone - the monthly build carries
    # on regardless. A missing side note is not a failure.
    def boom(*a, **k):
        raise OSError("gh not found")
    monkeypatch.setattr("tuxbox_release.notes.subprocess.run", boom)
    assert fetch_appimage("org/pc-build", "token") is None


def test_a_successful_lookup_is_parsed(monkeypatch):
    import subprocess as sp
    monkeypatch.setattr("tuxbox_release.notes.subprocess.run",
                        lambda *a, **k: sp.CompletedProcess(a, 0, stdout=GH_ANSWER))
    ref = fetch_appimage("org/pc-build", "token")
    assert ref is not None and ref["asset"].endswith(".AppImage")
