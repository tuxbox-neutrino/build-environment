"""Publish one monthly release to GitHub."""
from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

from .config import Config


def release_tag(image_version: str, when: date) -> str:
    """v<TUXBOX_IMAGE_VERSION>-<YYYY.MM>, e.g. v4.0.35.501-2026.10.

    The version has to be the four-part image_version from manifest.json.
    The three-part DISTRO_VERSION is the Yocto base and never appears on
    the box, so tagging with it would mislead everyone reading the tag.
    """
    parts = image_version.split(".")
    if len(parts) < 4:
        raise ValueError(
            "image_version must be the four-part TUXBOX_IMAGE_VERSION "
            f"(got {image_version!r})")
    return f"v{image_version}-{when.year}.{when.month:02d}"


def gh_create_draft_command(repo: str, tag: str, notes_file: str, commit: str) -> list[str]:
    return ["gh", "release", "create", tag,
            "--repo", repo, "--target", commit,
            "--title", f"Tuxbox-OS {tag}",
            "--notes-file", notes_file, "--draft"]


def gh_upload_command(repo: str, tag: str, assets: list[str]) -> list[str]:
    # --clobber so a retry after a failed run replaces a partial asset
    # instead of erroring out.
    return ["gh", "release", "upload", tag, *assets, "--repo", repo, "--clobber"]


def _run(cmd: list[str], cfg: Config) -> str:
    env = dict(os.environ, GH_TOKEN=cfg.token)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0:
        # Never echo the full command; the environment carries the token.
        raise RuntimeError(
            f"gh {' '.join(cmd[1:3])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_uploads(cfg: Config, tag: str, assets: list[Path]) -> None:
    """Compare every uploaded asset's size against the local file.

    A release whose assets are truncated is worse than no release: people
    download it and only notice when flashing fails.
    """
    listing = _run(["gh", "release", "view", tag, "--repo", cfg.repo,
                    "--json", "assets", "--jq",
                    '.assets[] | .name + " " + (.size|tostring)'], cfg)
    remote = dict(line.rsplit(" ", 1) for line in listing.splitlines() if " " in line)
    for asset in assets:
        expected = str(asset.stat().st_size)
        actual = remote.get(asset.name)
        if actual != expected:
            raise RuntimeError(
                f"upload incomplete: {asset.name} is {actual} bytes on GitHub, "
                f"{expected} locally")


def publish(cfg: Config, tag: str, notes: str, assets: list[Path],
            commit: str, dry_run: bool = False) -> str:
    """Draft, upload, verify, then publish. In that order, deliberately."""
    notes_file = cfg.state_dir / f"notes-{tag}.md"
    notes_file.parent.mkdir(parents=True, exist_ok=True)
    notes_file.write_text(notes, encoding="utf-8")

    if dry_run:
        return f"(dry-run) would publish {tag} with {len(assets)} assets"

    _run(gh_create_draft_command(cfg.repo, tag, str(notes_file), commit), cfg)
    _run(gh_upload_command(cfg.repo, tag, [str(a) for a in assets]), cfg)
    verify_uploads(cfg, tag, assets)
    _run(["gh", "release", "edit", tag, "--repo", cfg.repo, "--draft=false"], cfg)
    return _run(["gh", "release", "view", tag, "--repo", cfg.repo,
                 "--json", "url", "--jq", ".url"], cfg)
