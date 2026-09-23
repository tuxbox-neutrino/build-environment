"""Run state and locking for the monthly image build."""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def new_build_id() -> str:
    """UTC timestamp, sortable: 20260922T060000Z."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BuildState:
    """One JSON file per run, rewritten after every transition."""

    def __init__(self, state_dir: Path, build_id: str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.build_id = build_id
        self.path = self.state_dir / f"{build_id}.json"
        if not self.path.exists():
            self._write({
                "build_id": build_id,
                "created": _now(),
                "phases": [],
                "machines": {},
            })

    def _read_raw(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
        tmp.replace(self.path)
        (self.state_dir / "last.json").write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def read(self) -> dict:
        return self._read_raw()

    def start(self, phase: str) -> None:
        data = self._read_raw()
        data["phases"].append({"phase": phase, "status": "running",
                               "started": _now(), "ended": None})
        self._write(data)

    def finish(self, phase: str, status: str, **extra) -> None:
        data = self._read_raw()
        for entry in reversed(data["phases"]):
            if entry["phase"] == phase and entry["status"] == "running":
                entry.update(status=status, ended=_now(), **extra)
                break
        else:
            data["phases"].append({"phase": phase, "status": status,
                                   "started": _now(), "ended": _now(), **extra})
        self._write(data)

    def fail_running(self, error: str) -> None:
        """Close whatever phase was still open, as failed.

        A run that dies inside a phase otherwise leaves a state file
        claiming it is still running - which is what the dead man's
        switch and every later reader see.
        """
        data = self._read_raw()
        for entry in reversed(data["phases"]):
            if entry["status"] == "running":
                entry.update(status="failed", ended=_now(), error=error)
                self._write(data)
                return

    def machine_result(self, machine: str, status: str, **extra) -> None:
        data = self._read_raw()
        data["machines"][machine] = {"status": status, "recorded": _now(), **extra}
        self._write(data)


def last_state(state_dir: Path) -> dict | None:
    """Newest run, or None if nothing ran yet."""
    runs = sorted(Path(state_dir).glob("2*.json"))
    if not runs:
        return None
    return json.loads(runs[-1].read_text(encoding="utf-8"))


@contextmanager
def acquire_lock(state_dir: Path):
    """Refuse to start while another run holds the lock."""
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    lock_path = Path(state_dir) / "run.lock"
    handle = lock_path.open("w")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Ein Build läuft bereits (Sperre: {lock_path})") from exc
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield lock_path
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
        lock_path.unlink(missing_ok=True)
