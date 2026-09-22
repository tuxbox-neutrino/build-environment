"""Configuration for the monthly image build."""
from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Machine:
    """A build target: platform plus OEM variant."""
    machine: str
    machinebuild: str


@dataclass(frozen=True)
class Config:
    work_root: Path
    tmp_root: Path
    archive_root: Path
    image: str
    machines: tuple[Machine, ...]
    repo: str
    channel: str
    mail_to: str
    token: str

    @property
    def checkout(self) -> Path:
        return self.work_root / "build-environment"

    @property
    def state_dir(self) -> Path:
        return self.work_root / "state"

    @property
    def runs_dir(self) -> Path:
        return self.work_root / "runs"

    @property
    def artifacts_dir(self) -> Path:
        return self.work_root / "artifacts"


def _parse_machines(raw: str) -> tuple[Machine, ...]:
    machines = []
    for entry in (e.strip() for e in raw.split(",") if e.strip()):
        machine, _, machinebuild = entry.partition(":")
        machines.append(Machine(machine, machinebuild or machine))
    if not machines:
        raise ValueError("TUXBOX_MACHINES is empty")
    return tuple(machines)


def load_config(path: Path) -> Config:
    """Read the environment file and refuse anything unsafe."""
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IROTH | stat.S_IWOTH):
        raise PermissionError(
            f"{path} is readable by others (mode {mode:04o}); "
            "it holds the GitHub token"
        )

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    for key in ("TUXBOX_WORK_ROOT", "TUXBOX_MACHINES", "TUXBOX_REPO", "GH_TOKEN"):
        if not values.get(key):
            raise ValueError(f"{key} is missing from {path}")
    for key in ("GH_TOKEN", "TUXBOX_MAIL_TO"):
        if values.get(key, "").startswith("CHANGEME"):
            raise ValueError(f"{key} still holds its placeholder value")

    return Config(
        work_root=Path(values["TUXBOX_WORK_ROOT"]),
        tmp_root=Path(values.get("TUXBOX_TMP_ROOT", "/mnt/build")),
        archive_root=Path(values.get("TUXBOX_ARCHIVE_ROOT", "/mnt/archiv/releases")),
        image=values.get("TUXBOX_IMAGE", "tuxbox-build:ci"),
        machines=_parse_machines(values["TUXBOX_MACHINES"]),
        repo=values["TUXBOX_REPO"],
        channel=values.get("TUXBOX_CHANNEL", "release"),
        mail_to=values.get("TUXBOX_MAIL_TO", ""),
        token=values["GH_TOKEN"],
    )
