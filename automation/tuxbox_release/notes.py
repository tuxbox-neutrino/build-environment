"""Release notes built from the image manifest."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

from pathlib import Path

from .collect import IMAGE_SUFFIXES, MachineArtifacts

#: GitHub rejects release bodies beyond this many characters.
MAX_BODY = 125000
#: Section of a package that no feed index and no archived run knows.
UNKNOWN_SECTION = "unbekannt"


def read_package_list(manifest: Path) -> dict[str, str]:
    """Package name -> version from a Yocto image manifest.

    The image manifest ("<image>.tuxbox.manifest") sits next to the image
    and lists "<package> <arch> <version>" per line. It is written by every
    build, unlike buildhistory, which has to be enabled explicitly and is
    not active here.
    """
    versions: dict[str, str] = {}
    if not manifest.exists():
        return versions
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            versions[parts[0]] = parts[2]
    return versions


def write_package_list(packages: dict[str, str], dest: Path, machine: str) -> Path:
    """Keep this run's package set so next month can diff against it."""
    target = dest / f"packages-{machine}.txt"
    target.write_text(
        "\n".join(f"{name} {version}" for name, version in sorted(packages.items())) + "\n",
        encoding="utf-8")
    return target


def previous_package_list(archive_root: Path, machine: str) -> dict[str, str]:
    """Package set of the most recent archived run, empty on the first run."""
    candidates = sorted(Path(archive_root).glob(f"*/packages-{machine}.txt"))
    if not candidates:
        return {}
    versions: dict[str, str] = {}
    for line in candidates[-1].read_text(encoding="utf-8").splitlines():
        name, _, version = line.strip().partition(" ")
        if name:
            versions[name] = version
    return versions


def write_package_sections(sections: dict[str, str], dest: Path, machine: str) -> Path:
    """Keep this run's sections so next month can place removed packages.

    A package dropped from the image is usually gone from the next feed as
    well, so its section is only known from the month it was still built.
    """
    target = dest / f"sections-{machine}.txt"
    target.write_text(
        "".join(f"{name}\t{section}\n" for name, section in sorted(sections.items())),
        encoding="utf-8")
    return target


def previous_package_sections(archive_root: Path, machine: str) -> dict[str, str]:
    """Sections of the most recent archived run, empty if none was kept."""
    candidates = sorted(Path(archive_root).glob(f"*/sections-{machine}.txt"))
    if not candidates:
        return {}
    sections: dict[str, str] = {}
    for line in candidates[-1].read_text(encoding="utf-8").splitlines():
        name, _, section = line.partition("\t")
        if name:
            sections[name] = section
    return sections


def package_diff(previous: dict[str, str], current: dict[str, str]) -> dict:
    """What changed between two package sets."""
    changed = {
        name: (previous[name], current[name])
        for name in sorted(set(previous) & set(current))
        if previous[name] != current[name]
    }
    added = {name: current[name] for name in sorted(set(current) - set(previous))}
    removed = {name: previous[name] for name in sorted(set(previous) - set(current))}
    return {"changed": changed, "added": added, "removed": removed}


def section_counts(diff: dict, sections: dict[str, str]) -> dict[str, dict[str, int]]:
    """How many packages changed, arrived or left, per IPK section."""
    counts: dict[str, dict[str, int]] = {}
    for kind in ("changed", "added", "removed"):
        for name in diff[kind]:
            section = sections.get(name) or UNKNOWN_SECTION
            entry = counts.setdefault(section, {"changed": 0, "added": 0, "removed": 0})
            entry[kind] += 1
    return counts


def fetch_appimage(repo: str, token: str) -> dict | None:
    """Ask another repository for its newest AppImage release.

    Everything here is best effort. The reference is a courtesy to the
    reader, not part of the release, so no failure of this lookup may
    reach the caller.
    """
    if not repo:
        return None
    try:
        result = subprocess.run(
            ["gh", "release", "view", "--repo", repo,
             "--json", "tagName,url,publishedAt,assets"],
            capture_output=True, text=True, check=False,
            env=dict(os.environ, GH_TOKEN=token))
    except OSError:
        return None
    return parse_appimage_release(result.stdout)


