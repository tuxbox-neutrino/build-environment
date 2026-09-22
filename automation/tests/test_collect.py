import json
import pytest
from pathlib import Path
from tuxbox_release.collect import (select_assets, write_sha256sums, ASSET_SUFFIXES,
                                    _to_host_path)
from tuxbox_release.config import Config, Machine

MANIFEST = {
    "schema_version": 1,
    "machine": "hd51",
    "image_version": "4.0.35.501",
    "image_name": "tuxbox-image-hd51-4.0.35.501-20260922060545",
    "channel": "release",
    "git_hash": "277d6b8",
}


def make_config(tmp_path: Path) -> Config:
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
    )


def make_deploy(tmp_path: Path) -> Path:
    deploy = tmp_path / "images" / "hd51"
    deploy.mkdir(parents=True)
    base = MANIFEST["image_name"]
    for name in (
        f"{base}_recovery_emmc.zip",
        f"{base}_multi.zip",
        f"{base}.tuxbox.tar.bz2",
        f"{base}.tuxbox.ext4",
        f"{base}.rootfs.ext4",
        f"{base}.tuxbox.manifest",
    ):
        (deploy / name).write_bytes(b"x")
    (deploy / "manifest.json").write_text(json.dumps(MANIFEST))
    return deploy


def test_selects_exactly_the_three_flash_artefacts(tmp_path):
    assets = select_assets(make_deploy(tmp_path), MANIFEST)
    assert len(assets) == len(ASSET_SUFFIXES)
    assert {a.name.replace(MANIFEST["image_name"], "") for a in assets} == set(ASSET_SUFFIXES)


def test_raw_ext4_is_never_published(tmp_path):
    assets = select_assets(make_deploy(tmp_path), MANIFEST)
    assert not any(a.name.endswith(".ext4") for a in assets)


def test_missing_artefact_is_an_error(tmp_path):
    deploy = make_deploy(tmp_path)
    next(deploy.glob("*_multi.zip")).unlink()
    with pytest.raises(FileNotFoundError, match="_multi.zip"):
        select_assets(deploy, MANIFEST)


def test_assets_belong_to_the_image_in_the_manifest(tmp_path):
    deploy = make_deploy(tmp_path)
    (deploy / "tuxbox-image-hd51-4.0.35.400-20250101000000_multi.zip").write_bytes(b"old")
    assets = select_assets(deploy, MANIFEST)
    assert all(MANIFEST["image_name"] in a.name for a in assets)


def test_sha256sums_lists_every_file_by_bare_name(tmp_path):
    files = []
    for name in ("a.zip", "b.zip"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        files.append(path)
    sums = write_sha256sums(files, tmp_path)
    lines = sums.read_text().strip().splitlines()
    assert len(lines) == 2
    assert all(len(line.split("  ")[0]) == 64 for line in lines)
    assert sorted(line.split("  ")[1] for line in lines) == ["a.zip", "b.zip"]


def test_container_tmpdir_path_maps_back_to_the_ssd(tmp_path):
    cfg = make_config(tmp_path)
    got = _to_host_path(cfg, Machine("hd51", "mutant51"),
                        "/work/builds/hd51/tmp/deploy/images/hd51")
    assert got == cfg.tmp_root / "tmp-hd51" / "deploy/images/hd51"


def test_container_work_path_maps_back_to_the_checkout(tmp_path):
    cfg = make_config(tmp_path)
    got = _to_host_path(cfg, Machine("hd51", "mutant51"), "/work/builds/hd51")
    assert got == cfg.checkout / "builds/hd51"


def test_host_path_is_left_alone(tmp_path):
    cfg = make_config(tmp_path)
    assert _to_host_path(cfg, Machine("hd51", "mutant51"), "/mnt/elsewhere") == Path("/mnt/elsewhere")
