"""The opkg package feed that belongs to one release."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

from .config import Config

#: What a box needs from the feed: the packages and their index.
FEED_FILES = ("*.ipk", "Packages", "Packages.gz")
#: rsync gives up after this long without any data moving.
IO_TIMEOUT = 120
#: And the whole upload of one machine after this long.
UPLOAD_TIMEOUT = 3600


def release_dir(when: date) -> str:
    """YYYY.MM - the month part of the release tag, so image and feed agree."""
    return f"{when.year}.{when.month:02d}"


def image_feed_url(cfg: Config, release: str, machine: str) -> str:
    """Where the image built today will look for its packages."""
    return f"{cfg.feed_base_url.rstrip('/')}/{release}/{machine}"


def collect_feed(deploy_ipk: Path, dest: Path) -> Path | None:
    """Copy the build's feed out of TMPDIR before cleanup_tmpdir removes it.

    Only the packages and their indexes; Packages.stamps and the empty
    top-level Packages are build bookkeeping.
    """
    deploy_ipk = Path(deploy_ipk)
    if not deploy_ipk.is_dir():
        return None
    copied = False
    for arch in sorted(p for p in deploy_ipk.iterdir() if p.is_dir()):
        for pattern in FEED_FILES:
            for source in arch.glob(pattern):
                (dest / arch.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest / arch.name / source.name)
                copied = True
    return dest if copied else None


def _rsync(source: Path, target: str, extra: list[str]) -> list[str]:
    return ["rsync", "-a", "--chmod=D755,F644", "--mkpath",
            f"--timeout={IO_TIMEOUT}", *extra, f"{source}/", target]


def upload_feed(cfg: Config, release: str, machine: str, source: Path) -> None:
    """Upload one machine's feed: packages first, then the indexes.

    A box reading the index while the upload runs must never find a package
    named there that is not on the server yet. Raises RuntimeError on any
    failure; the caller decides whether that stops the release.
    """
    target = f"{cfg.feed_dest}{release}/{machine}/"
    for extra in (["--exclude=Packages*"], ["--delete-after"]):
        try:
            result = subprocess.run(_rsync(source, target, extra),
                                    capture_output=True, text=True,
                                    timeout=UPLOAD_TIMEOUT, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Feed-Upload {machine} abgebrochen: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError(
                f"Feed-Upload {machine} fehlgeschlagen ({result.returncode}): "
                f"{result.stderr.strip()[-300:]}")