def parse_appimage_release(raw: str) -> dict | None:
    """Pick the AppImage out of another repository's release, or None.

    The PC build lives in its own repository and follows its own schedule,
    so the monthly release only points at it. Anything unparseable, empty
    or without an AppImage asset yields None: a side note must never be
    able to fail the build.
    """
    try:
        data = json.loads(raw)
        assets = [a["name"] for a in data.get("assets", [])
                  if a.get("name", "").endswith(".AppImage")]
        if not assets:
            return None
        return {
            "asset": assets[0],
            "url": data["url"],
            "published": str(data.get("publishedAt", ""))[:10],
        }
    except (ValueError, KeyError, TypeError):
        return None


def source_url(repo: str, commit: str) -> str:
    """The build system's tree at the commit that was built.

    Linked instead of attached: whoever wants the source state can browse
    or clone it there, and the release carries only what goes on a box.
    """
    return f"https://github.com/{repo}/tree/{commit}"


#: Columns of the download table: heading and the file suffixes it shows,
#: the first one found wins.
DOWNLOAD_COLUMNS = (
    ("Image", IMAGE_SUFFIXES),
    ("Recovery", ("_recovery_emmc.zip",)),
)


def _short_name(suffix: str) -> str:
    """"_multi.zip" -> "multi.zip", "_recovery_emmc.zip" -> "recovery_emmc.zip"."""
    return suffix.lstrip("_")


def _megabytes(size: int) -> str:
    megabytes = size / 1e6
    return f"{megabytes:.1f} MB" if megabytes < 10 else f"{megabytes:.0f} MB"


def _download_url(release_repo: str, tag: str, name: str) -> str:
    return f"https://github.com/{release_repo}/releases/download/{tag}/{name}"


def _download_cell(result: MachineArtifacts, suffixes: tuple[str, ...],
                   release_repo: str, tag: str) -> str:
    """Link and size of the first matching file, or a dash if the box has none."""
    for suffix in suffixes:
        asset = next((a for a in result.assets if a.name.endswith(suffix)), None)
        if asset is None:
            continue
        cell = (f"[{_short_name(suffix)}]({_download_url(release_repo, tag, asset.name)})"
                if release_repo else f"`{_short_name(suffix)}`")
        if asset.exists():
            cell += f" · {_megabytes(asset.stat().st_size)}"
        return cell
    return "–"


