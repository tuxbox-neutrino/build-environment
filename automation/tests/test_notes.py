from pathlib import Path
from tuxbox_release.notes import (package_diff, render_notes, read_package_list,
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
