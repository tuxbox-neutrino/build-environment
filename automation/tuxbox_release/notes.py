"""Release notes built from the image manifest."""
from __future__ import annotations

from pathlib import Path

from .collect import MachineArtifacts

#: GitHub rejects release bodies beyond this many characters.
MAX_BODY = 125000
#: Per section, so one huge diff cannot crowd out everything else.
MAX_ENTRIES_PER_SECTION = 200


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


def render_notes(results: list[MachineArtifacts], tag: str,
                 package_diffs: dict[str, dict],
                 failed: list[str] | None = None) -> str:
    """Human-readable notes: what was built, from what, what changed."""
    failed = failed or []
    first = results[0].manifest if results else {}
    lines = [
        f"# Tuxbox-OS {tag}",
        "",
        f"- Image-Version: `{results[0].image_version if results else 'unbekannt'}`",
        f"- Quellstand: `{first.get('git_hash', 'unbekannt')}`",
        f"- Kanal: `{first.get('channel', 'release')}`",
        f"- Gebaut am: {first.get('build_date', 'unbekannt')}",
        "",
        "## Images",
        "",
    ]
    for result in results:
        names = ", ".join(f"`{a.name}`" for a in result.assets) or "-"
        lines.append(f"- **{result.machine}** — {names}")
    if failed:
        lines += ["", "## Nicht gebaut", ""]
        lines += [f"- **{machine}** — Build fehlgeschlagen, siehe Log" for machine in failed]

    lines += ["", "## Pruefsummen", "",
              "`sha256sum -c SHA256SUMS` nach dem Herunterladen.", ""]

    for machine, diff in sorted(package_diffs.items()):
        section = ["", f"## Paketaenderungen {machine}", ""]
        if not any(diff.values()):
            section.append("Keine Aenderungen gegenueber dem Vormonat.")
            section.append("")
            lines += section
            continue
        for title, entries in (("Geaendert", diff["changed"]),
                               ("Neu", diff["added"]),
                               ("Entfernt", diff["removed"])):
            if not entries:
                continue
            section.append(f"**{title}** ({len(entries)})")
            section.append("")
            for name, value in list(entries.items())[:MAX_ENTRIES_PER_SECTION]:
                if isinstance(value, tuple):
                    section.append(f"- `{name}`: {value[0]} -> {value[1]}")
                else:
                    section.append(f"- `{name}`: {value}")
            if len(entries) > MAX_ENTRIES_PER_SECTION:
                section.append(f"- … und {len(entries) - MAX_ENTRIES_PER_SECTION} weitere")
            section.append("")
        lines += section

    body = "\n".join(lines)
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY - 90].rstrip() + \
            "\n\n… gekuerzt; die vollstaendige Paketliste liegt im Manifest bei.\n"
    return body