def _build_time(stamp: str) -> datetime | None:
    """Yocto's build_date (YYYYmmddHHMMSS, UTC) as a datetime, if it is one."""
    try:
        return datetime.strptime(str(stamp), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _german_date(iso_day: str) -> str:
    try:
        return datetime.strptime(iso_day, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_day


def _changes_table(order: list[str], package_diffs: dict[str, dict],
                   sections: dict[str, dict[str, str]],
                   labels: dict[str, str]) -> list[str]:
    """One row per box, so more boxes add rows and never columns."""
    if not any(any(diff.values()) for diff in package_diffs.values()):
        return ["Keine Paketänderungen gegenüber dem Vormonat."]
    lines = ["| Box | Aktualisiert | Neu | Entfernt | nach Section |",
             "|---|---:|---:|---:|---|"]
    for machine in order:
        diff = package_diffs.get(machine)
        if diff is None:
            continue
        counts = section_counts(diff, sections.get(machine, {}))
        ranked = sorted(counts.items(),
                        key=lambda item: (-sum(item[1].values()), item[0]))
        by_section = " · ".join(f"{name} {sum(count.values())}"
                                for name, count in ranked) or "–"
        lines.append(f"| {labels.get(machine, machine)} | {len(diff['changed'])} "
                     f"| {len(diff['added'])} | {len(diff['removed'])} | {by_section} |")
    return lines


def render_notes(results: list[MachineArtifacts], tag: str,
                 package_diffs: dict[str, dict],
                 failed: list[str] | None = None,
                 appimage: dict | None = None,
                 source: str = "",
                 sections: dict[str, dict[str, str]] | None = None,
                 release_repo: str = "",
                 labels: dict[str, str] | None = None) -> str:
    """The release page: downloads first, then what changed, details last.

    Written for whoever wants to flash a box. One row per box in every
    table, so a new box adds a row and never a column. Package changes are
    counted per IPK section rather than listed: a month can touch hundreds
    of packages, and a list of all of them buries the rest of the page.
    The package lists stay in the run archive.
    """
    failed = failed or []
    sections = sections or {}
    labels = labels or {}
    first = results[0].manifest if results else {}
    built = _build_time(first.get("build_date", ""))
    lines = [f"Monatliches Neutrino-Image für Set-Top-Boxen, gebaut am {built:%d.%m.%Y}."
             if built else "Monatliches Neutrino-Image für Set-Top-Boxen.",
             "", "## Downloads", ""]

    if results:
        lines += ["| Box | " + " | ".join(head for head, _ in DOWNLOAD_COLUMNS) + " |",
                  "|---" * (len(DOWNLOAD_COLUMNS) + 1) + "|"]
        for result in results:
            cells = [_download_cell(result, suffixes, release_repo, tag)
                     for _, suffixes in DOWNLOAD_COLUMNS]
            lines.append(f"| {labels.get(result.machine, result.machine)} | "
                         + " | ".join(cells) + " |")
    else:
        lines.append("Keine Images gebaut.")
    if failed:
        names = ", ".join(labels.get(machine, machine) for machine in failed)
        lines += ["", f"**Nicht gebaut:** {names} – Build fehlgeschlagen."]

    hint = "**Image** ist der normale Download."
    if any(a.name.endswith("_recovery_emmc.zip") for r in results for a in r.assets):
        hint += (" Das **Recovery**-Paket wird nur gebraucht, wenn die Box ihr "
                 "Multiboot-Menü nicht mehr erreicht oder sich die Partitionierung "
                 "ändert – es kann den gesamten Flash löschen.")
    sums = (f"[`SHA256SUMS`]({_download_url(release_repo, tag, 'SHA256SUMS')})"
            if release_repo else "`SHA256SUMS`")
    lines += ["", hint, "",
              f"Prüfsummen: {sums} – im Download-Ordner `sha256sum -c SHA256SUMS` ausführen.",
              "", "## Paketänderungen gegenüber dem Vormonat", ""]
    order = [r.machine for r in results]
    order += sorted(set(package_diffs) - set(order))
    lines += _changes_table(order, package_diffs, sections, labels)

    if appimage:
        # A separate build from a separate repository: linked, not copied,
        # so nobody mistakes it for part of this month's box images.
        lines += ["", "## Neutrino für den PC", "",
                  "Die AppImage-Variante läuft auf dem Rechner statt auf der Box und "
                  "wird getrennt aus einem eigenen Quellstand gebaut: "
                  f"[{appimage['asset']}]({appimage['url']}) "
                  f"(Stand {_german_date(appimage['published'])})."]

    revision = first.get("git_hash", "unbekannt")
    if source:
        repo_name = source.split("/tree/")[0].rsplit("/", 1)[-1]
        source_cell = f"[`{repo_name}@{revision}`]({source})"
    else:
        source_cell = f"`{revision}`"
    lines += ["", "## Build-Details", "", "| | |", "|---|---|",
              f"| Image-Version | `{results[0].image_version if results else 'unbekannt'}` |",
              f"| Quellstand | {source_cell} |",
              f"| Kanal | `{first.get('channel', 'release')}` |",
              f"| Gebaut | {built:%d.%m.%Y, %H:%M} UTC |" if built
              else f"| Gebaut | {first.get('build_date', 'unbekannt')} |",
              ""]

    body = "\n".join(lines)
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY - 90].rstrip() + \
            "\n\n… gekürzt; die vollständigen Paketlisten liegen im Archiv des Laufs.\n"
    return body
