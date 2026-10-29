"""The opkg package feed that belongs to one release."""
from __future__ import annotations

import hashlib
import ipaddress
import shutil
import subprocess
import tarfile
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from .config import Config

#: What a box needs from the feed: the packages and their index.
FEED_FILES = ("*.ipk", "Packages", "Packages.gz")
#: rsync gives up after this long without any data moving.
IO_TIMEOUT = 120
#: And the whole upload of one machine after this long.
UPLOAD_TIMEOUT = 3600
VERIFY_TIMEOUT = 15


def feed_config_problem(cfg: Config) -> str | None:
    """Reject a release feed that cannot be used by boxes outside the LAN."""
    if not cfg.feed_base_url or not cfg.feed_dest:
        return "TUXBOX_FEED_BASE_URL und TUXBOX_FEED_DEST muessen beide gesetzt sein"
    try:
        url = urlsplit(cfg.feed_base_url)
        url.port  # Accessing it rejects malformed port numbers.
    except ValueError:
        return "TUXBOX_FEED_BASE_URL ist keine gueltige HTTP-URL"
    if (url.scheme != "http" or not url.hostname or url.username or
            url.password or url.query or url.fragment):
        return "TUXBOX_FEED_BASE_URL muss eine oeffentliche HTTP-URL sein"
    host = url.hostname.lower()
    if "." not in host or host.endswith((".local", ".lan", ".internal",
                                           ".home.arpa", ".fritz.box")):
        return "TUXBOX_FEED_BASE_URL darf keinen lokalen Host nennen"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            return "TUXBOX_FEED_BASE_URL darf keine private IP enthalten"
    return None


def release_dir(when: date) -> str:
    """YYYY.MM - the month part of the release tag, so image and feed agree."""
    return f"{when.year}.{when.month:02d}"


def image_feed_url(cfg: Config, release: str, machine: str) -> str:
    """Where the image built today will look for its packages."""
    return f"{cfg.feed_base_url.rstrip('/')}/{release}/{machine}"


def verify_image_feed(image: Path, feed_url: str,
                      architectures: set[str]) -> None:
    """Read the flash archive and prove its opkg sources match this release.

    Current monthly machines (HD51, HD60, H7) carry rootfs.tar.bz2 in their
    multi.zip. An unknown image layout must stop publishing until inspected.
    """
    try:
        with zipfile.ZipFile(image) as archive:
            roots = [name for name in archive.namelist()
                     if name.endswith("/rootfs.tar.bz2")]
            if len(roots) != 1:
                raise RuntimeError(f"{image.name}: genau ein rootfs.tar.bz2 erwartet")
            with archive.open(roots[0]) as rootfs:
                with tarfile.open(fileobj=rootfs, mode="r|bz2") as tar:
                    for member in tar:
                        if member.name.lstrip("./") == "etc/opkg/base-feeds.conf":
                            if not member.isfile() or member.size > 65536:
                                raise RuntimeError(f"{image.name}: base-feeds.conf ungueltig")
                            stream = tar.extractfile(member)
                            if stream is None:
                                raise RuntimeError(f"{image.name}: base-feeds.conf nicht lesbar")
                            content = stream.read().decode("utf-8")
                            break
                    else:
                        raise RuntimeError(f"{image.name}: base-feeds.conf fehlt")
    except (OSError, UnicodeError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"{image.name}: Feed-Pruefung im Image fehlgeschlagen: {exc}") from exc

    actual = {}
    for line in content.splitlines():
        fields = line.split()
        if fields and fields[0].startswith("src") and fields[0] != "src/gz":
            raise RuntimeError(f"{image.name}: unerwarteter opkg-Quellentyp")
        if fields and fields[0] == "src/gz":
            if len(fields) != 3 or fields[1] in actual:
                raise RuntimeError(f"{image.name}: ungueltige opkg-Quelle")
            actual[fields[1]] = fields[2]
    expected = {arch: f"{feed_url}/{arch}" for arch in architectures}
    if not expected or actual != expected:
        raise RuntimeError(
            f"{image.name}: opkg-Quellen stimmen nicht mit dem Release-Feed ueberein")


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


def verify_feed_online(cfg: Config, release: str, machine: str,
                       source: Path) -> None:
    """Check the public URL after upload, before publishing its image.

    Every staged architecture needs an index and at least one package. The
    served compressed index must equal the one just uploaded, while HEAD on a
    package catches a web-server mapping that serves indexes but not IPKs.
    """
    arch_dirs = sorted(p for p in source.iterdir() if p.is_dir())
    if not arch_dirs:
        raise RuntimeError(f"Feed {machine}: keine Architekturverzeichnisse")
    base = image_feed_url(cfg, release, machine)
    for arch_dir in arch_dirs:
        index = arch_dir / "Packages.gz"
        packages = sorted(arch_dir.glob("*.ipk"))
        if not index.is_file() or not packages:
            raise RuntimeError(
                f"Feed {machine}/{arch_dir.name}: Packages.gz oder IPKs fehlen")
        index_url = f"{base}/{quote(arch_dir.name)}/Packages.gz"
        try:
            request = Request(index_url, headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=VERIFY_TIMEOUT) as response:
                if response.geturl() != index_url:
                    raise RuntimeError(
                        f"Feed {machine}/{arch_dir.name}: HTTP-Weiterleitung im Index")
                remote = response.read(index.stat().st_size + 1)
            if hashlib.sha256(remote).digest() != hashlib.sha256(
                    index.read_bytes()).digest():
                raise RuntimeError(f"Feed {machine}/{arch_dir.name}: HTTP-Index weicht ab")

            package = packages[0]
            package_url = f"{base}/{quote(arch_dir.name)}/{quote(package.name)}"
            with urlopen(Request(package_url, method="HEAD"),
                         timeout=VERIFY_TIMEOUT) as response:
                if response.geturl() != package_url:
                    raise RuntimeError(
                        f"Feed {machine}/{arch_dir.name}: HTTP-Weiterleitung beim IPK")
                length = response.headers.get("Content-Length")
            if length is None or int(length) != package.stat().st_size:
                raise RuntimeError(
                    f"Feed {machine}/{arch_dir.name}: HTTP-IPK-Groesse weicht ab")
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Feed {machine}/{arch_dir.name}: HTTP-Pruefung fehlgeschlagen: {exc}") from exc
