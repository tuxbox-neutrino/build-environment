from pathlib import Path
from tuxbox_release.notes import (parse_appimage_release, package_diff,
                                  fetch_appimage, source_url, section_counts,
                                  write_package_sections,
                                  previous_package_sections,
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
    assert "277d6b8" in notes and "4.0.35.501" in notes


def test_failed_machine_is_named_in_the_notes():
    notes = render_notes([artifacts("hd51")], "v1-2026.10", {}, failed=["hd60"])
    assert "hd60" in notes and "nicht gebaut" in notes.lower()


def test_first_run_without_previous_data_says_so():
    notes = render_notes([artifacts()], "v1-2026.10",
                         {"hd51": {"changed": {}, "added": {}, "removed": {}}})
    assert "Keine Paketänderungen" in notes


def test_notes_stay_within_github_release_limit():
    huge = {"changed": {f"pkg{i}": ("1.0", "1.1") for i in range(5000)},
            "added": {}, "removed": {}}
    notes = render_notes([artifacts()], "v1-2026.10", {"hd51": huge})
    assert len(notes) < 125000


# --- package changes are counted per IPK section, not listed --------------

def test_changes_are_counted_per_section():
    diff = {"changed": {"neutrino": ("1", "2"), "tuxcal": ("1", "2")},
            "added": {"satfind": "1"}, "removed": {"oldlib": "1"}}
    sections = {"neutrino": "libs", "tuxcal": "neutrino-plugin",
                "satfind": "neutrino-plugin", "oldlib": "libs"}
    assert section_counts(diff, sections) == {
        "libs": {"changed": 1, "added": 0, "removed": 1},
        "neutrino-plugin": {"changed": 1, "added": 1, "removed": 0},
    }


def test_a_package_without_a_known_section_is_still_counted():
    diff = {"changed": {"mystery": ("1", "2")}, "added": {}, "removed": {}}
    assert section_counts(diff, {}) == {
        "unbekannt": {"changed": 1, "added": 0, "removed": 0}}


def test_the_notes_count_changes_without_naming_packages():
    # Hundreds of names made the release page unreadable; the counts per
    # section say what kind of change a month brought.
    diff = {"changed": {f"pkg{i}": ("1.0", "1.1") for i in range(300)},
            "added": {"newpkg": "1"}, "removed": {}}
    sections = {f"pkg{i}": ("libs" if i % 2 else "devel") for i in range(300)}
    sections["newpkg"] = "neutrino-plugin"
    notes = render_notes([artifacts()], "v1-2026.10", {"hd51": diff},
                         sections={"hd51": sections})
    assert "pkg1" not in notes and "newpkg" not in notes
    assert "| hd51 | 300 | 1 | 0 | devel 150 · libs 150 · neutrino-plugin 1 |" in notes
    assert len(notes) < 2500


def test_the_busiest_section_comes_first():
    diff = {"changed": {"a": ("1", "2"), "b": ("1", "2"), "c": ("1", "2")},
            "added": {}, "removed": {}}
    notes = render_notes([artifacts()], "v1-2026.10", {"hd51": diff},
                         sections={"hd51": {"a": "x11", "b": "libs", "c": "libs"}})
    assert notes.index("libs 2") < notes.index("x11 1")


def test_sections_survive_into_next_month(tmp_path):
    # A package removed next month is no longer in the feed; its section
    # has to come from this month's archive.
    run = tmp_path / "20261022T095021Z"
    run.mkdir()
    write_package_sections({"neutrino": "libs", "busybox": "base utils"}, run, "hd51")
    assert previous_package_sections(tmp_path, "hd51") == {
        "neutrino": "libs", "busybox": "base utils"}


def test_previous_sections_are_empty_without_an_archive(tmp_path):
    assert previous_package_sections(tmp_path, "hd51") == {}


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
    assert "20.09.2026" in body, "the reader cannot see it is a different build"


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


# --- the built source state is linked, not attached ------------------------

def test_the_source_link_points_at_the_tree_of_the_built_commit():
    assert source_url("tuxbox-neutrino/build-environment", "275ce154f1") == \
        "https://github.com/tuxbox-neutrino/build-environment/tree/275ce154f1"


def test_the_notes_link_the_built_source_state():
    url = "https://github.com/tuxbox-neutrino/build-environment/tree/275ce154f1"
    notes = render_notes([artifacts()], "v4.0.35.501-2026.10", {}, source=url)
    assert f"](" + url + ")" in notes
    assert "277d6b8" in notes, "the short hash from the manifest stays readable"


def test_without_a_source_link_the_hash_stays_plain_text():
    notes = render_notes([artifacts()], "v4.0.35.501-2026.10", {})
    assert "`277d6b8`" in notes and "/tree/" not in notes


# --- the page a downloader reads -------------------------------------------

def _built(tmp_path, machine, *suffixes):
    files = []
    for suffix in suffixes:
        f = tmp_path / f"tuxbox-image-{machine}-4.0.35.502-20261022095142{suffix}"
        f.write_bytes(b"x" * 2_500_000)
        files.append(f)
    return MachineArtifacts(
        machine=machine, image_version="4.0.35.502", assets=files,
        manifest={"git_hash": "813230a", "build_date": "20261022095142",
                  "channel": "release"})


def test_downloads_are_linked_with_their_size(tmp_path):
    result = _built(tmp_path, "hd51", "_multi.zip", "_recovery_emmc.zip")
    notes = render_notes([result], "v4.0.35.502-2026.10", {},
                         release_repo="tuxbox-neutrino/images",
                         labels={"hd51": "Mut@nt HD51"})
    base = "https://github.com/tuxbox-neutrino/images/releases/download/v4.0.35.502-2026.10/"
    assert (f"| Mut@nt HD51 | [multi.zip]({base}tuxbox-image-hd51-4.0.35.502-"
            f"20261022095142_multi.zip) · 2.5 MB |") in notes
    assert f"[`SHA256SUMS`]({base}SHA256SUMS)" in notes


def test_a_missing_file_type_leaves_a_dash(tmp_path):
    # A future box without a recovery package still gets its row.
    result = _built(tmp_path, "vuduo4k", "_usb.zip")
    notes = render_notes([result], "v1-2026.11", {}, release_repo="org/images")
    row = next(line for line in notes.splitlines() if line.startswith("| vuduo4k |"))
    assert "[usb.zip](" in row and row.endswith("| – |")


def test_every_box_is_one_row_in_both_tables(tmp_path):
    # More boxes mean more rows; the columns stay the same.
    boxes = [f"box{i}" for i in range(8)]
    results = [_built(tmp_path, m, "_multi.zip") for m in boxes]
    diffs = {m: {"changed": {"neutrino": ("1", "2")}, "added": {}, "removed": {}} for m in boxes}
    notes = render_notes(results, "v1-2026.11", diffs, release_repo="org/images",
                         sections={m: {"neutrino": "libs"} for m in boxes})
    header_lines = [l for l in notes.splitlines() if l.startswith("| Box |")]
    assert len(header_lines) == 2
    assert all(len(l.split("|")) <= 7 for l in header_lines)
    assert sum(1 for l in notes.splitlines() if l.startswith("| box")) == 16


def test_build_date_and_umlauts_are_written_for_people():
    notes = render_notes([artifacts()], "v1-2026.10", {})
    assert "Prüfsummen" in notes and "Pruefsummen" not in notes
    assert "Paketänderungen" in notes


def test_the_build_timestamp_is_readable(tmp_path):
    notes = render_notes([_built(tmp_path, "hd51", "_multi.zip")], "v1-2026.10", {})
    assert "gebaut am 22.10.2026" in notes
    assert "22.10.2026, 09:51 UTC" in notes


def test_a_failed_box_is_named_by_its_label(tmp_path):
    notes = render_notes([_built(tmp_path, "hd51", "_multi.zip")], "v1-2026.10", {},
                         failed=["hd60"], labels={"hd60": "AX HD60"})
    assert "**Nicht gebaut:** AX HD60" in notes


def test_a_dry_run_without_images_still_renders():
    assert "Downloads" in render_notes([], "dry-2026.10", {})



def test_the_download_table_offers_image_and_recovery_only(tmp_path):
    notes = render_notes([_built(tmp_path, "hd51", "_multi.zip")], "v1-2026.11", {})
    assert "| Box | Image | Recovery |" in notes
    assert "Root-Dateisystem" not in notes


def test_the_notes_name_the_package_feed_of_the_release():
    notes = render_notes([artifacts()], "v1-2026.11", {},
                         feed="http://feed.example.org/ipk/2026.11/")
    assert "`http://feed.example.org/ipk/2026.11/<box>/`" in notes


def test_without_a_feed_the_notes_do_not_mention_one():
    assert "opkg" not in render_notes([artifacts()], "v1-2026.11", {})
