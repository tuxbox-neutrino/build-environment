#!/usr/bin/env python3
"""
Tuxbox-OS Builder - Command Line Interface

Production-ready build orchestrator for Tuxbox-Neutrino.
Manages OE-Alliance integration, submodules, configuration, and builds.
"""

import argparse
import configparser
import contextlib
import io
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ANSI Colors
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'


# Disk-space thresholds for image builds (GB of free space on the build fs).
RECOMMENDED_DISK_GB = 100  # below this: warn, build continues
MIN_DISK_GB = 15           # below this: hard-abort before bitbake starts


def _resolve_min_disk_gb() -> float:
    """Hard disk-space floor, overridable via TUXBOX_MIN_DISK_GB env var."""
    raw = os.environ.get('TUXBOX_MIN_DISK_GB')
    if raw is None:
        return MIN_DISK_GB
    try:
        value = float(raw)
        return value if value >= 0 else MIN_DISK_GB
    except (TypeError, ValueError):
        return MIN_DISK_GB


class TuxboxBuilder:
    """Main builder class orchestrating all build operations."""

    def __init__(self):
        self.topdir = Path(__file__).parent.resolve()
        self.state_file = self.topdir / '.tuxbox' / 'state.json'
        self.preferred_builddir = self.topdir / 'builds'
        self.legacy_builddir = self.topdir / 'build'
        self.global_conf_dir = self.preferred_builddir / 'conf'
        self.workspace_dir = self.preferred_builddir / 'workspace'
        self.legacy_workspace_dir = self.legacy_builddir / 'workspace'
        self.builddir = self._default_non_coolstream_builddir()
        self.dl_dir = self.topdir / 'downloads'
        self.sstate_dir = self.topdir / 'sstate-cache'
        self._brand_machine_cache: Optional[Dict[str, List[str]]] = None
        self._machine_brand_cache: Optional[Dict[str, str]] = None

        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, color: str = Colors.RESET, bold: bool = False):
        """Colored logging output."""
        prefix = Colors.BOLD if bold else ''
        print(f"{prefix}{color}{message}{Colors.RESET}")

    def error(self, message: str):
        """Error logging."""
        self.log(f"ERROR: {message}", Colors.RED, bold=True)

    def success(self, message: str):
        """Success logging."""
        self.log(f"✓ {message}", Colors.GREEN)

    def warning(self, message: str):
        """Warning logging."""
        self.log(f"⚠ {message}", Colors.YELLOW)

    def info(self, message: str):
        """Info logging."""
        self.log(message, Colors.CYAN)

    def _free_gb(self, path: Path) -> float:
        """Free space (GB) on the filesystem holding ``path``.

        Walks up to the nearest existing parent so it also works for a build
        directory that has not been created yet.
        """
        probe = Path(path)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        stat = os.statvfs(probe)
        return (stat.f_bavail * stat.f_frsize) / (1024**3)

    def _disk_full_hint(self):
        """Print actionable cleanup hints for an out-of-space build fs."""
        self.info("Bitte Speicher freigeben und erneut starten, z. B.:")
        self.info("  - make clean")
        self.info("  - alte Build-Artefakte: rm -rf builds/<machine>/tmp*")
        self.info("  - Cache/Downloads aufraeumen: sstate-cache/ , downloads/")

    @staticmethod
    def _read_int(path: str) -> Optional[int]:
        try:
            with open(path) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def _inotify_limits(self) -> Tuple[Optional[int], Optional[int]]:
        """Return (max_user_instances, max_user_watches) or (None, None)."""
        return (
            self._read_int('/proc/sys/fs/inotify/max_user_instances'),
            self._read_int('/proc/sys/fs/inotify/max_user_watches'),
        )

    def _explain_enospc(self):
        """Explain a bitbake ENOSPC abort, distinguishing disk vs inotify.

        ``add_watch ... ENOSPC`` from pyinotify can mean either a full build
        filesystem OR an exhausted inotify limit. We disambiguate by checking
        the actual free space, so the user gets the right remedy.
        """
        free_gb = self._free_gb(self.builddir)
        if free_gb < _resolve_min_disk_gb():
            self.error(
                f"Build abgebrochen: Speicher voll "
                f"(nur noch {free_gb:.1f}GB frei auf dem Build-Dateisystem)."
            )
            self.info(f"Build-Verzeichnis: {self.builddir}")
            self._disk_full_hint()
            return

        instances, watches = self._inotify_limits()
        self.error(
            "Build abgebrochen: inotify-Limit erreicht "
            "(kein Speicherproblem - die Platte hat genug Platz)."
        )
        self.info(
            "bitbake/pyinotify konnte keine weitere Datei ueberwachen "
            "(add_watch ... ENOSPC)."
        )
        if instances is not None:
            self.info(f"Aktuelles fs.inotify.max_user_instances: {instances}")
        if watches is not None:
            self.info(f"Aktuelles fs.inotify.max_user_watches:   {watches}")
        self.info("Limit temporaer erhoehen und Build neu starten:")
        self.info("  sudo sysctl fs.inotify.max_user_instances=1024")
        self.info("  sudo sysctl fs.inotify.max_user_watches=524288")
        self.info("Dauerhaft (z. B. /etc/sysctl.d/90-inotify.conf):")
        self.info("  fs.inotify.max_user_instances=1024")
        self.info("  fs.inotify.max_user_watches=524288")
        self.info("Tipp: andere inotify-Nutzer schliessen (IDE, weitere Builds).")

    # Signatures of a resource-exhaustion (ENOSPC) abort in bitbake output.
    _ENOSPC_SIGNATURES = (
        'No space left on device',
        'WatchManagerError',
        'add_watch',
        'ENOSPC',
    )

    def _build_log_has_enospc(self, log_path: str) -> bool:
        """True if the captured build log shows an ENOSPC/inotify abort."""
        try:
            with open(log_path, errors='replace') as f:
                text = f.read()
        except OSError:
            return False
        return any(sig in text for sig in self._ENOSPC_SIGNATURES)

    @staticmethod
    def _cleanup_file(path: str):
        try:
            os.unlink(path)
        except OSError:
            pass

    def _default_non_coolstream_builddir(self) -> Path:
        """Return the legacy shared build dir fallback."""
        if (self.legacy_builddir / 'conf' / 'local.conf').exists():
            return self.legacy_builddir
        return self.preferred_builddir

    def _default_builddir_for_machine(self, machine: str) -> Path:
        """Return default build dir for a machine."""
        return self.preferred_builddir / machine

    def _resolve_user_path(self, value) -> Path:
        """Resolve a user-supplied path relative to the current shell."""
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def _shared_conf_dir_for_builddir(self, builddir: Optional[Path] = None) -> Path:
        if not builddir:
            return self.global_conf_dir
        builddir = self._resolve_user_path(builddir)
        if (
            builddir == self.legacy_builddir.resolve()
            or builddir.parent == self.preferred_builddir.resolve()
        ):
            return self.global_conf_dir
        return builddir.parent / 'conf'

    def _global_local_conf(self, builddir: Optional[Path] = None) -> Path:
        return self._shared_conf_dir_for_builddir(builddir) / 'local.conf'

    def _legacy_global_local_user_conf(self, builddir: Optional[Path] = None) -> Path:
        return self._shared_conf_dir_for_builddir(builddir) / 'local.conf.user.inc'

    def _global_bblayers_user_conf(self, builddir: Optional[Path] = None) -> Path:
        return self._shared_conf_dir_for_builddir(builddir) / 'bblayers.conf.user.inc'

    def _machine_conf_sources(self, conf_dir: Path, machine: str) -> List[Path]:
        builddir = conf_dir.parent
        return [
            conf_dir / 'local.conf',
            self._global_local_conf(builddir),
            conf_dir / 'local-feed.inc',
            conf_dir / 'local-image-server.inc',
            conf_dir / f'local.conf.{machine}.inc',
        ]

    def _machine_layer_sources(self, conf_dir: Path) -> List[Path]:
        builddir = conf_dir.parent
        return [
            conf_dir / 'bblayers.conf',
            self._global_bblayers_user_conf(builddir),
            conf_dir / 'bblayers.conf.user.inc',
        ]

    def _discover_builddirs(self) -> List[Path]:
        """Return candidate build dirs ordered by preference."""
        builddirs: List[Path] = []
        if self.preferred_builddir.is_dir():
            for candidate in sorted(self.preferred_builddir.iterdir()):
                if candidate.name in {'conf', 'workspace'}:
                    continue
                if (candidate / 'conf' / 'local.conf').exists() and candidate not in builddirs:
                    builddirs.append(candidate)
        for candidate in (self.legacy_builddir,):
            if (
                candidate.is_dir()
                and (candidate / 'conf' / 'local.conf').exists()
                and candidate not in builddirs
            ):
                builddirs.append(candidate)
        if not builddirs:
            builddirs.append(self.preferred_builddir)
        for path in sorted(p for p in self.topdir.glob('build-*') if p.is_dir()):
            if path not in builddirs:
                builddirs.append(path)
        return builddirs

    def _tmpdir_override_value(self, target_builddir: Path, machine: str) -> str:
        """Return TMPDIR override string for machine include file examples."""
        return "${TOPDIR}/tmp"

    def _migrate_saved_tmpdir_markers(self, target_builddir: Path) -> int:
        """Rewrite saved_tmpdir markers after one-time build->builds migration."""
        if target_builddir != self.preferred_builddir:
            return 0
        if self.legacy_builddir.exists():
            return 0

        old_prefix = f"{self.legacy_builddir}/"
        new_prefix = f"{self.preferred_builddir}/"
        changed = 0

        markers = list(target_builddir.glob("build/tmp*/saved_tmpdir"))
        markers += list(target_builddir.glob("tmp*/saved_tmpdir"))
        markers += [target_builddir / "tmp/saved_tmpdir"]

        seen: Set[Path] = set()
        for marker in markers:
            if marker in seen or not marker.exists() or not marker.is_file():
                continue
            seen.add(marker)
            try:
                saved = marker.read_text(errors='ignore').strip()
            except OSError:
                continue
            if not saved.startswith(old_prefix):
                continue
            migrated = saved.replace(old_prefix, new_prefix, 1)
            try:
                marker.write_text(f"{migrated}\n")
            except OSError:
                continue
            changed += 1

        return changed

    def _env_enabled(self, name: str, default: str = "1") -> bool:
        value = os.environ.get(name, default).strip().lower()
        return value not in ("0", "false", "no", "off", "disabled")

    def _local_feed_enabled(self) -> bool:
        return self._env_enabled("LOCAL_FEED", "1")

    def _local_image_server_enabled(self) -> bool:
        return self._env_enabled("LOCAL_IMAGE_SERVER", "1")

    def _detect_primary_ipv4(self) -> str:
        """Return the host IPv4 that should be reachable from the LAN."""
        if shutil.which("ip"):
            proc = subprocess.run(
                ["ip", "-4", "route", "get", "1.1.1.1"],
                capture_output=True,
                text=True,
                check=False,
            )
            match = re.search(r"\bsrc\s+([0-9.]+)", proc.stdout)
            if match:
                return match.group(1)

        if shutil.which("hostname"):
            proc = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                check=False,
            )
            for item in proc.stdout.split():
                if re.match(r"^[0-9]+(?:\.[0-9]+){3}$", item):
                    return item

        return "127.0.0.1"

    def _local_feed_base_url(self, machine: str) -> str:
        explicit = os.environ.get("LOCAL_FEED_BASE_URL", "").strip()
        if explicit:
            return (
                explicit
                .replace("${MACHINE}", machine)
                .replace("{machine}", machine)
                .rstrip("/")
            )

        host = os.environ.get("LOCAL_FEED_HOST", "auto").strip() or "auto"
        if host == "auto":
            host = self._detect_primary_ipv4()
            if host == "127.0.0.1":
                self.warning(
                    "Could not detect a LAN IPv4 for LOCAL_FEED_HOST=auto; "
                    "using 127.0.0.1. Set LOCAL_FEED_HOST to a reachable host IP."
                )
        port = os.environ.get("LOCAL_FEED_PORT", "33333").strip() or "33333"
        return f"http://{host}:{port}/{machine}/ipk"

    def _image_server_base_url(self) -> str:
        explicit = os.environ.get("IMAGE_SERVER_BASE_URL", "").strip()
        if explicit:
            return explicit.rstrip("/")

        host = os.environ.get("IMAGE_SERVER_HOST", "auto").strip() or "auto"
        if host == "auto":
            host = self._detect_primary_ipv4()
            if host == "127.0.0.1":
                self.warning(
                    "Could not detect a LAN IPv4 for IMAGE_SERVER_HOST=auto; "
                    "using 127.0.0.1. Set IMAGE_SERVER_HOST to a reachable host IP."
                )
        port = os.environ.get("IMAGE_SERVER_PORT", "33334").strip() or "33334"
        return f"http://{host}:{port}"

    def _local_image_update_base_url(self) -> str:
        return f"{self._image_server_base_url()}/feed"

    def _bitbake_quote(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _target_produces_image(self, target: str) -> bool:
        return target in {"tuxbox-image", "tuxbox-qemu-image"} or target.endswith("-image")

    def _post_build_image_server_hint(self, machine: str, machinebuild: Optional[str],
                                      target: str, builddir: Path, distro_type: str):
        if not self._target_produces_image(target):
            return

        effective_machinebuild = machinebuild
        deploy_images = builddir / 'tmp' / 'deploy' / 'images' / machine
        online_imagedir = machine
        channel = distro_type if distro_type in ('release', 'beta', 'nightly') else 'release'
        try:
            data = self._deploy_info_data(machine, machinebuild, builddir)
            deploy_images = Path(str(data.get('deploy_images', deploy_images)))
            online_imagedir = str(data.get('online_imagedir', online_imagedir))
            effective_machinebuild = str(data.get('machinebuild') or effective_machinebuild or "")
            manifest_path = Path(str(data.get('manifest', '')))
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(errors='ignore'))
                manifest_channel = str(manifest.get('channel', '')).strip()
                if manifest_channel:
                    channel = manifest_channel
        except (OSError, json.JSONDecodeError, ValueError):
            pass

        image_server_cmd = f"make image-server-start MACHINE={machine}"
        image_server_url_cmd = f"make image-server-url MACHINE={machine}"
        if effective_machinebuild:
            image_server_cmd += f" MACHINEBUILD={effective_machinebuild}"
            image_server_url_cmd += f" MACHINEBUILD={effective_machinebuild}"

        base_url = self._image_server_base_url()
        self.info(f"Image deploy path: {deploy_images}")
        self.info(f"Local Online-Flash server: {image_server_cmd}")
        self.info(f"Online-Flash URL: {base_url}/feed/{channel}/{online_imagedir}")
        self.info(f"Show Neutrino settings: {image_server_url_cmd}")
        online_update_repo = os.environ.get('PORTAL_ONLINE_UPDATE_REPO', '').strip()
        if not online_update_repo:
            online_update_repo = str((self.topdir / '..' / 'online-update').resolve())
        if (Path(online_update_repo) / 'public' / 'admin').is_dir():
            self.info(f"Admin WebIF (browser): {base_url}/admin/")

    def _online_imagedir_slug(self, value: str) -> str:
        """Return a URL/catalog safe image directory identifier."""
        raw = (value or "").strip().lower()
        raw = raw.replace("/", "-")
        raw = re.sub(r"[^a-z0-9_-]+", "-", raw)
        raw = re.sub(r"-+", "-", raw).strip("-")
        return raw or "unknown"

    def _write_if_changed(self, path: Path, content: str):
        if path.exists():
            try:
                if path.read_text() == content:
                    return
            except OSError:
                pass
        with open(path, "w") as f:
            f.write(content)
        self.info(f"Updated: {path}")

    def _ensure_local_feed_include_line(self, local_conf: Path):
        self._ensure_local_include_line(local_conf, "include conf/local-feed.inc")

    def _ensure_local_image_server_include_line(self, local_conf: Path):
        self._ensure_local_include_line(
            local_conf,
            "include conf/local-image-server.inc",
            after_line="include conf/local-feed.inc",
        )

    def _ensure_local_include_line(self, local_conf: Path, include_line: str,
                                   after_line: Optional[str] = None):
        if not local_conf.exists():
            return
        try:
            lines = local_conf.read_text().splitlines()
        except OSError:
            return
        if any(line.strip() == include_line for line in lines):
            return

        insert_at = len(lines)
        if after_line:
            for index, line in enumerate(lines):
                if line.strip() == after_line:
                    insert_at = index + 1
                    break
        if insert_at == len(lines):
            for index, line in enumerate(lines):
                stripped = line.strip()
                if stripped == "include conf/local.conf.${MACHINE}.inc":
                    insert_at = index
                    break
        lines.insert(insert_at, include_line)
        local_conf.write_text("\n".join(lines) + "\n")
        self.info(f"Added local include {include_line}: {local_conf}")

    def ensure_local_feed_config(self, conf_dir: Path, machine: str):
        """Generate local-feed.inc and include it before machine overrides."""
        local_conf = conf_dir / "local.conf"
        local_feed_conf = conf_dir / "local-feed.inc"
        enabled = self._local_feed_enabled()

        if enabled:
            feed_url = self._local_feed_base_url(machine)
            content = (
                "# Local package feed generated by tuxbox-os-builder.\n"
                "# Override IPK_FEED_SERVER in builds/conf/local.conf for public feeds.\n"
                f"IPK_FEED_SERVER ?= \"{feed_url}\"\n"
            )
        else:
            content = (
                "# Local package feed generated by tuxbox-os-builder.\n"
                "# LOCAL_FEED=0 disables the automatic IPK_FEED_SERVER default.\n"
            )

        self._write_if_changed(local_feed_conf, content)
        self._ensure_local_feed_include_line(local_conf)

    def ensure_local_image_server_config(self, conf_dir: Path, machine: str):
        """Generate local-image-server.inc for image-version Online-Flash URLs."""
        local_conf = conf_dir / "local.conf"
        local_image_conf = conf_dir / "local-image-server.inc"
        enabled = self._local_image_server_enabled()

        if enabled:
            image_update_base_url = self._local_image_update_base_url()
            content = (
                "# Local Online-Flash image server generated by tuxbox-os-builder.\n"
                "# IPK package feeds use conf/local-feed.inc and port 33333.\n"
                "# This base URL is combined with channel and TUXBOX_IMAGE_DIR for /etc/image-version.\n"
                f"TUXBOX_IMAGE_UPDATE_BASE_URL ?= \"{self._bitbake_quote(image_update_base_url)}\"\n"
                "TUXBOX_IMAGE_MANIFEST_FILE ?= \"manifest.json\"\n"
                "# Local/private URLs use Neutrino's LOCAL_SERVICE_KEY fallback; no real image key is generated here.\n"
            )
            service_key = os.environ.get("TUXBOX_SERVICE_KEY", "").strip()
            if service_key:
                content += f"TUXBOX_SERVICE_KEY ?= \"{self._bitbake_quote(service_key)}\"\n"
        else:
            content = (
                "# Local Online-Flash image server generated by tuxbox-os-builder.\n"
                "# LOCAL_IMAGE_SERVER=0 disables the automatic TUXBOX_IMAGE_UPDATE_BASE_URL default.\n"
            )

        self._write_if_changed(local_image_conf, content)
        self._ensure_local_image_server_include_line(local_conf)

    def _post_build_local_feed(self, machine: str, target: str, builddir: Path):
        """Publish the current deploy/ipk tree and start the local feed server."""
        if not self._local_feed_enabled():
            self.info("Local feed: disabled")
            return

        feed_targets = {"tuxbox-image", "tuxbox-qemu-image", "package-index"}
        if target not in feed_targets and not target.endswith("-image"):
            return

        script = self.topdir / "scripts" / "feed-server.sh"
        if not script.exists():
            self.warning(f"Local feed server helper missing: {script}")
            return

        env = os.environ.copy()
        publish_cmd = [
            str(script),
            "publish",
            "--machine",
            machine,
            "--builddir",
            str(builddir),
        ]
        publish = subprocess.run(
            publish_cmd,
            cwd=self.topdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if publish.returncode != 0:
            message = (publish.stderr or publish.stdout).strip()
            self.warning(f"Local feed publish failed: {message}")
        elif publish.stdout.strip():
            self.info(publish.stdout.strip())

        start_cmd = [str(script), "start", "--machine", machine]
        start = subprocess.run(
            start_cmd,
            cwd=self.topdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if start.returncode != 0:
            message = (start.stderr or start.stdout).strip()
            self.warning(f"Local feed server start failed: {message}")
        elif start.stdout.strip():
            self.info(start.stdout.strip())

    def run_cmd(self, cmd: List[str], cwd: Optional[Path] = None,
                check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command with error handling."""
        try:
            if capture:
                result = subprocess.run(
                    cmd, cwd=cwd, check=check,
                    capture_output=True, text=True
                )
            else:
                result = subprocess.run(cmd, cwd=cwd, check=check)
            return result
        except subprocess.CalledProcessError as e:
            self.error(f"Command failed: {' '.join(cmd)}")
            if capture and e.stderr:
                self.error(e.stderr)
            sys.exit(1)

    def load_state(self) -> Dict:
        """Load build state from JSON file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def save_state(self, state: Dict):
        """Save build state to JSON file."""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def check_prerequisites(self) -> bool:
        """Check system prerequisites for building."""
        self.log("Checking system prerequisites...", Colors.BOLD, bold=True)

        required_cmds = [
            'git', 'gcc', 'g++', 'make', 'python3', 'patch', 'diffstat',
            'tar', 'gzip', 'bzip2', 'xz', 'lz4', 'unzip', 'wget', 'curl',
            'luajit'
        ]

        missing = []
        for cmd in required_cmds:
            result = self.run_cmd(['which', cmd], capture=True, check=False)
            if result.returncode != 0:
                missing.append(cmd)

        multilib_missing = False
        if platform.machine() in ('x86_64', 'amd64') and 'gcc' not in missing and 'g++' not in missing:
            multilib_missing = not self._check_multilib_compiler()

        if missing:
            self.error(f"Missing required tools: {', '.join(missing)}")
            self.info("\nInstall on Debian/Ubuntu:")
            self.info("sudo apt install -y gawk wget git diffstat unzip texinfo \\")
            self.info("  gcc g++ build-essential chrpath socat cpio python3 python3-pip \\")
            self.info("  python3-pexpect xz-utils debianutils iputils-ping python3-git \\")
            self.info("  python3-jinja2 python3-subunit zstd lz4 file locales libacl1 luajit")

        if multilib_missing:
            self.error("Missing 32-bit compiler/multilib support (gcc/g++ -m32)")
            self.info("\nInstall on Debian/Ubuntu:")
            self.info("sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386")

        if missing or multilib_missing:
            return False

        # Check disk space
        free_gb = self._free_gb(self.topdir)

        if free_gb < RECOMMENDED_DISK_GB:
            self.warning(
                f"Only {free_gb:.1f}GB free space. "
                f"Recommended: {RECOMMENDED_DISK_GB}GB+"
            )
        else:
            self.success(f"Disk space OK: {free_gb:.1f}GB free")

        # Check Python version
        py_version = sys.version_info
        if py_version < (3, 6):
            self.error(f"Python 3.6+ required. Found: {py_version.major}.{py_version.minor}")
            return False

        self.success("All prerequisites met")
        return True

    def _check_multilib_compiler(self) -> bool:
        """Verify that 32-bit host binaries can be built on 64-bit hosts."""
        checks = [
            ('gcc', 'int main(void) { return 0; }', 'test.c'),
            ('g++', 'int main() { return 0; }', 'test.cpp'),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for compiler, source, filename in checks:
                src = tmp / filename
                out = tmp / f'{compiler}-m32-test'
                src.write_text(source)
                result = self.run_cmd(
                    [compiler, '-m32', str(src), '-o', str(out)],
                    capture=True,
                    check=False,
                )
                if result.returncode != 0:
                    return False
        return True

    def init_submodules(self):
        """Initialize and update git submodules."""
        self.log("Initializing git submodules...", Colors.BOLD, bold=True)

        # Check if .gitmodules exists
        gitmodules = self.topdir / '.gitmodules'
        if not gitmodules.exists():
            self.warning("No .gitmodules found. Creating stub for manual configuration.")
            gitmodules.write_text("""# Git Submodules for Tuxbox-OS Builder
#
# Add submodules manually:
#   git submodule add <URL> <path>
#
# Example:
#   git submodule add https://github.com/oe-alliance/oe-alliance-core.git oe-alliance
#   git submodule add https://github.com/tuxbox-neutrino/meta-neutrino.git meta-neutrino
""")
            self.info("Please add submodules manually and run init again.")
            return

        # Update submodules
        self.run_cmd(['git', 'submodule', 'init'])
        self.run_cmd(['git', 'submodule', 'update', '--recursive'])

        self.success("Submodules initialized")

    def _load_brand_machines(self) -> Dict[str, List[str]]:
        """Load machine lists from OE-Alliance meta-brands (cached)."""
        if self._brand_machine_cache is not None:
            return self._brand_machine_cache

        brand_map: Dict[str, List[str]] = {}
        machine_map: Dict[str, str] = {}
        brands_dir = self.topdir / 'oe-alliance' / 'meta-brands'
        if brands_dir.exists():
            for meta_dir in sorted(brands_dir.iterdir()):
                if not meta_dir.is_dir():
                    continue
                if not meta_dir.name.startswith('meta-'):
                    continue
                conf_dir = meta_dir / 'conf' / 'machine'
                if not conf_dir.is_dir():
                    continue
                machines = sorted(
                    p.stem for p in conf_dir.glob('*.conf') if p.is_file()
                )
                if not machines:
                    continue
                brand = meta_dir.name[len('meta-'):]
                brand_map[brand] = machines
                for machine in machines:
                    machine_map.setdefault(machine, brand)

        self._brand_machine_cache = brand_map
        self._machine_brand_cache = machine_map
        return brand_map

    def _brand_summary_lines(self, max_brands: int = 5, max_machines: int = 6) -> List[str]:
        """Return a short, readable list of brands and example machines."""
        brand_map = self._load_brand_machines()
        if not brand_map:
            return []

        preferred = [
            'gfutures',
            'airdigital',
            'vuplus',
            'coolstream',
            'ini',
            'edision',
        ]
        lines: List[str] = []
        seen = set()

        for brand in preferred + sorted(brand_map.keys()):
            if brand in seen or brand not in brand_map:
                continue
            machines = brand_map[brand]
            if not machines:
                continue
            sample = ", ".join(machines[:max_machines])
            extra = len(machines) - max_machines
            if extra > 0:
                sample = f"{sample}, ... (+{extra} more)"
            lines.append(f"{brand}: {sample}")
            seen.add(brand)
            if len(lines) >= max_brands:
                break

        remaining = len(brand_map) - len(seen)
        if remaining > 0:
            lines.append(f"... {remaining} more brands")
        return lines

    def _brand_summary_rows(self, max_brands: int = 5, max_machines: int = 6) -> List[Tuple[str, str]]:
        """Return short brand -> machines rows for tabular display."""
        brand_map = self._load_brand_machines()
        if not brand_map:
            return []

        preferred = [
            'gfutures',
            'airdigital',
            'vuplus',
            'coolstream',
            'ini',
            'edision',
        ]
        rows: List[Tuple[str, str]] = []
        seen = set()

        for brand in preferred + sorted(brand_map.keys()):
            if brand in seen or brand not in brand_map:
                continue
            machines = brand_map[brand]
            if not machines:
                continue
            sample = ", ".join(machines[:max_machines])
            extra = len(machines) - max_machines
            if extra > 0:
                sample = f"{sample}, ... (+{extra} more)"
            rows.append((brand, sample))
            seen.add(brand)
            if len(rows) >= max_brands:
                break

        remaining = len(brand_map) - len(seen)
        if remaining > 0:
            rows.append(("...", f"{remaining} more brands"))
        return rows

    def _print_kv_table(self, title: str, rows: List[Tuple[str, str]]):
        if not rows:
            return
        self.log(title, Colors.BOLD, bold=True)
        width = max(len(key) for key, _ in rows)
        for key, value in rows:
            self.info(f"  {key:<{width}} : {value}")

    def _print_table(self, title: str, headers: List[str], rows: List[Tuple[str, ...]]):
        if not rows:
            return
        self.log(title, Colors.BOLD, bold=True)
        col_widths = [len(header) for header in headers]
        for row in rows:
            for idx, cell in enumerate(row):
                col_widths[idx] = max(col_widths[idx], len(str(cell)))

        header_line = "  " + "  ".join(
            f"{headers[idx]:<{col_widths[idx]}}" for idx in range(len(headers))
        )
        self.info(header_line)
        self.info("  " + "  ".join("-" * width for width in col_widths))
        for row in rows:
            row_line = "  " + "  ".join(
                f"{str(row[idx]):<{col_widths[idx]}}" for idx in range(len(headers))
            )
            self.info(row_line)

    def _extract_includes(self, text: str) -> List[str]:
        includes: List[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if not (stripped.startswith('include ') or stripped.startswith('require ')):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            includes.append(parts[1])
        return includes

    def _resolve_include(self, include_path: str, layer_root: Path, current_file: Path) -> Optional[Path]:
        candidate = None
        if include_path.startswith('conf/'):
            candidate = layer_root / include_path
        else:
            candidate = (current_file.parent / include_path)
            if not candidate.exists():
                candidate = layer_root / include_path
        if candidate.exists():
            return candidate
        return None

    def _extract_machinebuild_values(self, text: str) -> List[str]:
        pattern = re.compile(r"['\"]MACHINEBUILD['\"]\s*,\s*['\"]([^'\"]+)['\"]")
        return [match for match in pattern.findall(text) if match]

    def _extract_machinebuild_pairs(self, text: str) -> List[Tuple[str, str]]:
        pattern = re.compile(
            r"contains\(\s*['\"]MACHINEBUILD['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]*)['\"]"
        )
        return [(build.strip(), value.strip()) for build, value in pattern.findall(text) if build]

    def _normalize_machine_value(self, value: str) -> Optional[str]:
        cleaned = value.strip()
        if not cleaned or '$' in cleaned:
            return None
        if '/' in cleaned:
            cleaned = cleaned.split('/')[-1]
        cleaned = cleaned.strip().lower()
        return cleaned or None

    def _collect_machinebuilds_from_oem(self, oem_path: Path) -> Dict[str, List[Tuple[str, str]]]:
        mapping = {'imagedir': [], 'driver': []}
        if not oem_path.exists():
            return mapping
        try:
            text = oem_path.read_text(errors='ignore')
        except OSError:
            return mapping

        current = None
        in_block = False
        start_block = re.compile(r'^(IMAGEDIR|MACHINE_DRIVER)\s*(?:\?=|=)\s*\"\\\s*$')
        single_line = re.compile(r'^(IMAGEDIR|MACHINE_DRIVER)\s*(?:\?=|=)\s*\".*\"$')

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if start_block.match(stripped):
                current = 'imagedir' if stripped.startswith('IMAGEDIR') else 'driver'
                in_block = True
                continue
            if single_line.match(stripped):
                current = None
                in_block = False
                continue
            if in_block and current:
                for build, value in self._extract_machinebuild_pairs(stripped):
                    mapping[current].append((build, value))
                if stripped == '"' or (stripped.endswith('"') and not stripped.endswith('\\"')):
                    in_block = False
                    current = None

        return mapping

    def _machinebuilds_from_oem(self, brand: str, machines: List[str]) -> Dict[str, Dict[str, Set[str]]]:
        layer_root = self.topdir / 'oe-alliance' / 'meta-brands' / f"meta-{brand}"
        include_dir = layer_root / 'conf' / 'machine' / 'include'
        machine_lookup = {m.lower(): m for m in machines}
        oem_map: Dict[str, Dict[str, Set[str]]] = {
            machine: {'imagedir': set(), 'driver': set()} for machine in machines
        }
        if not include_dir.is_dir():
            return oem_map

        for oem_file in include_dir.glob('*oem.inc'):
            mapping = self._collect_machinebuilds_from_oem(oem_file)
            for source_key, pairs in mapping.items():
                for build, value in pairs:
                    target = self._normalize_machine_value(value)
                    if not target:
                        continue
                    machine = machine_lookup.get(target)
                    if machine:
                        oem_map[machine][source_key].add(build)

        return oem_map

    def _collect_machinebuilds_from_conf(self, conf_path: Path, layer_root: Path) -> List[str]:
        builds = set()
        queue = [conf_path]
        seen = set()

        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)

            if path.name.endswith('oem.inc'):
                continue

            try:
                text = path.read_text(errors='ignore')
            except OSError:
                continue

            for value in self._extract_machinebuild_values(text):
                builds.add(value)

            for include in self._extract_includes(text):
                if include.endswith('oem.inc'):
                    continue
                resolved = self._resolve_include(include, layer_root, path)
                if resolved:
                    queue.append(resolved)

        return sorted(builds)

    def _machinebuilds_for_brand(self, brand: str, machines: List[str]) -> Dict[str, Dict[str, Set[str]]]:
        layer_root = self.topdir / 'oe-alliance' / 'meta-brands' / f"meta-{brand}"
        conf_dir = layer_root / 'conf' / 'machine'
        if not conf_dir.is_dir():
            return {
                machine: {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
                for machine in machines
            }

        build_map: Dict[str, set] = {machine: set() for machine in machines}
        for machine in machines:
            conf_path = conf_dir / f"{machine}.conf"
            if not conf_path.exists():
                continue
            for value in self._collect_machinebuilds_from_conf(conf_path, layer_root):
                build_map[machine].add(value)

        oem_map = self._machinebuilds_from_oem(brand, machines)
        result: Dict[str, Dict[str, Set[str]]] = {}
        for machine in machines:
            result[machine] = {
                'explicit': set(build_map.get(machine, set())),
                'oem_imagedir': set(oem_map.get(machine, {}).get('imagedir', set())),
                'oem_driver': set(oem_map.get(machine, {}).get('driver', set())),
            }
        return result

    def _format_machinebuild_list(self, build_info: Dict[str, Set[str]]) -> List[str]:
        explicit = sorted(build_info.get('explicit', set()))
        oem_imagedir = set(build_info.get('oem_imagedir', set()))
        oem_driver = set(build_info.get('oem_driver', set()))
        builds = list(explicit)
        inferred = sorted((oem_imagedir | oem_driver) - set(explicit))
        for build in inferred:
            labels = []
            if build in oem_imagedir:
                labels.append('imagedir')
            if build in oem_driver:
                labels.append('driver')
            label = f"oem:{'+'.join(labels)}" if labels else "oem"
            builds.append(f"{build} ({label})")
        return builds

    def _machinebuild_candidates(self, machine: str) -> Tuple[List[str], List[str]]:
        brand_map = self._load_brand_machines()
        brand = self._machine_brand_cache.get(machine) if self._machine_brand_cache else None
        if not brand:
            return [], []
        machines = brand_map.get(brand, [])
        builds_map = self._machinebuilds_for_brand(brand, machines)
        build_info = builds_map.get(
            machine, {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
        )
        build_names = sorted(
            set(build_info.get('explicit', set()))
            | set(build_info.get('oem_imagedir', set()))
            | set(build_info.get('oem_driver', set()))
        )
        return build_names, self._format_machinebuild_list(build_info)

    def _validate_machinebuild(self, machine: str, machinebuild: Optional[str]):
        if not machinebuild:
            return
        build_names, build_display = self._machinebuild_candidates(machine)
        if not build_names:
            return
        if machinebuild in build_names:
            return
        self.error(f"Invalid MACHINEBUILD '{machinebuild}' for MACHINE '{machine}'.")
        self.info(f"Available: {', '.join(build_display)}")
        sys.exit(1)

    def _oem_values_for_machinebuild(self, brand: str, machinebuild: str) -> Dict[str, Set[str]]:
        values = {'imagedir': set(), 'driver': set()}
        layer_root = self.topdir / 'oe-alliance' / 'meta-brands' / f"meta-{brand}"
        include_dir = layer_root / 'conf' / 'machine' / 'include'
        if not include_dir.is_dir():
            return values

        for oem_file in include_dir.glob('*oem.inc'):
            mapping = self._collect_machinebuilds_from_oem(oem_file)
            for key in ['imagedir', 'driver']:
                for build, value in mapping.get(key, []):
                    if build == machinebuild and value:
                        values[key].add(value)
        return values

    def _read_conf_value(self, conf_path: Path, key: str) -> Optional[str]:
        if not conf_path.exists():
            return None
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*(?:\?\?=|\?=|=)\s*['\"]([^'\"]+)['\"]")
        try:
            text = conf_path.read_text(errors='ignore')
        except OSError:
            return None
        for line in text.splitlines():
            if line.strip().startswith('#'):
                continue
            match = pattern.match(line)
            if match:
                return match.group(1).strip()
        return None

    def _read_machine_values_from_conf(self, conf_dir: Path) -> Tuple[Optional[str], Optional[str]]:
        local_conf = conf_dir / 'local.conf'
        if not local_conf.exists():
            return None, None

        machine = self._read_conf_value(local_conf, 'MACHINE')
        machinebuild = self._read_conf_value(local_conf, 'MACHINEBUILD')

        user_conf = conf_dir / 'local.conf.user.inc'
        if user_conf.exists():
            machine_override = self._read_conf_value(user_conf, 'MACHINE')
            machinebuild_override = self._read_conf_value(user_conf, 'MACHINEBUILD')
            if machine_override:
                machine = machine_override
            if machinebuild_override:
                machinebuild = machinebuild_override

        if machine:
            machine_conf = conf_dir / f'local.conf.{machine}.inc'
            if machine_conf.exists():
                machine_override = self._read_conf_value(machine_conf, 'MACHINE')
                machinebuild_override = self._read_conf_value(machine_conf, 'MACHINEBUILD')
                if machine_override:
                    machine = machine_override
                if machinebuild_override:
                    machinebuild = machinebuild_override

        return machine, machinebuild

    def _find_image_immediate_assignments(self, conf_paths: List[Path]) -> List[str]:
        issues = []
        for conf_path in conf_paths:
            if not conf_path.exists():
                continue
            try:
                text = conf_path.read_text(errors='ignore')
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or ':=' not in stripped:
                    continue
                if not (
                    stripped.startswith('IMAGE_NAME')
                    or stripped.startswith('IMAGE_VER_STRING')
                    or stripped.startswith('IMAGE_NAME_SUFFIX')
                ):
                    continue
                if 'DATE' in stripped or 'DATETIME' in stripped:
                    issues.append(f"{conf_path}:{idx}: {stripped}")
        return issues

    def _discover_build_configs(self, builddir_hint: Optional[Path] = None) -> List[Dict[str, Optional[str]]]:
        builddirs: List[Path]
        if builddir_hint:
            builddirs = [builddir_hint]
        else:
            builddirs = self._discover_builddirs()

        configs = []
        for builddir in builddirs:
            conf_dir = builddir / 'conf'
            local_conf = conf_dir / 'local.conf'
            if not local_conf.exists():
                continue
            machine, machinebuild = self._read_machine_values_from_conf(conf_dir)
            configs.append({
                'builddir': str(builddir),
                'machine': machine,
                'machinebuild': machinebuild,
            })
        return configs

    def _select_build_config(self, builddir_hint: Optional[Path] = None) -> Optional[Dict[str, Optional[str]]]:
        configs = self._discover_build_configs(builddir_hint)
        if not configs:
            return None
        if len(configs) == 1:
            return configs[0]
        if not builddir_hint:
            preferred_matches = [
                item for item in configs
                if item.get('builddir') and Path(item['builddir']) == self.preferred_builddir
            ]
            if len(preferred_matches) == 1:
                return preferred_matches[0]
        if not sys.stdin.isatty():
            self.error("Multiple build configs found. Specify --machine or --builddir.")
            for idx, item in enumerate(configs, start=1):
                builddir = item.get('builddir') or '?'
                machine = item.get('machine') or '?'
                machinebuild = item.get('machinebuild') or '-'
                self.info(f"  {idx}) {builddir} (MACHINE={machine}, MACHINEBUILD={machinebuild})")
            sys.exit(1)

        self.info("Multiple build configs found:")
        for idx, item in enumerate(configs, start=1):
            builddir = item.get('builddir') or '?'
            machine = item.get('machine') or '?'
            machinebuild = item.get('machinebuild') or '-'
            self.info(f"  {idx}) {builddir} (MACHINE={machine}, MACHINEBUILD={machinebuild})")

        while True:
            choice = input("Select config [1-{}]: ".format(len(configs))).strip()
            if not choice:
                continue
            if choice.isdigit():
                index = int(choice)
                if 1 <= index <= len(configs):
                    return configs[index - 1]
            self.warning("Invalid selection. Try again.")

    def _read_conf_values_with_sources(self, conf_paths: List[Path], keys: List[str]) -> Dict[str, Tuple[Optional[str], Optional[Path]]]:
        values: Dict[str, Tuple[Optional[str], Optional[Path]]] = {key: (None, None) for key in keys}
        key_pattern = "|".join(re.escape(key) for key in keys)
        pattern = re.compile(rf"^\s*({key_pattern})\s*(?:\?\?=|\?=|=)\s*['\"]([^'\"]+)['\"]")

        for conf_path in conf_paths:
            if not conf_path.exists():
                continue
            try:
                text = conf_path.read_text(errors='ignore')
            except OSError:
                continue
            for line in text.splitlines():
                if line.strip().startswith('#'):
                    continue
                match = pattern.match(line)
                if match:
                    key = match.group(1)
                    values[key] = (match.group(2).strip(), conf_path)
        return values

    def _format_conf_source(self, source: Optional[Path], conf_dir: Path) -> str:
        if not source:
            return "unknown"
        try:
            return str(source.relative_to(conf_dir))
        except ValueError:
            return str(source)

    def _resolve_topdir_in_path(self, value: Optional[str], build_dir: Optional[str]) -> Optional[str]:
        """Resolve TOPDIR placeholders to a concrete build directory path."""
        if not value:
            return value
        topdir = build_dir or str(self.builddir)
        return value.replace("${TOPDIR}", topdir).replace("$TOPDIR", topdir)

    def _extract_layer_paths(self, conf_path: Path) -> List[str]:
        if not conf_path.exists():
            return []
        try:
            text = conf_path.read_text(errors='ignore')
        except OSError:
            return []
        layers = []
        topdir_str = str(self.topdir)
        for line in text.splitlines():
            if line.strip().startswith('include '):
                continue
            for match in re.findall(r"(/[^\s\"']+)", line):
                if not match.startswith(topdir_str):
                    continue
                if match not in layers:
                    layers.append(match)
        return layers

    def detect_machine_brand(self, machine: str) -> str:
        """Detect the brand/manufacturer for a given machine."""
        self._load_brand_machines()
        if self._machine_brand_cache and machine in self._machine_brand_cache:
            return self._machine_brand_cache[machine]

        # Fallback mapping for common machines (when submodules are not ready)
        machine_brands = {
            'hd51': 'gfutures',
            'hd60': 'gfutures',
            'hd61': 'gfutures',
            'zgemmah7': 'airdigital',
            'h7s': 'airdigital',
            'h7c': 'airdigital',
            'tank': 'coolstream',
            'ultimo4k': 'vuplus',
            'uno4k': 'vuplus',
            'duo4k': 'vuplus',
        }

        return machine_brands.get(machine, 'unknown')

    def _git_output(self, path: Path, args: List[str]) -> Optional[str]:
        if not path.exists():
            return None
        result = subprocess.run(
            ['git', '-C', str(path)] + args,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def _layer_ref(self, path: Path) -> Optional[Tuple[str, str, str]]:
        if not self._git_output(path, ['rev-parse', '--git-dir']):
            return None
        branch = self._git_output(path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        commit = self._git_output(path, ['rev-parse', '--short', 'HEAD']) or "-"
        if branch and branch != 'HEAD':
            return ("branch", branch, commit)
        name = self._git_output(path, ['name-rev', '--name-only', '--no-undefined',
                                        '--exclude', 'refs/remotes/origin/HEAD', 'HEAD'])
        if name:
            return ("detached", name, commit)
        return ("detached", "-", commit)

    def _print_layer_refs(self):
        layers = [
            ('poky', self.topdir / 'poky'),
            ('oe-alliance', self.topdir / 'oe-alliance'),
            ('meta-openembedded', self.topdir / 'meta-openembedded'),
            ('meta-neutrino', self.topdir / 'meta-neutrino'),
            ('meta-tuxbox', self.topdir / 'meta-tuxbox'),
        ]
        refs = []
        for name, path in layers:
            ref = self._layer_ref(path)
            if ref:
                state, ref_name, commit = ref
                refs.append((name, state, ref_name, commit))
        if refs:
            self._print_table("Layer refs", ["Layer", "State", "Ref", "Commit"], refs)

    def machines(self, args):
        """List machines by brand using OE-Alliance meta-brands."""
        brand_map = self._load_brand_machines()
        if not brand_map:
            self.error("OE-Alliance meta-brands not found. Run init or check submodules.")
            sys.exit(1)

        if args.brand:
            brand = args.brand
            if brand not in brand_map:
                self.error(f"Unknown brand: {brand}")
                available = ", ".join(sorted(brand_map.keys()))
                self.info(f"Available brands: {available}")
                sys.exit(1)
            brands = [brand]
        else:
            brands = sorted(brand_map.keys())

        for brand in brands:
            machines = brand_map[brand]
            if not args.with_builds:
                self.info(f"{brand}: {', '.join(machines)}")
                continue

            builds_map = self._machinebuilds_for_brand(brand, machines)
            self.info(f"{brand}:")
            pad = max((len(m) for m in machines), default=0)
            for machine in machines:
                build_info = builds_map.get(
                    machine, {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
                )
                builds = self._format_machinebuild_list(build_info)
                build_text = ", ".join(builds) if builds else "-"
                prefix = f"  {machine.ljust(pad)}  builds: "
                width = max(60, 100 - len(prefix))
                wrapped = textwrap.wrap(build_text, width=width) or ["-"]
                for idx, chunk in enumerate(wrapped):
                    if idx == 0:
                        self.info(f"{prefix}{chunk}")
                    else:
                        self.info(f"{' ' * len(prefix)}{chunk}")

    def machine_info(self, args):
        """Show build variants and config path for a specific machine."""
        machine = args.machine
        if not machine:
            self.error("Machine is required (e.g., --machine hd51)")
            sys.exit(1)

        brand_map = self._load_brand_machines()
        if not brand_map:
            self.error("OE-Alliance meta-brands not found. Run init or check submodules.")
            sys.exit(1)

        brand = self._machine_brand_cache.get(machine) if self._machine_brand_cache else None
        if not brand:
            self.error(f"Unknown machine: {machine}")
            available = ", ".join(sorted(brand_map.keys()))
            self.info(f"Available brands: {available}")
            sys.exit(1)

        self.info(f"Machine: {machine}")
        self.info(f"Brand: {brand}")

        layer_root = self.topdir / 'oe-alliance' / 'meta-brands' / f"meta-{brand}"
        machine_conf = layer_root / 'conf' / 'machine' / f"{machine}.conf"
        if machine_conf.exists():
            self.info(f"Config: {machine_conf}")
        else:
            self.warning(f"Config: missing ({machine_conf})")

        builds_map = self._machinebuilds_for_brand(brand, brand_map.get(brand, []))
        build_info = builds_map.get(
            machine, {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
        )

        explicit = sorted(build_info.get('explicit', set()))
        oem_imagedir = sorted(build_info.get('oem_imagedir', set()))
        oem_driver = sorted(build_info.get('oem_driver', set()))

        self.info("")
        self.info("Build variants:")
        self.info(f"  explicit: {', '.join(explicit) if explicit else '-'}")
        self.info(f"  oem:imagedir: {', '.join(oem_imagedir) if oem_imagedir else '-'}")
        self.info(f"  oem:driver: {', '.join(oem_driver) if oem_driver else '-'}")

    def _coolstream_machines(self) -> List[str]:
        conf_dir = self.topdir / 'meta-coolstream' / 'conf' / 'machine'
        if not conf_dir.is_dir():
            return []
        return sorted(p.stem for p in conf_dir.glob('coolstream-*.conf') if p.is_file())

    def _audit_matrix(self, machine: Optional[str] = None,
                      machinebuild: Optional[str] = None,
                      brand_filter: Optional[str] = None) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        brand_map = self._load_brand_machines()

        if machine:
            brand = self.detect_machine_brand(machine)
            if brand == 'unknown' and machine.startswith('coolstream-'):
                brand = 'coolstream'
            builds, _ = self._machinebuild_candidates(machine)
            build_values = [machinebuild] if machinebuild else (builds or [machine])
            for build in build_values:
                rows.append({'brand': brand, 'machine': machine, 'machinebuild': build})
            return rows

        for brand in sorted(brand_map.keys()):
            if brand_filter and brand != brand_filter:
                continue
            machines = brand_map[brand]
            builds_map = self._machinebuilds_for_brand(brand, machines)
            for mach in machines:
                build_info = builds_map.get(
                    mach, {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
                )
                build_names = sorted(
                    set(build_info.get('explicit', set()))
                    | set(build_info.get('oem_imagedir', set()))
                    | set(build_info.get('oem_driver', set()))
                )
                for build in build_names or [mach]:
                    rows.append({'brand': brand, 'machine': mach, 'machinebuild': build})

        if not brand_filter or brand_filter == 'coolstream':
            for mach in self._coolstream_machines():
                rows.append({'brand': 'coolstream', 'machine': mach, 'machinebuild': mach})

        return rows

    def _audit_slug(self, machine: str, machinebuild: str) -> str:
        value = f"{machine}-{machinebuild}"
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', value)

    def _audit_scratch_root(self, requested: Optional[str]) -> Path:
        if requested:
            root = self._resolve_user_path(requested)
            root.mkdir(parents=True, exist_ok=True)
            return root
        Path('/tmp/tuxbox-audit').mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='run-', dir='/tmp/tuxbox-audit'))
        return root

    def _audit_generate_config(self, machine: str, machinebuild: str,
                               builddir: Path, distro: str,
                               distro_type: str) -> Optional[str]:
        if builddir.exists():
            shutil.rmtree(builddir)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.generate_config(machine, distro, distro_type, machinebuild, builddir)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            return f"config generation exited {code}"
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            return f"config generation failed: {exc}"
        return None

    def _audit_read_generated_values(self, builddir: Path, machine: str) -> Dict[str, Optional[str]]:
        conf_dir = builddir / 'conf'
        keys = [
            'MACHINE', 'MACHINEBUILD', 'DISTRO', 'DISTRO_TYPE', 'TMPDIR',
            'IPK_FEED_SERVER', 'TUXBOX_IMAGE_UPDATE_BASE_URL',
            'TUXBOX_IMAGE_UPDATE_URL', 'TUXBOX_IMAGE_MANIFEST_FILE',
        ]
        values_with_sources = self._read_conf_values_with_sources(
            self._machine_conf_sources(conf_dir, machine),
            keys,
        )
        return {key: values_with_sources.get(key, (None, None))[0] for key in keys}

    def _audit_bitbake_keys(self) -> List[str]:
        return [
            'MACHINE',
            'MACHINEBUILD',
            'PREFERRED_PROVIDER_virtual/kernel',
            'PREFERRED_VERSION_linux-gfutures',
            'PREFERRED_VERSION_linux-maxytec',
            'PREFERRED_VERSION_linux-airdigital',
            'PREFERRED_VERSION_linux-coolstream',
            'PN',
            'PV',
            'FILESPATH',
            'SRC_URI',
            'KERNEL_IMAGETYPE',
            'KERNEL_OUTPUT',
            'KERNEL_FILE',
            'IMAGE_FSTYPES',
            'IMAGE_CLASSES',
            'IMAGEDIR',
            'MACHINE_DRIVER',
            'MTD_KERNEL',
            'MTD_ROOTFS',
        ]

    def _audit_parse_bitbake_env(self, builddir: Path,
                                 timeout: int) -> Tuple[Dict[str, str], Optional[str]]:
        oe_init = self.topdir / 'poky' / 'oe-init-build-env'
        if not oe_init.exists():
            return {}, f"missing {oe_init}"
        cmd = (
            f"cd {self.topdir}\n"
            "unset MACHINE MACHINEBUILD BUILDDIR BBPATH\n"
            f"source {oe_init} {builddir} >/dev/null\n"
            "bitbake -e virtual/kernel"
        )
        env = os.environ.copy()
        env.pop('MACHINE', None)
        env.pop('MACHINEBUILD', None)
        proc = subprocess.Popen(
            ['bash', '-c', cmd],
            cwd=self.topdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
            stdout, stderr = proc.communicate()
            return {}, f"bitbake -e timed out after {timeout}s"
        if proc.returncode != 0:
            message = (stderr or stdout).strip().splitlines()
            return {}, message[0] if message else f"bitbake -e exited {proc.returncode}"

        wanted = set(self._audit_bitbake_keys())
        values: Dict[str, str] = {}
        pattern = re.compile(r'^([A-Za-z0-9_+./:-]+)="(.*)"$')
        for line in stdout.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            key, value = match.group(1), match.group(2)
            if key in wanted:
                values[key] = value
        return values, None

    def _audit_defconfig_path(self, env_values: Dict[str, str]) -> str:
        src_uri = env_values.get('SRC_URI', '')
        if 'file://defconfig' not in src_uri:
            return '-'
        filespath = env_values.get('FILESPATH', '')
        for entry in filespath.split(':'):
            if not entry:
                continue
            candidate = Path(entry) / 'defconfig'
            if candidate.exists():
                try:
                    return str(candidate.relative_to(self.topdir))
                except ValueError:
                    return str(candidate)
        return 'missing'

    def _audit_high_risk_keys(self, rows: List[Dict[str, str]]) -> Set[Tuple[str, str]]:
        machines = {
            'hd51', 'hd60', 'hd61', 'hd66se',
            'multibox', 'multiboxse',
            'h7', 'h9', 'h10', 'h11',
            'coolstream-nevis', 'coolstream-tank',
        }
        representative_brands = {'vuplus', 'edision', 'octagon', 'gigablue'}
        keys: Set[Tuple[str, str]] = set()
        seen_brands: Set[str] = set()
        for row in rows:
            key = (row['machine'], row['machinebuild'])
            if row['machine'] in machines:
                keys.add(key)
            brand = row['brand']
            if brand in representative_brands and brand not in seen_brands:
                keys.add(key)
                seen_brands.add(brand)
        return keys

    def _audit_should_bitbake(self, mode: str, row: Dict[str, str],
                              high_risk: Set[Tuple[str, str]],
                              static_errors: List[str],
                              selected: bool) -> bool:
        if mode == 'none':
            return False
        if mode == 'all':
            return True
        if mode == 'selected':
            return selected
        if mode == 'suspicious':
            return bool(static_errors)
        if mode == 'high-risk':
            return (row['machine'], row['machinebuild']) in high_risk or bool(static_errors)
        return False

    def _audit_latest_zip(self, machine: str) -> Optional[Path]:
        candidates: List[Path] = []
        for builddir in self._discover_builddirs():
            candidates.extend(
                builddir.glob(f"tmp/deploy/images/{machine}/*_multi.zip")
            )
            candidates.extend(
                builddir.glob(f"tmp/deploy/images/{machine}/*_usb.zip")
            )
            candidates.extend(
                builddir.glob(f"tmp/deploy/images/{machine}/*_single_mmc.zip")
            )
            candidates.extend(
                builddir.glob(f"**/tmp-{machine}/deploy/images/{machine}/*_multi.zip")
            )
            candidates.extend(
                builddir.glob(f"**/tmp-{machine}/deploy/images/{machine}/*_usb.zip")
            )
            candidates.extend(
                builddir.glob(f"**/tmp-{machine}/deploy/images/{machine}/*_single_mmc.zip")
            )
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _audit_inspect_deploy_zip(self, machine: str, expected_driver: Optional[str],
                                  expected_kernel_file: Optional[str]) -> Tuple[str, List[str]]:
        archive = self._audit_latest_zip(machine)
        if not archive:
            return '-', [f"no deploy zip for {machine}"]
        errors: List[str] = []
        try:
            with zipfile.ZipFile(archive) as zf:
                names = zf.namelist()
                kernel_names = [name for name in names if name.endswith(('kernel.bin', 'uImage'))]
                rootfs_names = [name for name in names if name.endswith('rootfs.tar.bz2')]
                if expected_kernel_file and not any(name.endswith(expected_kernel_file) for name in kernel_names):
                    errors.append(f"deploy missing {expected_kernel_file}")
                if not rootfs_names:
                    errors.append("deploy missing rootfs.tar.bz2")
                if expected_driver and rootfs_names:
                    driver_token = expected_driver.replace('-', '_')
                    package_token = expected_driver.replace('_', '-')
                    found_driver = False
                    wrong_hd60 = False
                    with zf.open(rootfs_names[0]) as rootfs:
                        with tarfile.open(fileobj=rootfs, mode='r:bz2') as tf:
                            for member in tf:
                                name = member.name
                                if f"/{driver_token}_" in name or package_token in name:
                                    found_driver = True
                                if machine == 'multiboxse' and 'gfutures-' in name:
                                    wrong_hd60 = True
                                if found_driver and not wrong_hd60:
                                    break
                    if not found_driver:
                        errors.append(f"deploy rootfs missing driver {expected_driver}")
                    if wrong_hd60:
                        errors.append("multiboxse rootfs contains gfutures packages")
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
            errors.append(f"cannot inspect deploy zip: {exc}")
        return archive.name, errors

    def _audit_live_box(self, machine: str) -> Tuple[str, List[str]]:
        hosts = {'hd51': '192.168.1.54', 'hd60': '192.168.1.99'}
        host = hosts.get(machine)
        if not host:
            return '-', []
        remote = (
            "uname -a; "
            "cat /proc/cmdline 2>/dev/null; "
            "cat /proc/device-tree/model 2>/dev/null; printf '\\n'; "
            "find /lib/modules -maxdepth 1 -mindepth 1 -type d -printf '%f\\n' 2>/dev/null; "
            "opkg list-installed 2>/dev/null | grep -E 'kernel|gfutures|maxytec|dvb|bootargs|partitions|recovery' | head -40; "
            "cat /etc/image-version /var/etc/.version 2>/dev/null | head -40"
        )
        proc = subprocess.run(
            [
                'ssh',
                '-o', 'BatchMode=yes',
                '-o', 'ConnectTimeout=5',
                '-o', 'StrictHostKeyChecking=accept-new',
                f'root@{host}',
                remote,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout).strip().splitlines()
            return host, [message[0] if message else f"ssh exited {proc.returncode}"]
        problems: List[str] = []
        output = proc.stdout
        if machine == 'hd51' and '4.10.12' not in output:
            problems.append("live hd51 is not running 4.10.12")
        if machine == 'hd60' and '4.4.35' not in output:
            problems.append("live hd60 is not running 4.4.35")
        return host, problems

    def audit_machine_mapping(self, args):
        """Audit MACHINE/MACHINEBUILD and kernel mapping without building images."""
        rows = self._audit_matrix(args.machine, args.machinebuild, args.brand)
        if args.limit:
            rows = rows[:args.limit]
        if not rows:
            self.error("No audit rows selected")
            sys.exit(1)

        scratch_root = self._audit_scratch_root(args.scratch_root)
        high_risk = self._audit_high_risk_keys(rows)
        selected = bool(args.machine)
        result_rows: List[Tuple[str, ...]] = []
        json_rows: List[Dict[str, object]] = []
        failed = False

        for row in rows:
            brand = row['brand']
            machine = row['machine']
            machinebuild = row['machinebuild']
            builddir = scratch_root / self._audit_slug(machine, machinebuild)
            errors: List[str] = []
            warnings: List[str] = []
            kernel = '-'
            image_type = '-'
            imagedir = '-'
            driver = '-'

            config_error = self._audit_generate_config(
                machine, machinebuild, builddir, args.distro, args.distro_type
            )
            if config_error:
                errors.append(config_error)
            else:
                values = self._audit_read_generated_values(builddir, machine)
                if values.get('MACHINE') != machine:
                    errors.append(f"local.conf MACHINE={values.get('MACHINE')}")
                if values.get('MACHINEBUILD') != machinebuild:
                    errors.append(f"local.conf MACHINEBUILD={values.get('MACHINEBUILD')}")

                conf_dir = builddir / 'conf'
                bblayers = []
                for layer_source in self._machine_layer_sources(conf_dir):
                    bblayers += self._extract_layer_paths(layer_source)
                if brand == 'coolstream':
                    if not any(path.endswith('/meta-coolstream') for path in bblayers):
                        errors.append("missing meta-coolstream layer")
                elif brand != 'unknown':
                    expected = f"/oe-alliance/meta-brands/meta-{brand}"
                    if not any(expected in path for path in bblayers):
                        errors.append(f"missing meta-{brand} layer")

                builds, display = self._machinebuild_candidates(machine)
                if builds and machinebuild not in builds:
                    errors.append(
                        f"invalid MACHINEBUILD, available: {', '.join(display)}"
                    )

            oem_values = (
                self._oem_values_for_machinebuild(brand, machinebuild)
                if brand not in ('unknown', 'coolstream') else {'imagedir': set(), 'driver': set()}
            )
            if oem_values['imagedir']:
                imagedir = ",".join(sorted(oem_values['imagedir']))
            if oem_values['driver']:
                driver = ",".join(sorted(oem_values['driver']))

            env_values: Dict[str, str] = {}
            bitbake_error = None
            if not errors or args.bitbake in ('all', 'selected', 'high-risk', 'suspicious'):
                if self._audit_should_bitbake(args.bitbake, row, high_risk, errors, selected):
                    env_values, bitbake_error = self._audit_parse_bitbake_env(
                        builddir, args.bitbake_timeout
                    )
                    if bitbake_error:
                        errors.append(f"bitbake: {bitbake_error}")
                    else:
                        resolved_machine = env_values.get('MACHINE')
                        resolved_machinebuild = env_values.get('MACHINEBUILD')
                        if resolved_machine != machine:
                            errors.append(f"bitbake MACHINE={resolved_machine}")
                        if resolved_machinebuild != machinebuild:
                            errors.append(f"bitbake MACHINEBUILD={resolved_machinebuild}")

                        kernel_pn = env_values.get('PN') or env_values.get('PREFERRED_PROVIDER_virtual/kernel') or '-'
                        kernel_pv = env_values.get('PV') or '-'
                        kernel = f"{kernel_pn} {kernel_pv}".strip()
                        image_type = env_values.get('KERNEL_FILE') or env_values.get('KERNEL_IMAGETYPE') or '-'
                        imagedir = env_values.get('IMAGEDIR') or imagedir
                        driver = env_values.get('MACHINE_DRIVER') or driver

                        expected_imagedirs = oem_values['imagedir'] or ({machine} if machinebuild == machine else set())
                        expected_drivers = oem_values['driver'] or ({machine} if machinebuild == machine else set())
                        if expected_imagedirs and imagedir not in expected_imagedirs:
                            errors.append(f"IMAGEDIR={imagedir}")
                        if expected_drivers and driver not in expected_drivers:
                            errors.append(f"MACHINE_DRIVER={driver}")

                        defconfig = self._audit_defconfig_path(env_values)
                        if defconfig == 'missing':
                            errors.append("defconfig missing from FILESPATH")
                        elif defconfig != '-':
                            warnings.append(f"defconfig={defconfig}")

            if args.deploy:
                deploy_name, deploy_errors = self._audit_inspect_deploy_zip(
                    machine,
                    driver if driver != '-' else None,
                    image_type if image_type in ('kernel.bin', 'uImage') else None,
                )
                if deploy_name != '-':
                    warnings.append(f"deploy={deploy_name}")
                errors.extend(deploy_errors)

            if args.live:
                host, live_errors = self._audit_live_box(machine)
                if host != '-':
                    warnings.append(f"live={host}")
                errors.extend(live_errors)

            if errors:
                status = 'FAIL'
                failed = True
                reason = "; ".join(errors[:3])
            elif warnings:
                status = 'PASS'
                reason = "; ".join(warnings[:2])
            else:
                status = 'PASS'
                reason = '-'

            result_rows.append((
                machine,
                machinebuild,
                brand,
                kernel,
                image_type,
                imagedir,
                driver,
                status,
                reason,
            ))
            json_rows.append({
                'machine': machine,
                'machinebuild': machinebuild,
                'brand': brand,
                'kernel': kernel,
                'image': image_type,
                'imagedir': imagedir,
                'driver': driver,
                'status': status,
                'reason': reason,
                'scratch_builddir': str(builddir),
            })

        if args.json:
            print(json.dumps(json_rows, indent=2))
        else:
            self._print_table(
                "Machine/kernel mapping audit",
                ['machine', 'machinebuild', 'brand', 'kernel', 'image',
                 'imagedir', 'driver', 'status', 'reason'],
                result_rows,
            )
            self.info(f"Scratch root: {scratch_root}")

        if not args.keep_scratch:
            shutil.rmtree(scratch_root, ignore_errors=True)

        if failed:
            sys.exit(1)

    def _config_identity(self, conf_dir: Path) -> Tuple[Optional[str], Optional[str]]:
        return self._read_machine_values_from_conf(conf_dir)

    def _config_scan_dirs(self) -> List[Path]:
        """Return legacy and per-machine config dirs that may need migration."""
        dirs: List[Path] = []
        for conf_dir in [
            self.legacy_builddir / 'conf',
            self.preferred_builddir / 'conf',
        ]:
            if (conf_dir / 'local.conf').exists() and conf_dir not in dirs:
                dirs.append(conf_dir)
        for builddir in sorted(self.topdir.glob('build-*')):
            conf_dir = builddir / 'conf'
            if (conf_dir / 'local.conf').exists() and conf_dir not in dirs:
                dirs.append(conf_dir)
        if self.preferred_builddir.is_dir():
            for builddir in sorted(self.preferred_builddir.iterdir()):
                conf_dir = builddir / 'conf'
                if (conf_dir / 'local.conf').exists() and conf_dir not in dirs:
                    dirs.append(conf_dir)
        return dirs

    def _backup_path_for(self, path: Path, backup_root: Path) -> Path:
        try:
            rel = path.resolve().relative_to(self.topdir)
        except ValueError:
            rel = Path(path.name)
        return backup_root / rel

    def _backup_path(self, path: Path, backup_root: Path):
        if not path.exists():
            return
        dst = self._backup_path_for(path, backup_root)
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(
                path,
                dst,
                dirs_exist_ok=True,
                symlinks=True,
                ignore_dangling_symlinks=True,
                ignore=self._backup_ignore,
            )
        else:
            shutil.copy2(path, dst)

    def _backup_ignore(self, directory: str, names: List[str]) -> Set[str]:
        ignored = set()
        for name in names:
            candidate = Path(directory) / name
            if name in {'oe-workdir', 'tmp', 'pseudo'}:
                ignored.add(name)
                continue
            try:
                if candidate.is_socket() or candidate.is_fifo():
                    ignored.add(name)
            except OSError:
                ignored.add(name)
        return ignored

    def _copyable_conf_files(self, src_conf: Path, machine: str) -> List[Path]:
        """Return legacy config files safe to copy into one machine builddir."""
        allowed_names = {
            'local.conf',
            'bblayers.conf',
            'local-feed.inc',
            'local-image-server.inc',
            'local.conf.user.inc',
            'bblayers.conf.user.inc',
            'templateconf.cfg',
            f'local.conf.{machine}.inc',
        }
        return [
            item
            for item in sorted(src_conf.iterdir())
            if item.is_file() and item.name in allowed_names
        ]

    def _copy_conf_dir(self, src_conf: Path, dst_conf: Path, machine: str):
        dst_conf.mkdir(parents=True, exist_ok=True)
        for item in self._copyable_conf_files(src_conf, machine):
            shutil.copy2(item, dst_conf / item.name)

    def _foreign_machine_include_files(self, conf_dir: Path, machine: str) -> List[Path]:
        foreign = []
        for item in sorted(conf_dir.glob('local.conf.*.inc')):
            if not item.is_file():
                continue
            name = item.name
            if name in {'local.conf.user.inc', f'local.conf.{machine}.inc'}:
                continue
            foreign.append(item)
        return foreign

    def _remove_foreign_machine_includes(self, conf_dir: Path, machine: str) -> List[str]:
        removed = []
        for item in self._foreign_machine_include_files(conf_dir, machine):
            try:
                item.unlink()
                removed.append(item.name)
            except OSError:
                pass
        return removed

    def _strip_generated_tmpdir_override(self, conf_dir: Path, machine: str) -> bool:
        machine_conf = conf_dir / f'local.conf.{machine}.inc'
        if not machine_conf.exists():
            return False
        try:
            lines = machine_conf.read_text(errors='ignore').splitlines()
        except OSError:
            return False
        generated_hint = any('Default TMPDIR uses per-machine subdirs' in line for line in lines)
        if not generated_hint:
            return False
        changed = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'^TMPDIR\s*=\s*"\$\{TOPDIR\}/(?:build/)?tmp-[^"]+"$', stripped):
                new_lines.append(f"# Migrated away from generated shared TMPDIR: {stripped}")
                changed = True
            else:
                new_lines.append(line)
        if changed:
            machine_conf.write_text("\n".join(new_lines).rstrip() + "\n")
        return changed

    def _has_generated_tmpdir_override(self, conf_dir: Path, machine: str) -> bool:
        machine_conf = conf_dir / f'local.conf.{machine}.inc'
        if not machine_conf.exists():
            return False
        try:
            text = machine_conf.read_text(errors='ignore')
        except OSError:
            return False
        if 'Default TMPDIR uses per-machine subdirs' not in text:
            return False
        return bool(re.search(r'^\s*TMPDIR\s*=\s*"\$\{TOPDIR\}/(?:build/)?tmp-[^"]+"\s*$', text, re.MULTILINE))

    def _conf_assignment_refs(self, conf_path: Path, keys: Set[str]) -> List[str]:
        if not conf_path.exists():
            return []
        key_pattern = "|".join(re.escape(key) for key in sorted(keys))
        pattern = re.compile(rf"^\s*({key_pattern})\s*(?:\?\?=|\?=|=|:=|\+=|:append\s*=)")
        refs = []
        try:
            lines = conf_path.read_text(errors='ignore').splitlines()
        except OSError:
            return refs
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            match = pattern.match(line)
            if match:
                refs.append(f"{conf_path}:{idx}: {match.group(1)}")
        return refs

    def _central_forbidden_assignment_refs(self, builddir: Optional[Path] = None) -> List[str]:
        forbidden = {'MACHINE', 'MACHINEBUILD', 'TMPDIR', 'TUXBOX_IMAGE_DIR'}
        refs = []
        for conf_path in [
            self._global_local_conf(builddir),
            self._legacy_global_local_user_conf(builddir),
        ]:
            refs.extend(self._conf_assignment_refs(conf_path, forbidden))
        return refs

    def _strip_central_forbidden_lines(self, text: str) -> str:
        forbidden = {'MACHINE', 'MACHINEBUILD', 'TMPDIR', 'TUXBOX_IMAGE_DIR'}
        key_pattern = "|".join(re.escape(key) for key in sorted(forbidden))
        assign_pattern = re.compile(rf"^\s*({key_pattern})\s*(?:\?\?=|\?=|=|:=|\+=|:append\s*=)")
        cleaned = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('include conf/local-feed.inc'):
                continue
            if stripped.startswith('include conf/local-image-server.inc'):
                continue
            if stripped.startswith('include conf/local.conf.user.inc'):
                continue
            if stripped.startswith('include conf/local.conf.${MACHINE}.inc'):
                continue
            if not stripped.startswith('#') and assign_pattern.match(line):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).rstrip() + "\n"

    def _read_text_if_exists(self, path: Path) -> Optional[str]:
        if not path.exists():
            return None
        try:
            return path.read_text(errors='ignore')
        except OSError:
            return None

    def _normalized_conf_text(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()

    def _shared_local_conf_is_generated(self, text: str) -> bool:
        header = "\n".join(text.splitlines()[:12])
        has_generated_marker = "This file is auto-generated by tuxbox-os-builder" in header
        has_local_header = (
            "Shared local configuration for Tuxbox-OS builds" in header
            or "Local configuration for Tuxbox-OS builds" in header
        )
        return has_generated_marker and has_local_header

    def _strip_migrated_generated_local_conf_block(self, text: str) -> Tuple[str, bool]:
        marker = "# Migrated from legacy build/conf/local.conf\n"
        start = text.find(marker)
        if start < 0:
            return text, False
        next_marker = text.find("\n# Migrated from legacy ", start + len(marker))
        if next_marker < 0:
            return text, False
        block = text[start:next_marker]
        if not self._shared_local_conf_is_generated(block):
            return text, False
        cleaned = text[:start].rstrip() + "\n\n" + text[next_marker + 1:].lstrip()
        return cleaned.rstrip() + "\n", True

    def _conf_values_from_paths(self, conf_paths: List[Path], keys: List[str]) -> Dict[str, Optional[str]]:
        values = self._read_conf_values_with_sources(conf_paths, keys)
        return {key: values.get(key, (None, None))[0] for key in keys}

    def _assignment_key_from_line(self, line: str) -> Optional[str]:
        match = re.match(
            r"^\s*([A-Za-z0-9_${}/.+-]+(?::[A-Za-z0-9_${}/.+-]+)*)\s*(?:\?\?=|\?=|:=|=|\+=|:append\s*=)",
            line,
        )
        return match.group(1) if match else None

    def _normalize_legacy_local_user_content(self, text: str, base_text: str) -> str:
        """Keep user edits from the old default local.conf.user.inc without duplicating defaults."""
        cleaned = self._strip_central_forbidden_lines(text)
        if "# Use this file for personal settings" not in cleaned:
            return cleaned

        lines = cleaned.splitlines()
        default_end = -1
        for index, line in enumerate(lines):
            if "Avoid: changing IMAGE_NAME_SUFFIX" in line:
                default_end = index
                break
        if default_end < 0:
            return cleaned

        base_lines = {line.strip() for line in base_text.splitlines() if line.strip()}
        base_keys = {
            key
            for line in base_text.splitlines()
            for key in [self._assignment_key_from_line(line)]
            if key
        }
        skip_if_base_has_key = {"DL_DIR", "SSTATE_DIR"}

        kept: List[str] = []
        for line in lines[:default_end + 1]:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key = self._assignment_key_from_line(line)
            if stripped in base_lines:
                continue
            if key in skip_if_base_has_key and key in base_keys:
                continue
            kept.append(line)

        tail = lines[default_end + 1:]
        while tail and not tail[0].strip():
            tail.pop(0)

        result_lines = kept
        if kept and tail:
            result_lines.append("")
        result_lines.extend(tail)
        return "\n".join(result_lines).rstrip() + "\n"

    def _legacy_local_user_is_machine_specific(self, text: str, machine: str) -> bool:
        stripped = self._strip_central_forbidden_lines(text)
        if stripped != text:
            return True
        machine_tokens = [
            f":{machine}",
            f"_{machine}",
            f"-{machine}",
            f"/{machine}",
        ]
        return any(token in text for token in machine_tokens)

    def _append_unique_block(self, path: Path, header: str, block: str) -> bool:
        block = block.strip()
        if not block:
            return False
        existing = self._read_text_if_exists(path) or ""
        if self._normalized_conf_text(block) in self._normalized_conf_text(existing):
            return False
        new_text = existing.rstrip()
        if new_text:
            new_text += "\n\n"
        new_text += f"{header}\n{block}\n"
        path.write_text(new_text)
        return True

    def _rewrite_workspace_paths_in_text(self, text: str) -> str:
        return text.replace(str(self.legacy_workspace_dir), str(self.workspace_dir))

    def _workspace_layer_lines(self, workspace_path: Optional[Path] = None) -> str:
        workspace = workspace_path or self.workspace_dir
        return (
            "BBLAYERS += \" \\\n"
            f"  {workspace} \\\n"
            "\"\n"
        )

    def _ensure_workspace_layer_in_shared_bblayers(self) -> bool:
        if not (self.workspace_dir / 'conf' / 'layer.conf').exists():
            return False
        path = self._global_bblayers_user_conf()
        existing = self._read_text_if_exists(path) or ""
        rewritten = self._rewrite_workspace_paths_in_text(existing)
        changed = rewritten != existing
        if str(self.workspace_dir) not in rewritten:
            rewritten = rewritten.rstrip() + "\n\n# Central devtool workspace shared by all machines.\n"
            rewritten += self._workspace_layer_lines()
            changed = True
        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rewritten.rstrip() + "\n")
        return changed

    def _remove_workspace_layer_from_machine_bblayers(self, bblayers_conf: Path) -> bool:
        if not bblayers_conf.exists():
            return False
        text = self._read_text_if_exists(bblayers_conf)
        if text is None:
            return False
        new_lines = []
        skip_block = False
        changed = False
        workspace_paths = {str(self.workspace_dir), str(self.legacy_workspace_dir)}
        for line in text.splitlines():
            if any(path in line for path in workspace_paths):
                changed = True
                continue
            if skip_block:
                if '"' in line:
                    skip_block = False
                changed = True
                continue
            new_lines.append(line)
        if changed:
            bblayers_conf.write_text("\n".join(new_lines).rstrip() + "\n")
        return changed

    def _machine_local_is_thin(self, conf_dir: Path, machine: str, machinebuild: str) -> bool:
        local_conf = conf_dir / 'local.conf'
        text = self._read_text_if_exists(local_conf) or ""
        required = [
            f'MACHINE ?= "{machine}"',
            f'MACHINEBUILD ?= "{machinebuild}"',
            f"include {self._global_local_conf(conf_dir.parent)}",
            'include conf/local-feed.inc',
            'include conf/local-image-server.inc',
            'include conf/local.conf.${MACHINE}.inc',
        ]
        forbidden = [
            "include conf/local.conf.user.inc",
            f"include {self._legacy_global_local_user_conf(conf_dir.parent)}",
        ]
        return all(item in text for item in required) and not any(item in text for item in forbidden)

    def _migration_rows(self, apply_changes: bool) -> Tuple[List[Dict[str, str]], bool]:
        rows: List[Dict[str, str]] = []
        failed = False
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_root = self.topdir / '.tuxbox' / 'config-backups' / timestamp

        def add_row(source: Path, target: Optional[Path], machine: str,
                    machinebuild: str, action: str, status: str, reason: str):
            rows.append({
                'source': str(source),
                'target': str(target) if target else '-',
                'machine': machine or '-',
                'machinebuild': machinebuild or '-',
                'action': action,
                'status': status,
                'reason': reason,
            })

        legacy_conf = self.legacy_builddir / 'conf'
        legacy_local = legacy_conf / 'local.conf'
        legacy_user = legacy_conf / 'local.conf.user.inc'
        legacy_bblayers_user = legacy_conf / 'bblayers.conf.user.inc'
        workspace_conflict = (
            self.legacy_workspace_dir.exists()
            and self.workspace_dir.exists()
            and self.legacy_workspace_dir.resolve() != self.workspace_dir.resolve()
        )
        effective_apply = apply_changes and not workspace_conflict

        # Shared config migration/normalization.
        shared_reasons = []
        shared_action = 'ok'
        shared_status = 'PASS'
        shared_target = self.global_conf_dir
        shared_local_conf = self._global_local_conf()
        legacy_shared_user = self._legacy_global_local_user_conf()
        shared_local_text = self._read_text_if_exists(shared_local_conf) or ""
        legacy_local_text = self._read_text_if_exists(legacy_local) or ""
        shared_local_generated = (
            bool(shared_local_text)
            and self._shared_local_conf_is_generated(shared_local_text)
        )
        cleaned_shared_local_text, generated_migrated_block = (
            self._strip_migrated_generated_local_conf_block(shared_local_text)
        )
        shared_files = [
            shared_local_conf,
            self._global_bblayers_user_conf(),
        ]
        missing_shared = [path.name for path in shared_files if not path.exists()]
        central_forbidden = self._central_forbidden_assignment_refs()
        if missing_shared:
            shared_action = 'migrate' if legacy_local.exists() or legacy_user.exists() else 'normalized'
            shared_reasons.append(f"create shared file(s): {', '.join(missing_shared)}")
        if shared_local_generated:
            shared_action = 'normalized'
            shared_reasons.append("convert generated shared local.conf to user/site local.conf")
        if legacy_shared_user.exists():
            shared_action = 'migrate'
            shared_reasons.append("move shared local.conf.user.inc into local.conf")
        if legacy_user.exists():
            shared_action = 'migrate'
            shared_reasons.append("move legacy build/conf/local.conf.user.inc into local.conf")
        if legacy_bblayers_user.exists():
            shared_action = 'migrate'
            shared_reasons.append("move legacy build/conf/bblayers.conf.user.inc into shared layer include")
        if generated_migrated_block:
            shared_action = 'normalized'
            shared_reasons.append("remove generated legacy local.conf block")
        if central_forbidden:
            shared_action = 'normalized'
            shared_reasons.append(
                "remove machine-specific assignment(s): "
                + ', '.join(ref.split(':', 1)[0] for ref in central_forbidden)
            )

        if effective_apply and shared_reasons:
            self._backup_path(self.global_conf_dir, backup_root)
            self._backup_path(legacy_conf, backup_root)
            self.global_conf_dir.mkdir(parents=True, exist_ok=True)

            value_sources = [
                shared_local_conf,
                legacy_local,
                legacy_shared_user,
                legacy_user,
            ]
            values = self._conf_values_from_paths(
                value_sources,
                ['DISTRO', 'DISTRO_TYPE', 'DL_DIR', 'SSTATE_DIR'],
            )
            if not shared_local_conf.exists() or shared_local_generated:
                self.generate_shared_local_conf(
                    values.get('DISTRO') or 'tuxbox',
                    values.get('DISTRO_TYPE') or 'release',
                    self.global_conf_dir,
                    overwrite=True,
                    dl_dir=values.get('DL_DIR') or str(self.dl_dir),
                    sstate_dir=values.get('SSTATE_DIR') or str(self.sstate_dir),
                )
                if legacy_local.exists() and not self._shared_local_conf_is_generated(legacy_local_text):
                    if self._append_unique_block(
                        shared_local_conf,
                        "# Migrated from legacy build/conf/local.conf",
                        self._strip_central_forbidden_lines(legacy_local_text),
                    ):
                        pass
            else:
                cleaned = self._strip_central_forbidden_lines(cleaned_shared_local_text)
                if cleaned != shared_local_text:
                    shared_local_conf.write_text(cleaned)

            if legacy_shared_user.exists():
                text = self._normalize_legacy_local_user_content(
                    self._read_text_if_exists(legacy_shared_user) or '',
                    self._read_text_if_exists(shared_local_conf) or '',
                )
                self._append_unique_block(
                    shared_local_conf,
                    "# Migrated from legacy builds/conf/local.conf.user.inc",
                    text,
                )
                legacy_shared_user.unlink()

            if legacy_user.exists():
                text = self._normalize_legacy_local_user_content(
                    self._read_text_if_exists(legacy_user) or '',
                    self._read_text_if_exists(shared_local_conf) or '',
                )
                self._append_unique_block(
                    shared_local_conf,
                    "# Migrated from legacy build/conf/local.conf.user.inc",
                    text,
                )
                legacy_user.unlink()

            if not self._global_bblayers_user_conf().exists():
                if legacy_bblayers_user.exists():
                    text = legacy_bblayers_user.read_text(errors='ignore')
                    self._global_bblayers_user_conf().write_text(
                        self._rewrite_workspace_paths_in_text(text).rstrip() + "\n"
                    )
                    legacy_bblayers_user.unlink()
                else:
                    self._global_bblayers_user_conf().write_text(
                        self._default_shared_bblayers_user_conf_content()
                    )
            elif legacy_bblayers_user.exists():
                text = self._rewrite_workspace_paths_in_text(
                    self._read_text_if_exists(legacy_bblayers_user) or ''
                )
                self._append_unique_block(
                    self._global_bblayers_user_conf(),
                    "# Migrated from legacy build/conf/bblayers.conf.user.inc",
                    text,
                )
                legacy_bblayers_user.unlink()

        if shared_reasons:
            add_row(
                legacy_conf if legacy_conf.exists() else self.global_conf_dir,
                shared_target,
                '-',
                '-',
                shared_action,
                shared_status,
                '; '.join(shared_reasons),
            )

        # Workspace migration/normalization.
        workspace_action = 'ok'
        workspace_status = 'PASS'
        workspace_reasons = []
        if workspace_conflict:
            workspace_status = 'FAIL'
            workspace_action = 'blocked'
            workspace_reasons.append(
                f"both {self.legacy_workspace_dir} and {self.workspace_dir} exist"
            )
            failed = True
        elif self.legacy_workspace_dir.exists():
            workspace_action = 'migrate'
            workspace_reasons.append(f"{self.legacy_workspace_dir} -> {self.workspace_dir}")
            if effective_apply:
                self._backup_path(self.legacy_workspace_dir, backup_root)
                self.workspace_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(self.legacy_workspace_dir), str(self.workspace_dir))

        workspace_path_rewrites = []
        if self.workspace_dir.exists():
            for bbappend in sorted((self.workspace_dir / 'appends').glob('*.bbappend')):
                text = self._read_text_if_exists(bbappend)
                if text and str(self.legacy_workspace_dir) in text:
                    workspace_path_rewrites.append(bbappend.name)
            shared_bblayers_text = self._read_text_if_exists(self._global_bblayers_user_conf()) or ''
            rewritten_shared_bblayers = self._rewrite_workspace_paths_in_text(shared_bblayers_text)
            if shared_bblayers_text and str(self.legacy_workspace_dir) in shared_bblayers_text:
                workspace_path_rewrites.append(self._global_bblayers_user_conf().name)
            workspace_layer_missing = (
                (self.workspace_dir / 'conf' / 'layer.conf').exists()
                and str(self.workspace_dir) not in rewritten_shared_bblayers
            )
            if workspace_path_rewrites and workspace_status != 'FAIL':
                workspace_action = 'normalized'
                workspace_reasons.append(
                    "rewrite legacy workspace path(s): " + ', '.join(workspace_path_rewrites)
                )
                if effective_apply:
                    self._backup_path(self.workspace_dir, backup_root)
                    self._backup_path(self._global_bblayers_user_conf(), backup_root)
                    for bbappend in sorted((self.workspace_dir / 'appends').glob('*.bbappend')):
                        text = self._read_text_if_exists(bbappend)
                        if text:
                            rewritten = self._rewrite_workspace_paths_in_text(text)
                            if rewritten != text:
                                bbappend.write_text(rewritten)
                    text = self._read_text_if_exists(self._global_bblayers_user_conf())
                    if text:
                        rewritten = self._rewrite_workspace_paths_in_text(text)
                        if rewritten != text:
                            self._global_bblayers_user_conf().write_text(rewritten)
            if workspace_layer_missing and workspace_status != 'FAIL':
                workspace_action = 'normalized'
                workspace_reasons.append('add central workspace layer to shared bblayers include')
            if effective_apply and workspace_status != 'FAIL':
                self._ensure_workspace_layer_in_shared_bblayers()

        if workspace_reasons:
            add_row(
                self.legacy_workspace_dir if self.legacy_workspace_dir.exists() else self.workspace_dir,
                self.workspace_dir,
                '-',
                '-',
                workspace_action,
                workspace_status,
                '; '.join(workspace_reasons),
            )

        for conf_dir in self._config_scan_dirs():
            if conf_dir.resolve() == self.global_conf_dir.resolve():
                continue
            builddir = conf_dir.parent
            machine, machinebuild = self._config_identity(conf_dir)
            target = self._default_builddir_for_machine(machine) if machine else None
            target_conf = target / 'conf' if target else None
            status = 'PASS'
            action = 'ok'
            reason = '-'

            if not machine:
                status = 'FAIL'
                action = 'blocked'
                reason = 'local.conf does not define MACHINE'
                failed = True
            elif not machinebuild:
                status = 'FAIL'
                action = 'blocked'
                reason = 'local.conf does not define MACHINEBUILD'
                failed = True
            else:
                build_names, build_display = self._machinebuild_candidates(machine)
                if build_names and machinebuild not in build_names:
                    status = 'FAIL'
                    action = 'blocked'
                    reason = (
                        f"MACHINEBUILD {machinebuild} invalid for {machine}; "
                        f"available: {', '.join(build_display)}"
                    )
                    failed = True
                elif target_conf and conf_dir.resolve() != target_conf.resolve():
                    if target_conf.exists():
                        tm, tmb = self._config_identity(target_conf)
                        if tm == machine and (not tmb or tmb == machinebuild):
                            if conf_dir.resolve() == legacy_conf.resolve():
                                action = 'normalized'
                                archive_conf = self.legacy_builddir / f"conf.legacy-{timestamp}"
                                reason = (
                                    f"archive legacy build/conf; target already exists at {target}"
                                )
                                if effective_apply:
                                    self._backup_path(conf_dir, backup_root)
                                    archive_conf.parent.mkdir(parents=True, exist_ok=True)
                                    suffix = 1
                                    candidate = archive_conf
                                    while candidate.exists():
                                        candidate = self.legacy_builddir / f"conf.legacy-{timestamp}-{suffix}"
                                        suffix += 1
                                    shutil.move(str(conf_dir), str(candidate))
                                    reason = f"archived legacy build/conf to {candidate}"
                            else:
                                action = 'legacy ignored'
                                reason = f"target already exists at {target}"
                        else:
                            status = 'FAIL'
                            action = 'blocked'
                            reason = f"target {target_conf} has MACHINE={tm} MACHINEBUILD={tmb}"
                            failed = True
                    else:
                        action = 'migrate'
                        reason = f"{builddir} -> {target}"
                        if effective_apply:
                            self._backup_path(conf_dir, backup_root)
                            target_conf.mkdir(parents=True, exist_ok=True)
                            self.generate_bblayers_conf(target_conf, machine, self.detect_machine_brand(machine))
                            self.generate_local_conf(target_conf, machine, 'tuxbox', 'release', machinebuild, target)
                            self.ensure_local_feed_config(target_conf, machine)
                            self.ensure_local_image_server_config(target_conf, machine)
                            self.ensure_machine_overrides(target_conf, machine)
                            self.ensure_devtool_config(target_conf)
                elif target_conf:
                    foreign_includes = self._foreign_machine_include_files(conf_dir, machine)
                    has_tmpdir_override = self._has_generated_tmpdir_override(conf_dir, machine)
                    local_user_conf = conf_dir / 'local.conf.user.inc'
                    bblayers_user_conf = conf_dir / 'bblayers.conf.user.inc'
                    devtool_workspace = self._devtool_workspace_value(conf_dir)
                    needs_thin_local = not self._machine_local_is_thin(conf_dir, machine, machinebuild)
                    needs_devtool = devtool_workspace != str(self.workspace_dir)
                    needs_workspace_layer_cleanup = False
                    bblayers_text = self._read_text_if_exists(conf_dir / 'bblayers.conf') or ''
                    if str(self.workspace_dir) in bblayers_text or str(self.legacy_workspace_dir) in bblayers_text:
                        needs_workspace_layer_cleanup = True
                    if (
                        has_tmpdir_override
                        or foreign_includes
                        or local_user_conf.exists()
                        or bblayers_user_conf.exists()
                        or needs_thin_local
                        or needs_devtool
                        or needs_workspace_layer_cleanup
                    ):
                        action = 'normalized'
                        reasons = []
                        if has_tmpdir_override:
                            reasons.append('remove generated TMPDIR override')
                        if foreign_includes:
                            names = ', '.join(item.name for item in foreign_includes)
                            reasons.append(f'remove foreign machine include(s): {names}')
                        if local_user_conf.exists():
                            reasons.append('move legacy local.conf.user.inc into central/machine config')
                        if bblayers_user_conf.exists():
                            reasons.append('move per-machine bblayers.conf.user.inc into shared include')
                        if needs_thin_local:
                            reasons.append('regenerate thin machine local.conf')
                        if needs_devtool:
                            reasons.append('set shared devtool workspace')
                        if needs_workspace_layer_cleanup:
                            reasons.append('remove direct workspace layer from machine bblayers.conf')
                        reason = '; '.join(reasons)
                    if effective_apply and action == 'normalized':
                        self._backup_path(conf_dir, backup_root)
                        changed = False
                        removed = self._remove_foreign_machine_includes(conf_dir, machine)
                        if removed:
                            changed = True
                        if self._strip_generated_tmpdir_override(conf_dir, machine):
                            changed = True
                        self.ensure_machine_overrides(conf_dir, machine)
                        machine_conf = conf_dir / f'local.conf.{machine}.inc'
                        if local_user_conf.exists():
                            raw_text = self._read_text_if_exists(local_user_conf) or ''
                            text = self._strip_central_forbidden_lines(raw_text)
                            if self._legacy_local_user_is_machine_specific(raw_text, machine):
                                if self._append_unique_block(
                                    machine_conf,
                                    "# Migrated from legacy per-machine local.conf.user.inc",
                                    text,
                                ):
                                    changed = True
                            else:
                                if self._append_unique_block(
                                    self._global_local_conf(),
                                    f"# Migrated from legacy per-machine local.conf.user.inc ({machine})",
                                    text,
                                ):
                                    changed = True
                            local_user_conf.unlink()
                            changed = True
                        if bblayers_user_conf.exists():
                            text = self._rewrite_workspace_paths_in_text(
                                self._read_text_if_exists(bblayers_user_conf) or ''
                            )
                            global_text = self._read_text_if_exists(self._global_bblayers_user_conf()) or ''
                            default_text = self._default_shared_bblayers_user_conf_content()
                            normalized = self._normalized_conf_text(text)
                            if (
                                normalized
                                and normalized != self._normalized_conf_text(global_text)
                                and normalized != self._normalized_conf_text(default_text)
                            ):
                                if self._append_unique_block(
                                    self._global_bblayers_user_conf(),
                                    "# Migrated from legacy per-machine bblayers.conf.user.inc",
                                    text,
                                ):
                                    changed = True
                            bblayers_user_conf.unlink()
                            changed = True
                        if needs_thin_local:
                            self.generate_local_conf(conf_dir, machine, 'tuxbox', 'release', machinebuild, builddir)
                            changed = True
                        if self._remove_workspace_layer_from_machine_bblayers(conf_dir / 'bblayers.conf'):
                            changed = True
                        self.generate_bblayers_conf(conf_dir, machine, self.detect_machine_brand(machine))
                        self.ensure_local_feed_config(conf_dir, machine)
                        self.ensure_local_image_server_config(conf_dir, machine)
                        self.ensure_devtool_config(conf_dir)
                        if self._ensure_workspace_layer_in_shared_bblayers():
                            changed = True
                        if changed:
                            action = 'normalized'
                            reasons = []
                            if removed:
                                reasons.append(f"removed foreign machine include(s): {', '.join(removed)}")
                            if not self._has_generated_tmpdir_override(conf_dir, machine) and has_tmpdir_override:
                                reasons.append('removed generated TMPDIR override')
                            reason = '; '.join(reasons) or 'normalized central config layout'

            add_row(builddir, target, machine or '-', machinebuild or '-', action, status, reason)

        return rows, failed

    def migrate_configs(self, args):
        """Migrate legacy shared configs into per-machine build dirs."""
        apply_changes = bool(args.apply)
        check_only = bool(args.check)
        rows, failed = self._migration_rows(apply_changes)
        needs_action = any(row['action'] in ('migrate', 'normalized') for row in rows)

        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            self._print_table(
                "Config migration",
                ['source', 'target', 'machine', 'machinebuild', 'action', 'status', 'reason'],
                [
                    (
                        row['source'], row['target'], row['machine'], row['machinebuild'],
                        row['action'], row['status'], row['reason']
                    )
                    for row in rows
                ],
            )
            if apply_changes and rows:
                self.info("Backups: .tuxbox/config-backups/<timestamp>/")

        if failed or (check_only and needs_action):
            sys.exit(1)

    def _resolve_topdir_value(self, value: Optional[str], builddir: Path, machine: str) -> Optional[str]:
        if not value:
            return None
        resolved = value.replace('${TOPDIR}', str(builddir)).replace('${MACHINE}', machine)
        return resolved

    def _existing_or_first(self, candidates: List[Path]) -> Path:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _deploy_info_data(self, machine: str, machinebuild: Optional[str],
                          builddir: Optional[Path]) -> Dict[str, object]:
        target_builddir = builddir or self._default_builddir_for_machine(machine)
        conf_dir = target_builddir / 'conf'
        local_conf = conf_dir / 'local.conf'
        bblayers_conf = conf_dir / 'bblayers.conf'
        keys = [
            'MACHINE', 'MACHINEBUILD', 'DISTRO', 'DISTRO_TYPE', 'TMPDIR',
            'TUXBOX_IMAGE_DIR', 'IPK_FEED_SERVER',
            'TUXBOX_IMAGE_UPDATE_BASE_URL', 'TUXBOX_IMAGE_UPDATE_URL',
            'TUXBOX_IMAGE_MANIFEST_FILE',
        ]
        values = self._read_conf_values_with_sources(
            self._machine_conf_sources(conf_dir, machine),
            keys,
        )
        conf_machine = values.get('MACHINE', (None, None))[0]
        conf_machinebuild = values.get('MACHINEBUILD', (None, None))[0]
        ipk_feed_server = values.get('IPK_FEED_SERVER', (None, None))[0]
        image_update_base_url = values.get('TUXBOX_IMAGE_UPDATE_BASE_URL', (None, None))[0]
        image_update_url = values.get('TUXBOX_IMAGE_UPDATE_URL', (None, None))[0]
        image_manifest_file = values.get('TUXBOX_IMAGE_MANIFEST_FILE', (None, None))[0]
        effective_machinebuild = machinebuild or conf_machinebuild or machine
        brand = self.detect_machine_brand(machine)
        oem_values = (
            self._oem_values_for_machinebuild(brand, effective_machinebuild)
            if brand not in ('unknown', 'coolstream') else {'imagedir': set(), 'driver': set()}
        )
        raw_imagedir = next(iter(sorted(oem_values.get('imagedir') or {machine})))
        driver = next(iter(sorted(oem_values.get('driver') or {machine})))
        configured_online = values.get('TUXBOX_IMAGE_DIR', (None, None))[0]
        online_imagedir = configured_online or self._online_imagedir_slug(raw_imagedir)
        tmpdir_value = values.get('TMPDIR', (None, None))[0]
        tmpdir = Path(self._resolve_topdir_value(tmpdir_value, target_builddir, machine)) if tmpdir_value else target_builddir / 'tmp'
        deploy_ipk = self._existing_or_first([
            tmpdir / 'deploy' / 'ipk',
            target_builddir / 'tmp' / 'deploy' / 'ipk',
            target_builddir / 'build' / 'tmp' / 'deploy' / 'ipk',
            target_builddir / 'build' / f'tmp-{machine}' / 'deploy' / 'ipk',
            target_builddir / f'tmp-{machine}' / 'deploy' / 'ipk',
        ])
        deploy_images = self._existing_or_first([
            tmpdir / 'deploy' / 'images' / machine,
            target_builddir / 'tmp' / 'deploy' / 'images' / machine,
            target_builddir / 'build' / 'tmp' / 'deploy' / 'images' / machine,
            target_builddir / 'build' / f'tmp-{machine}' / 'deploy' / 'images' / machine,
            target_builddir / f'tmp-{machine}' / 'deploy' / 'images' / machine,
        ])
        manifest = deploy_images / 'manifest.json'

        errors: List[str] = []
        warnings: List[str] = []
        if not local_conf.exists():
            errors.append(f"missing {local_conf}")
        if not bblayers_conf.exists():
            errors.append(f"missing {bblayers_conf}")
        if not self._global_local_conf(target_builddir).exists():
            errors.append(f"missing {self._global_local_conf(target_builddir)}")
        if not self._global_bblayers_user_conf(target_builddir).exists():
            errors.append(f"missing {self._global_bblayers_user_conf(target_builddir)}")
        legacy_shared_user = self._legacy_global_local_user_conf(target_builddir)
        if legacy_shared_user.exists():
            errors.append(f"legacy shared user include present: {legacy_shared_user}")
        if (conf_dir / 'local.conf.user.inc').exists():
            errors.append(f"legacy per-machine user include present: {conf_dir / 'local.conf.user.inc'}")
        if (conf_dir / 'bblayers.conf.user.inc').exists():
            errors.append(f"legacy per-machine layer include present: {conf_dir / 'bblayers.conf.user.inc'}")
        for ref in self._central_forbidden_assignment_refs(target_builddir):
            errors.append(f"machine-specific assignment in shared config: {ref}")
        if conf_machine and conf_machine != machine:
            errors.append(f"local.conf MACHINE={conf_machine} (requested {machine})")
        if machinebuild and conf_machinebuild and conf_machinebuild != machinebuild:
            errors.append(f"local.conf MACHINEBUILD={conf_machinebuild} (requested {machinebuild})")
        build_names, build_display = self._machinebuild_candidates(machine)
        if build_names and effective_machinebuild not in build_names:
            errors.append(
                f"MACHINEBUILD {effective_machinebuild} invalid for {machine}; "
                f"available: {', '.join(build_display)}"
            )
        bblayers = []
        for layer_source in self._machine_layer_sources(conf_dir):
            bblayers += self._extract_layer_paths(layer_source)
        if brand != 'unknown':
            expected = '/meta-coolstream' if brand == 'coolstream' else f"/oe-alliance/meta-brands/meta-{brand}"
            if not any(expected in path for path in bblayers):
                errors.append(f"missing brand layer {expected}")
        if raw_imagedir != online_imagedir and raw_imagedir == self._online_imagedir_slug(raw_imagedir):
            warnings.append(f"TUXBOX_IMAGE_DIR={online_imagedir} differs from IMAGEDIR={raw_imagedir}")

        data: Dict[str, object] = {
            'machine': machine,
            'machinebuild': effective_machinebuild,
            'brand': brand,
            'builddir': str(target_builddir),
            'confdir': str(conf_dir),
            'tmpdir': str(tmpdir),
            'deploy_ipk': str(deploy_ipk),
            'deploy_images': str(deploy_images),
            'raw_imagedir': raw_imagedir,
            'online_imagedir': online_imagedir,
            'ipk_feed_server': ipk_feed_server or '',
            'image_update_base_url': image_update_base_url or '',
            'image_update_url': image_update_url or '',
            'image_manifest_file': image_manifest_file or '',
            'driver': driver,
            'manifest': str(manifest),
            'errors': errors,
            'warnings': warnings,
        }
        data['status'] = 'FAIL' if errors else ('WARN' if warnings else 'PASS')
        data['reason'] = '; '.join(errors or warnings) if (errors or warnings) else '-'
        return data

    def deploy_info(self, args):
        machine = args.machine
        builddir = self._resolve_user_path(args.builddir) if args.builddir else None
        data = self._deploy_info_data(machine, args.machinebuild, builddir)
        errors = list(data.get('errors', []))
        if args.require_ipk and not Path(str(data['deploy_ipk'])).is_dir():
            errors.append(f"missing deploy/ipk: {data['deploy_ipk']}")
        if args.require_images and not Path(str(data['deploy_images'])).is_dir():
            errors.append(f"missing deploy/images: {data['deploy_images']}")
        manifest_path = Path(str(data['manifest']))
        if args.require_manifest:
            if not manifest_path.is_file():
                errors.append(f"missing manifest: {manifest_path}")
            else:
                try:
                    manifest = json.loads(manifest_path.read_text(errors='ignore'))
                    if str(manifest.get('machine', '')) != machine:
                        errors.append(f"manifest machine={manifest.get('machine')}")
                    if str(manifest.get('imagedir', '')) != str(data['online_imagedir']):
                        errors.append(
                            f"manifest imagedir={manifest.get('imagedir')} "
                            f"(expected {data['online_imagedir']})"
                        )
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"cannot read manifest: {exc}")
        if errors:
            data['errors'] = errors
            data['status'] = 'FAIL'
            data['reason'] = '; '.join(errors)

        if args.json:
            print(json.dumps(data, indent=2))
        else:
            self._print_kv_table("Deploy info", [
                ("Machine", str(data['machine'])),
                ("MachineBuild", str(data['machinebuild'])),
                ("Brand", str(data['brand'])),
                ("Build dir", str(data['builddir'])),
                ("TMPDIR", str(data['tmpdir'])),
                ("Deploy IPK", str(data['deploy_ipk'])),
                ("Deploy images", str(data['deploy_images'])),
                ("Raw IMAGEDIR", str(data['raw_imagedir'])),
                ("Online imagedir", str(data['online_imagedir'])),
                ("IPK feed server", str(data['ipk_feed_server']) or "-"),
                ("Image update base URL", str(data['image_update_base_url']) or "-"),
                ("Image update URL", str(data['image_update_url']) or "-"),
                ("Image manifest file", str(data['image_manifest_file']) or "-"),
                ("Manifest", str(data['manifest'])),
                ("Status", str(data['status'])),
                ("Reason", str(data['reason'])),
            ])
        if data['status'] == 'FAIL':
            sys.exit(1)

    def generate_config(self, machine: str, distro: str, distro_type: str = 'release',
                        machinebuild: Optional[str] = None, builddir: Optional[Path] = None):
        """Generate build configuration files from templates."""
        self.log(f"Generating configuration for {machine}...", Colors.BOLD, bold=True)

        # Detect machine brand for meta-brands layer
        brand = self.detect_machine_brand(machine)
        if brand == 'unknown':
            self.warning(f"Unknown machine '{machine}' - brand layer may need manual configuration")
        if not machinebuild:
            build_names, build_display = self._machinebuild_candidates(machine)
            if len(build_names) == 1:
                machinebuild = build_names[0]
                self.info(f"Auto-selected MACHINEBUILD={machinebuild} for {machine}")
            elif len(build_names) > 1:
                self.error(f"MACHINEBUILD required for {machine}")
                self.info(f"Available: {', '.join(build_display)}")
                self.info("Pass --machinebuild or set MACHINEBUILD=...")
                sys.exit(1)
            else:
                self.info(f"No MACHINEBUILD variants listed for {machine}; defaulting to MACHINEBUILD={machine}")

        self._validate_machinebuild(machine, machinebuild)

        # Create shared and machine-specific config directories.
        target_builddir = self._resolve_user_path(builddir) if builddir else self._default_builddir_for_machine(machine)
        shared_conf_dir = self._shared_conf_dir_for_builddir(target_builddir)
        shared_conf_dir.mkdir(parents=True, exist_ok=True)
        conf_dir = target_builddir / 'conf'
        conf_dir.mkdir(parents=True, exist_ok=True)

        # Generate shared config first. Per-machine local.conf includes it.
        self.generate_shared_local_conf(distro, distro_type, shared_conf_dir)
        self.ensure_shared_overrides(shared_conf_dir)

        # Generate bblayers.conf
        self.generate_bblayers_conf(conf_dir, machine, brand)

        # Generate per-machine local.conf entrypoint
        self.generate_local_conf(conf_dir, machine, distro, distro_type, machinebuild, target_builddir)

        # Generate local URL defaults before user override includes.
        self.ensure_local_feed_config(conf_dir, machine)
        self.ensure_local_image_server_config(conf_dir, machine)

        # Ensure machine-local override and devtool config files exist.
        self.ensure_machine_overrides(conf_dir, machine)
        self.ensure_devtool_config(conf_dir)

        self.success("Configuration generated")

    def generate_bblayers_conf(self, conf_dir: Path, machine: str, brand: str):
        """Generate bblayers.conf from template."""
        template_file = self.topdir / 'templates' / 'bblayers.conf.template'
        output_file = conf_dir / 'bblayers.conf'

        if not template_file.exists():
            self.error(f"Template not found: {template_file}")
            sys.exit(1)

        # Read template
        with open(template_file) as f:
            content = f.read()

        # Replace variables
        content = content.replace('##OEROOT##', str(self.topdir / 'oe-alliance' / 'openembedded-core'))
        content = content.replace('##TOPDIR##', str(self.topdir))
        content = content.replace(
            '##BBLAYERS_USER_INCLUDE##',
            f'include {self._global_bblayers_user_conf(conf_dir.parent)}',
        )

        # Add brand-specific layer
        if brand != 'unknown':
            brand_layer = f'BBLAYERS += " \\\n  {self.topdir}/oe-alliance/meta-brands/meta-{brand} \\\n"\n'
            content = content.replace('##BRAND_LAYERS##', brand_layer)
        else:
            content = content.replace('##BRAND_LAYERS##', '# Add brand layer manually\n')

        # Add toolchain/coolstream layers when MACHINE startswith coolstream
        if machine.startswith('coolstream'):
            toolchain_layer = f'BBLAYERS += " \\\n  {self.topdir}/meta-tuxbox-toolchain \\\n  {self.topdir}/meta-coolstream \\\n"\n'
            content = content.replace('##TOOLCHAIN_LAYER##', toolchain_layer)
        else:
            content = content.replace('##TOOLCHAIN_LAYER##', '')

        # Write output
        with open(output_file, 'w') as f:
            f.write(content)

        self.info(f"Generated: {output_file}")

    def generate_shared_local_conf(self, distro: str, distro_type: str,
                                   shared_conf_dir: Optional[Path] = None,
                                   overwrite: bool = False,
                                   dl_dir: Optional[str] = None,
                                   sstate_dir: Optional[str] = None):
        """Create the central user/site local.conf when it is missing."""
        template_file = self.topdir / 'templates' / 'local.conf.template'
        output_file = (shared_conf_dir or self.global_conf_dir) / 'local.conf'

        if not template_file.exists():
            self.error(f"Template not found: {template_file}")
            sys.exit(1)
        if output_file.exists() and not overwrite:
            return

        with open(template_file) as f:
            content = f.read()

        content = content.replace('##DISTRO##', distro)
        content = content.replace('##DL_DIR##', dl_dir or str(self.dl_dir))
        content = content.replace('##SSTATE_DIR##', sstate_dir or str(self.sstate_dir))
        content = content.replace('##DISTRO_TYPE##', distro_type)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content)

        self.info(f"Created/updated: {output_file}")

    def generate_local_conf(self, conf_dir: Path, machine: str, distro: str, distro_type: str,
                            machinebuild: Optional[str], target_builddir: Path):
        """Generate the per-machine local.conf entrypoint."""
        output_file = conf_dir / 'local.conf'
        effective_machinebuild = machinebuild or machine

        brand = self.detect_machine_brand(machine)
        oem_values = (
            self._oem_values_for_machinebuild(brand, effective_machinebuild)
            if brand not in ('unknown', 'coolstream') else {'imagedir': set()}
        )
        raw_imagedir = next(iter(sorted(oem_values.get('imagedir') or {machine})))
        online_imagedir = self._online_imagedir_slug(raw_imagedir)

        content = (
            "# Machine entry configuration for Tuxbox-OS builds\n"
            "#\n"
            "# This file is auto-generated by tuxbox-os-builder.\n"
            "# Shared settings are included below from:\n"
            "# {shared_local}\n"
            f"# machine-specific overrides live in conf/local.conf.{machine}.inc.\n"
            "\n"
            "MACHINE ?= \"{machine}\"\n"
            "MACHINEBUILD ?= \"{machinebuild}\"\n"
            "TMPDIR ?= \"${{TOPDIR}}/tmp\"\n"
            "\n"
            "# URL-safe alias for online-flash/catalog paths. OE-Alliance IMAGEDIR\n"
            "# remains untouched for flash/image classes.\n"
            "TUXBOX_IMAGE_DIR ?= \"{online_imagedir}\"\n"
            "\n"
            "include {shared_local}\n"
            "include conf/local-feed.inc\n"
            "include conf/local-image-server.inc\n"
            "include conf/local.conf.${{MACHINE}}.inc\n"
        ).format(
            machine=machine,
            machinebuild=effective_machinebuild,
            online_imagedir=online_imagedir,
            shared_local=self._global_local_conf(target_builddir),
        )

        # Coolstream-specific toolchain defaults (HD2 uClibc, HD1 glibc)
        if machine.startswith('coolstream') and machine != 'coolstream-nevis':
            content += '\n# Coolstream external uClibc toolchain\n'
            content += 'TCMODE ?= "external-coolstream"\n'
            content += 'TCLIBC ?= "uclibc"\n'
            content += 'BBMASK:append = "|.*/meta-tuxbox/recipes-kodi/.*|.*/meta-tuxbox/recipes-multimedia/kodi/.*|.*/recipes-mediacenter/kodi/.*"\n'
        elif machine == 'coolstream-nevis':
            # Mask Kodi bbappends not used on coolstream
            content += 'BBMASK:append = "|.*/meta-tuxbox/recipes-kodi/.*|.*/meta-tuxbox/recipes-multimedia/kodi/.*|.*/recipes-mediacenter/kodi/.*"\n'

        # Mask cross-canadian rust/go for external/uclibc targets
        if machine.startswith('coolstream'):
            content += 'BBMASK:append = "|cross-canadian|.*/rust-tools-cross-canadian.*|.*/rust-cross-canadian.*|.*/go-cross-canadian.*|.*/packagegroup-cross-canadian.*|.*/gcc-cross-canadian.*|.*/cargo-cross-canadian.*|.*/cross-canadian.*"\n'

        # Write output
        with open(output_file, 'w') as f:
            f.write(content)

        self.info(f"Generated: {output_file}")
        self.info(f"  Machine: {machine}")
        self.info(f"  MachineBuild: {effective_machinebuild}")
        self.info(f"  Distro: {distro}")
        self.info("  Threads: default (auto)")
        self.info("  Parallel: default (auto)")

    def _default_shared_bblayers_user_conf_content(self) -> str:
        content = (
            "# Shared local layer overrides (not tracked)\n"
            "# Example:\n"
            "# BBLAYERS += \" \\\n"
            "#   /path/to/your/layer \\\n"
            "# \"\n"
        )
        if (self.workspace_dir / 'conf' / 'layer.conf').exists():
            content += (
                "\n"
                "# Central devtool workspace shared by all machines.\n"
                "BBLAYERS += \" \\\n"
                f"  {self.workspace_dir} \\\n"
                "\"\n"
            )
        return content

    def ensure_shared_overrides(self, shared_conf_dir: Optional[Path] = None):
        """Create shared layer override files if missing."""
        shared_conf_dir = shared_conf_dir or self.global_conf_dir
        overrides = {
            shared_conf_dir / 'bblayers.conf.user.inc': self._default_shared_bblayers_user_conf_content(),
        }

        for path, content in overrides.items():
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w') as f:
                    f.write(content)
                self.info(f"Created: {path}")

    def ensure_machine_overrides(self, conf_dir: Path, machine: str):
        """Create machine-local override files if missing."""
        overrides = {
            conf_dir / f'local.conf.{machine}.inc': (
                f"# Local overrides for MACHINE={machine} (not tracked)\n"
                "# Use this file for machine-specific tweaks.\n"
                "# TMPDIR defaults to ${TOPDIR}/tmp inside this per-machine builddir.\n"
            ),
        }

        for path, content in overrides.items():
            if not path.exists():
                with open(path, 'w') as f:
                    f.write(content)
                self.info(f"Created: {path}")

    def ensure_devtool_config(self, conf_dir: Path):
        """Ensure devtool uses the shared workspace from this builddir."""
        path = conf_dir / 'devtool.conf'
        parser = configparser.ConfigParser()
        if path.exists():
            parser.read(path)
        if not parser.has_section('General'):
            parser.add_section('General')
        current = parser.get('General', 'workspace_path', fallback='')
        desired = str(self.workspace_dir)
        if current == desired:
            return
        parser.set('General', 'workspace_path', desired)
        with open(path, 'w') as f:
            parser.write(f)
        self.info(f"Updated: {path}")

    def _devtool_workspace_value(self, conf_dir: Path) -> Optional[str]:
        path = conf_dir / 'devtool.conf'
        if not path.exists():
            return None
        parser = configparser.ConfigParser()
        parser.read(path)
        return parser.get('General', 'workspace_path', fallback=None)

    def show_config(self, args):
        """Show current configuration and highlight issues."""
        machine = args.machine
        requested_machinebuild = args.machinebuild or os.environ.get('MACHINEBUILD')
        distro = args.distro
        distro_type = args.distro_type

        target_builddir = self._resolve_user_path(args.builddir) if args.builddir else (
            self._default_builddir_for_machine(machine)
        )
        conf_dir = target_builddir / 'conf'
        local_conf = conf_dir / 'local.conf'
        bblayers_conf = conf_dir / 'bblayers.conf'
        shared_local_conf = self._global_local_conf(target_builddir)
        legacy_shared_local_user_conf = self._legacy_global_local_user_conf(target_builddir)
        local_machine_conf = conf_dir / f'local.conf.{machine}.inc'
        bblayers_user_conf = self._global_bblayers_user_conf(target_builddir)
        legacy_local_user_conf = conf_dir / 'local.conf.user.inc'
        legacy_bblayers_user_conf = conf_dir / 'bblayers.conf.user.inc'

        self.log("=== Configuration Summary ===", Colors.BOLD, bold=True)
        self.info(f"Build dir: {target_builddir}")
        self.info("Config files:")
        if local_conf.exists():
            self.success(f"local.conf: {local_conf}")
        else:
            self.warning(f"local.conf: missing ({local_conf})")
        if bblayers_conf.exists():
            self.success(f"bblayers.conf: {bblayers_conf}")
        else:
            self.warning(f"bblayers.conf: missing ({bblayers_conf})")
        if shared_local_conf.exists():
            self.success(f"shared user/site local.conf: {shared_local_conf}")
        else:
            self.warning(f"shared user/site local.conf: missing ({shared_local_conf})")
        if legacy_shared_local_user_conf.exists():
            self.warning(f"legacy shared local.conf.user.inc: {legacy_shared_local_user_conf}")
        if local_machine_conf.exists():
            self.success(f"local.conf.{machine}.inc: {local_machine_conf}")
        else:
            self.info(f"local.conf.{machine}.inc: missing ({local_machine_conf})")
        if bblayers_user_conf.exists():
            self.success(f"shared bblayers.conf.user.inc: {bblayers_user_conf}")
        else:
            self.info(f"shared bblayers.conf.user.inc: missing ({bblayers_user_conf})")
        if legacy_local_user_conf.exists():
            self.warning(f"legacy per-machine local.conf.user.inc: {legacy_local_user_conf}")
        if legacy_bblayers_user_conf.exists():
            self.warning(f"legacy per-machine bblayers.conf.user.inc: {legacy_bblayers_user_conf}")

        keys = [
            'MACHINE', 'MACHINEBUILD', 'DISTRO', 'DISTRO_TYPE',
            'DL_DIR', 'SSTATE_DIR', 'TMPDIR',
            'IPK_FEED_SERVER', 'TUXBOX_IMAGE_UPDATE_BASE_URL',
            'TUXBOX_IMAGE_UPDATE_URL', 'TUXBOX_IMAGE_MANIFEST_FILE',
        ]
        values = {}
        sources = {}
        if local_conf.exists():
            conf_sources = self._machine_conf_sources(conf_dir, machine)
            values_with_sources = self._read_conf_values_with_sources(conf_sources, keys)
            for key in keys:
                value, source = values_with_sources.get(key, (None, None))
                values[key] = value
                sources[key] = source

            self.info("")
            self.info("Values (from local.conf + includes):")
            for key in keys:
                value = values.get(key)
                if value:
                    source_label = self._format_conf_source(sources.get(key), conf_dir)
                    self.info(f"  {key}: {value} ({source_label})")
                elif key == 'TMPDIR':
                    self.info(f"  {key}: default ({target_builddir}/tmp)")
                else:
                    self.warning(f"  {key}: not set")

        layer_sources: Dict[str, Path] = {}
        for layer_file in self._machine_layer_sources(conf_dir):
            for layer in self._extract_layer_paths(layer_file):
                if layer not in layer_sources:
                    layer_sources[layer] = layer_file
        if layer_sources:
            self.info("")
            self.info("Layers (from bblayers.conf + includes):")
            for layer, source in layer_sources.items():
                source_label = self._format_conf_source(source, conf_dir)
                if Path(layer).exists():
                    self.info(f"  {layer} ({source_label})")
                else:
                    self.warning(f"  {layer} ({source_label}, missing)")

        errors = []
        warnings = []
        if not local_conf.exists():
            errors.append("local.conf missing (run make config)")
        if not bblayers_conf.exists():
            errors.append("bblayers.conf missing (run make config)")
        if not shared_local_conf.exists():
            errors.append("shared local.conf missing (run make config)")
        if not bblayers_user_conf.exists():
            errors.append("shared bblayers.conf.user.inc missing (run make config)")
        if legacy_shared_local_user_conf.exists():
            errors.append("legacy shared local.conf.user.inc present (run make migrate-configs)")
        if legacy_local_user_conf.exists():
            errors.append("legacy per-machine local.conf.user.inc present (run make migrate-configs)")
        if legacy_bblayers_user_conf.exists():
            errors.append("legacy per-machine bblayers.conf.user.inc present (run make migrate-configs)")
        central_forbidden = self._central_forbidden_assignment_refs(target_builddir)
        if central_forbidden:
            errors.append(
                "machine-specific assignment in shared config: "
                + ', '.join(central_forbidden)
            )

        required_layers = ['poky', 'oe-alliance', 'meta-openembedded', 'meta-neutrino', 'meta-tuxbox']
        for layer in required_layers:
            path = self.topdir / layer
            if not path.exists():
                errors.append(f"Missing layer: {path}")

        configured_machine = values.get('MACHINE')
        configured_machinebuild = values.get('MACHINEBUILD')
        configured_distro = values.get('DISTRO')
        configured_distro_type = values.get('DISTRO_TYPE')

        if configured_machine and configured_machine != machine:
            errors.append(f"local.conf MACHINE={configured_machine} (requested {machine})")
        if requested_machinebuild and configured_machinebuild and configured_machinebuild != requested_machinebuild:
            errors.append(
                f"local.conf MACHINEBUILD={configured_machinebuild} (requested {requested_machinebuild})"
            )

        brand = self.detect_machine_brand(machine)
        if brand == 'unknown':
            warnings.append(f"Unknown brand for machine '{machine}'")
        else:
            layer_root = self.topdir / 'oe-alliance' / 'meta-brands' / f"meta-{brand}"
            machine_conf = layer_root / 'conf' / 'machine' / f"{machine}.conf"
            if not machine_conf.exists():
                errors.append(f"Machine config not found: {machine_conf}")
            else:
                brand_map = self._load_brand_machines()
                machines = brand_map.get(brand, [])
                builds_map = self._machinebuilds_for_brand(brand, machines)
                build_info = builds_map.get(
                    machine, {'explicit': set(), 'oem_imagedir': set(), 'oem_driver': set()}
                )
                build_names = (
                    set(build_info.get('explicit', set()))
                    | set(build_info.get('oem_imagedir', set()))
                    | set(build_info.get('oem_driver', set()))
                )
                builds_display = self._format_machinebuild_list(build_info)
                machinebuild = configured_machinebuild or requested_machinebuild or machine
                if build_names and machinebuild not in build_names:
                    errors.append(
                        f"MACHINEBUILD '{machinebuild}' not listed for {machine} "
                        f"(available: {', '.join(builds_display)})"
                    )

        if warnings:
            self.info("")
            self.warning("Warnings:")
            for item in warnings:
                self.warning(f"  {item}")

        image_immediate = self._find_image_immediate_assignments(
            self._machine_conf_sources(conf_dir, machine)
        )
        if image_immediate:
            self.info("")
            self.warning("Image naming uses ':=' with DATE/DATETIME (causes basehash changes):")
            for item in image_immediate:
                self.warning(f"  {item}")

        if errors:
            self.info("")
            self.error("Errors:")
            for item in errors:
                self.error(f"  {item}")
            sys.exit(1)

        if warnings:
            self.success("Configuration has warnings")
        else:
            self.success("Configuration looks OK")

    def init(self, args):
        """Initialize build environment."""
        self.log("=== Tuxbox-OS Builder Initialization ===", Colors.BOLD, bold=True)

        # Check prerequisites
        if not self.check_prerequisites():
            sys.exit(1)

        # Initialize submodules
        self.init_submodules()

        # Create build directories
        self.builddir.mkdir(parents=True, exist_ok=True)
        self.dl_dir.mkdir(parents=True, exist_ok=True)
        self.sstate_dir.mkdir(parents=True, exist_ok=True)

        # Save state
        state = {
            'initialized': True,
            'version': '1.0.0'
        }
        self.save_state(state)

        self.success("Build environment initialized successfully!")
        self.info("")
        self._print_kv_table("Environment", [
            ("Build dir", str(self.builddir)),
            ("DL dir", str(self.dl_dir)),
            ("SSTATE dir", str(self.sstate_dir)),
        ])

        examples = self._brand_summary_rows()
        if examples:
            self.info("")
            self._print_table("Machine examples (OE-Alliance)", ["Brand", "Examples"], examples)
            self.info("  Full list: make list-machines")

        hint_machine = getattr(args, 'machine', None) or os.environ.get('MACHINE')
        hint_machinebuild = getattr(args, 'machinebuild', None) or os.environ.get('MACHINEBUILD')
        example_machine = hint_machine or "hd51"
        example_machinebuild = hint_machinebuild if hint_machinebuild and hint_machinebuild != example_machine else None
        if hint_machine and not example_machinebuild:
            build_names, _ = self._machinebuild_candidates(hint_machine)
            if len(build_names) == 1 and build_names[0] != example_machine:
                example_machinebuild = build_names[0]

        self.info("")
        self._print_table("Next steps", ["Tool", "Command"], [
            (
                "Make",
                f"make image MACHINE={example_machine}" +
                (f" MACHINEBUILD={example_machinebuild}" if example_machinebuild else "")
            ),
            (
                "CLI",
                f"./cli.py build --machine {example_machine}" +
                (f" --machinebuild {example_machinebuild}" if example_machinebuild else "")
            ),
        ])
        if hint_machine:
            self.info("  Note: MACHINEBUILD is required for some machines.")
        else:
            self.info("  Note: examples use hd51 by default.")

    def build(self, args):
        """Build an image."""
        machine = args.machine or os.environ.get('MACHINE')
        machinebuild = args.machinebuild or os.environ.get('MACHINEBUILD')
        distro = args.distro
        distro_type = args.distro_type
        requested_target = args.target or 'tuxbox-image'
        target = 'package-index' if requested_target == 'feeds' else requested_target

        target_builddir = self._resolve_user_path(args.builddir) if args.builddir else None
        if not machine:
            selected = self._select_build_config(target_builddir)
            if not selected:
                self.error("No existing build config found. Specify --machine or run make config.")
                sys.exit(1)
            machine = selected.get('machine')
            if not machine:
                self.error("Selected config does not define MACHINE. Edit local.conf and try again.")
                sys.exit(1)
            if not machinebuild:
                machinebuild = selected.get('machinebuild')
            target_builddir = (
                self._resolve_user_path(selected['builddir'])
                if selected.get('builddir') else self.builddir
            )

        self._print_layer_refs()
        self.log(f"=== Building {target} for {machine} ===", Colors.BOLD, bold=True)

        # Select per-machine build directory (isolate Coolstream builds)
        if not target_builddir:
            target_builddir = self._default_builddir_for_machine(machine)
        self.builddir = target_builddir
        migrated_markers = self._migrate_saved_tmpdir_markers(target_builddir)
        if migrated_markers:
            self.info(
                f"Migrated {migrated_markers} TMPDIR marker(s) for builddir rename (build -> builds)"
            )

        # Check if initialized
        state = self.load_state()
        if not state.get('initialized'):
            self.warning("Build environment not initialized. Running init...")
            args.machine = machine
            args.machinebuild = machinebuild
            self.init(args)

        # Check if OE-Alliance submodule exists
        oe_alliance = self.topdir / 'oe-alliance'
        if not oe_alliance.exists():
            self.error("OE-Alliance submodule not found!")
            self.info("Please add submodule:")
            self.info("  git submodule add https://github.com/oe-alliance/oe-alliance-core.git oe-alliance")
            self.info("  git submodule update --init --recursive")
            sys.exit(1)

        # Generate configuration (only if missing or forced)
        conf_dir = target_builddir / 'conf'
        local_conf = conf_dir / 'local.conf'
        bblayers_conf = conf_dir / 'bblayers.conf'
        config_exists = local_conf.exists() and bblayers_conf.exists()
        shared_config_exists = (
            self._global_local_conf(target_builddir).exists()
            and self._global_bblayers_user_conf(target_builddir).exists()
        )
        legacy_config_exists = (
            (conf_dir / 'local.conf.user.inc').exists()
            or (conf_dir / 'bblayers.conf.user.inc').exists()
            or self._legacy_global_local_user_conf(target_builddir).exists()
        )
        config_status = "existing"
        if config_exists and not args.force_config and (not shared_config_exists or legacy_config_exists):
            self.error("Config exists but is not in the central-config layout.")
            if not shared_config_exists:
                self.error(f"  Missing shared config under {self.global_conf_dir}")
            if legacy_config_exists:
                self.error("  Legacy user include files are still present")
            self.info("Run 'make migrate-configs', 'make config FORCE_CONFIG=1', or pass --force-config.")
            sys.exit(1)
        if config_exists and not args.force_config:
            values = self._read_conf_values_with_sources(
                self._machine_conf_sources(conf_dir, machine),
                ['MACHINE', 'MACHINEBUILD'],
            )
            configured_machine = values.get('MACHINE', (None, None))[0]
            configured_machinebuild = values.get('MACHINEBUILD', (None, None))[0]
            mismatches = []
            if configured_machine and configured_machine != machine:
                mismatches.append(f"local.conf MACHINE={configured_machine} (requested {machine})")
            if machinebuild and configured_machinebuild and configured_machinebuild != machinebuild:
                mismatches.append(
                    f"local.conf MACHINEBUILD={configured_machinebuild} (requested {machinebuild})"
                )
            if mismatches:
                self.error("Config already exists and does not match requested values:")
                for item in mismatches:
                    self.error(f"  {item}")
                self.info("Run 'make migrate-configs', 'make config', or pass --force-config to overwrite.")
                sys.exit(1)
            if not machinebuild and configured_machinebuild:
                machinebuild = configured_machinebuild
        else:
            self.generate_config(machine, distro, distro_type, machinebuild, target_builddir)
            config_status = "generated"

        self.ensure_local_feed_config(conf_dir, machine)
        self.ensure_local_image_server_config(conf_dir, machine)
        self._validate_machinebuild(machine, machinebuild)

        local_feed_value = (
            self._local_feed_base_url(machine)
            if self._local_feed_enabled()
            else "disabled"
        )
        local_image_server_value = (
            self._local_image_update_base_url()
            if self._local_image_server_enabled()
            else "disabled"
        )

        self.info("")
        self._print_kv_table("Build summary", [
            ("Target", target),
            ("Machine", machine),
            ("MachineBuild", machinebuild or "-"),
            ("Distro", distro),
            ("Distro type", distro_type),
            ("Build dir", str(self.builddir)),
            ("Config", config_status),
            ("Local feed", local_feed_value),
            ("Local image server", local_image_server_value),
        ])

        # Setup environment and invoke BitBake
        if args.devshell:
            self.invoke_bitbake_devshell(target, machine)
        elif args.offline:
            self.invoke_bitbake(target, offline=True)
        else:
            self.invoke_bitbake(target, offline=False)

        if not args.devshell:
            self._post_build_local_feed(machine, target, target_builddir)
            self._post_build_image_server_hint(machine, machinebuild, target, target_builddir, distro_type)

    def invoke_bitbake(self, target: str, offline: bool = False):
        """Invoke BitBake to build target."""
        oe_init_script = self.topdir / 'poky' / 'oe-init-build-env'

        if not oe_init_script.exists():
            self.error(f"OE init script not found: {oe_init_script}")
            self.error("Please ensure Poky submodule is properly initialized")
            sys.exit(1)

        # Pre-flight: abort early on insufficient disk space so users get a
        # clear message instead of a raw pyinotify ENOSPC traceback from bitbake.
        min_disk = _resolve_min_disk_gb()
        free_gb = self._free_gb(self.builddir)
        if free_gb < min_disk:
            self.error(
                f"Zu wenig Speicherplatz: nur {free_gb:.1f}GB frei auf dem "
                f"Build-Dateisystem."
            )
            self.info(f"Build-Verzeichnis: {self.builddir}")
            self.info(
                f"Mindestens benoetigt: {min_disk:.0f}GB, "
                f"empfohlen: {RECOMMENDED_DISK_GB}GB+"
            )
            self._disk_full_hint()
            self.info("Es wurde kein bitbake gestartet.")
            sys.exit(1)
        elif free_gb < RECOMMENDED_DISK_GB:
            self.warning(
                f"Nur {free_gb:.1f}GB frei auf dem Build-Dateisystem "
                f"(empfohlen: {RECOMMENDED_DISK_GB}GB+). Build koennte scheitern."
            )

        # Build BitBake command. Only stderr is tee'd to a temp log so we can
        # scan it afterwards for resource-exhaustion errors (ENOSPC from
        # bitbake's pyinotify add_watch) while leaving stdout on the terminal,
        # which keeps bitbake's live progress UI intact. pipefail preserves
        # bitbake's exit code through the pipe.
        log_fd, log_path = tempfile.mkstemp(prefix='tuxbox-build-', suffix='.log')
        os.close(log_fd)
        quoted_log = shlex.quote(log_path)

        if offline:
            bb_cmd = f"BB_NO_NETWORK='1' bitbake {target}"
        else:
            bb_cmd = f"bitbake {target}"

        build_cmd = f"""
set -o pipefail
cd {self.topdir}
source {oe_init_script} {self.builddir}
{{ {bb_cmd} 2>&1 1>&3 | tee {quoted_log} >&2; }} 3>&1
"""

        self._print_table("BitBake command (oe-init-build-env)", ["Step", "Command"], [
            ("1", f"source {oe_init_script} {self.builddir}"),
            ("2", bb_cmd),
        ])
        self.info(f"Building target: {target}")
        if offline:
            self.info("Offline mode: enabled")

        # Execute build
        result = self.run_cmd(['bash', '-c', build_cmd], check=False)

        if result.returncode != 0:
            if self._build_log_has_enospc(log_path):
                # Disk-full or inotify-limit: give a clear cause + remedy
                # instead of the raw pyinotify traceback.
                self._explain_enospc()
            else:
                self.error(f"Build failed with exit code {result.returncode}")
            self._cleanup_file(log_path)
            sys.exit(1)

        self._cleanup_file(log_path)
        self.success(f"Build completed: {target}")
        self.info(f"Images: {self.builddir / 'tmp' / 'deploy' / 'images'}")

    def invoke_bitbake_devshell(self, target: str, machine: str):
        """Invoke BitBake devshell."""
        oe_init_script = self.topdir / 'poky' / 'oe-init-build-env'

        if not oe_init_script.exists():
            self.error(f"OE init script not found: {oe_init_script}")
            sys.exit(1)

        self.info(f"Starting devshell for {target}...")

        # Devshell command
        devshell_cmd = f"""
cd {self.topdir}
source {oe_init_script} {self.builddir}
bitbake -c devshell {target}
"""

        self._print_table("BitBake command (oe-init-build-env)", ["Step", "Command"], [
            ("1", f"source {oe_init_script} {self.builddir}"),
            ("2", f"bitbake -c devshell {target}"),
        ])
        # Execute interactively
        result = self.run_cmd(['bash', '-c', devshell_cmd], check=False)

        if result.returncode != 0:
            self.error("Devshell failed")
            sys.exit(1)

    def clean(self, args):
        """Clean build artifacts."""
        machine = args.machine

        self.log(f"Cleaning build for {machine}...", Colors.BOLD, bold=True)

        # TODO: Remove tmp artifacts for specific machine
        self.success("Build cleaned")

    def fetch_only(self, args):
        """Download sources without building."""
        machine = args.machine

        self.log(f"Fetching sources for {machine}...", Colors.BOLD, bold=True)

        # TODO: bitbake -c fetchall
        self.info("Fetch-only mode")

    def sync(self, args):
        """Sync with upstream and check for updates."""
        self.log("Syncing with upstream...", Colors.BOLD, bold=True)

        if args.check:
            # Check for updates without applying
            self.run_cmd(['git', 'fetch', '--all'])
            self.run_cmd(['git', 'submodule', 'foreach', 'git', 'fetch', '--all'])
            self.info("Checked for updates")
        else:
            # Apply updates
            self.run_cmd(['git', 'pull'])
            self.run_cmd(['git', 'submodule', 'update', '--remote', '--recursive'])
            self.success("Synced with upstream")

    # ------------------------------------------------------------------
    # info command
    # ------------------------------------------------------------------

    def _builder_version(self) -> str:
        """Detect builder version from git, gitpkgv count-short style.

        On a version tag:        1.2.0
        N commits after tag:     1.2.0-git5
        No version tag in repo:  0.0-git142
        """
        # Try git describe with version-like tags (v1.0, 1.0, ver1.0)
        describe = self._git_output(
            self.topdir, ['describe', '--tags', '--long', '--match', 'v[0-9]*']
        ) or self._git_output(
            self.topdir, ['describe', '--tags', '--long', '--match', '[0-9]*']
        )
        if describe:
            m = re.match(r'^v?e?r?(\d[^-]*)-(\d+)-g[0-9a-f]+$', describe)
            if m:
                tag_ver = m.group(1)
                ahead = int(m.group(2))
                if ahead == 0:
                    return tag_ver
                return f"{tag_ver}-git{ahead}"

        # No version tag — use commit count
        count = self._git_output(self.topdir, ['rev-list', 'HEAD', '--count']) or "0"
        return f"0.0-git{count}"

    def _yocto_version(self) -> Tuple[str, str]:
        """Read Yocto codename and version from poky distro conf.

        Returns (codename, version) e.g. ("kirkstone", "4.0.32").
        """
        poky_conf = self.topdir / 'poky' / 'meta-poky' / 'conf' / 'distro' / 'poky.conf'
        codename = ""
        version = ""
        if poky_conf.exists():
            try:
                text = poky_conf.read_text(errors='ignore')
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith('#'):
                        continue
                    m = re.match(r'DISTRO_CODENAME\s*=\s*"([^"]+)"', line)
                    if m:
                        codename = m.group(1)
                    m = re.match(r'DISTRO_VERSION\s*=\s*"([^"]+)"', line)
                    if m and 'snapshot' not in m.group(1):
                        version = m.group(1)
            except OSError:
                pass
        if not codename and not version:
            return ("kirkstone", "4.0")
        return (codename, version)

    def _ccache_status(self) -> Dict:
        """Collect ccache status information."""
        result: Dict = {"enabled": False}
        if not shutil.which("ccache"):
            return result

        # Check if ccache is configured in any shared or machine build conf
        ccache_in_conf = False
        conf_files = [self._global_local_conf()]
        for builddir in self._discover_builddirs():
            conf_dir = builddir / "conf"
            machine, _ = self._read_machine_values_from_conf(conf_dir)
            conf_files.append(conf_dir / "local.conf")
            if machine:
                conf_files.append(conf_dir / f"local.conf.{machine}.inc")
        seen_conf_files: Set[Path] = set()
        for conf_file in conf_files:
            if conf_file in seen_conf_files or not conf_file.exists():
                continue
            seen_conf_files.add(conf_file)
            try:
                text = conf_file.read_text(errors="ignore")
                if re.search(r'^\s*INHERIT\s*\+?=.*"ccache"', text, re.MULTILINE):
                    ccache_in_conf = True
                    break
            except OSError:
                pass

        if not ccache_in_conf:
            return result

        result["enabled"] = True
        try:
            proc = subprocess.run(
                ["ccache", "-s"],
                capture_output=True, text=True, timeout=5
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    stripped = line.strip()
                    stripped_lower = stripped.lower()
                    # New format: "Cache size (GB):  4.56 /  5.00 (91.25%)"
                    m = re.match(r'Cache size\s*\([^)]*\)\s*:\s*(\S+)\s*/\s*(\S+)', stripped)
                    if m:
                        result["size"] = m.group(1)
                        result["max_size"] = m.group(2)
                        continue
                    # New format: "Hits: 7373 / 28523 (25.85%)"
                    if stripped_lower.startswith("hits:") and "direct" not in stripped_lower and "preprocessed" not in stripped_lower:
                        m2 = re.match(r'Hits:\s*(\d+)\s*/\s*(\d+)\s*\(([^)]+)\)', stripped, re.IGNORECASE)
                        if m2:
                            result["hit_rate"] = m2.group(3)
                            continue
                    # Old format fallback
                    if "cache size" in stripped_lower and "max" not in stripped_lower:
                        parts = stripped.split(":")
                        if len(parts) >= 2:
                            result["size"] = parts[-1].strip()
                    elif "max cache size" in stripped_lower:
                        parts = stripped.split(":")
                        if len(parts) >= 2:
                            result["max_size"] = parts[-1].strip()
                    elif "hit rate" in stripped_lower:
                        parts = stripped.split(":")
                        if len(parts) >= 2:
                            result["hit_rate"] = parts[-1].strip()
        except (subprocess.TimeoutExpired, OSError):
            pass
        return result

    def _collect_info(self, machine: Optional[str] = None,
                      distro: str = "tuxbox",
                      distro_type: str = "release",
                      machinebuild: Optional[str] = None,
                      builddir: Optional[str] = None) -> Dict:
        """Collect all info data into a dict."""
        data: Dict = {}

        # Version info
        data["builder_version"] = self._builder_version()
        codename, yocto_ver = self._yocto_version()
        data["yocto_codename"] = codename
        data["yocto_version"] = yocto_ver
        py = sys.version_info
        data["python_version"] = f"{py.major}.{py.minor}.{py.micro}"
        git_proc = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        )
        git_ver = git_proc.stdout.strip().replace("git version ", "") if git_proc.returncode == 0 else "unknown"
        data["git_version"] = git_ver

        # Build configuration
        configured = False
        build_config: Dict = {}
        if machine:
            target_builddir = self._resolve_user_path(builddir) if builddir else self._default_builddir_for_machine(machine)
            conf_dir = target_builddir / "conf"
            local_conf = conf_dir / "local.conf"

            build_config["build_dir"] = str(target_builddir)
            if local_conf.exists():
                configured = True
                keys = [
                    "MACHINE", "MACHINEBUILD", "DISTRO", "DISTRO_TYPE",
                    "DL_DIR", "SSTATE_DIR", "TMPDIR", "IPK_FEED_SERVER",
                    "TUXBOX_IMAGE_UPDATE_BASE_URL", "TUXBOX_IMAGE_UPDATE_URL",
                    "TUXBOX_IMAGE_MANIFEST_FILE",
                ]
                conf_sources = self._machine_conf_sources(conf_dir, machine)
                values_with_sources = self._read_conf_values_with_sources(conf_sources, keys)
                for key in keys:
                    value, _ = values_with_sources.get(key, (None, None))
                    build_config[key.lower()] = value
            else:
                build_config["machine"] = machine
                build_config["machinebuild"] = machinebuild or machine
                build_config["distro"] = distro
                build_config["distro_type"] = distro_type
        else:
            # No machine specified — try to detect from existing config
            for bd in self._discover_builddirs():
                conf_dir = bd / "conf"
                lc = conf_dir / "local.conf"
                if lc.exists():
                    detected_machine, _ = self._read_machine_values_from_conf(conf_dir)
                    conf_sources = (
                        self._machine_conf_sources(conf_dir, detected_machine)
                        if detected_machine else [lc, self._global_local_conf()]
                    )
                    vals = self._read_conf_values_with_sources(
                        conf_sources, ["MACHINE", "MACHINEBUILD", "DISTRO", "DISTRO_TYPE", "DL_DIR", "SSTATE_DIR", "TMPDIR"]
                    )
                    build_config["build_dir"] = str(bd)
                    configured = True
                    for key in ["MACHINE", "MACHINEBUILD", "DISTRO", "DISTRO_TYPE", "DL_DIR", "SSTATE_DIR", "TMPDIR"]:
                        value, _ = vals.get(key, (None, None))
                        build_config[key.lower()] = value
                    break

        data["configured"] = configured
        data["build"] = build_config

        # Layer refs
        layers_list = []
        layers = [
            ("poky", self.topdir / "poky"),
            ("oe-alliance", self.topdir / "oe-alliance"),
            ("meta-openembedded", self.topdir / "meta-openembedded"),
            ("meta-neutrino", self.topdir / "meta-neutrino"),
            ("meta-tuxbox", self.topdir / "meta-tuxbox"),
        ]
        for name, path in layers:
            ref = self._layer_ref(path)
            if ref:
                state, ref_name, commit = ref
                layers_list.append({"name": name, "state": state, "ref": ref_name, "commit": commit})
            elif path.exists():
                layers_list.append({"name": name, "state": "unknown", "ref": "-", "commit": "-"})
            else:
                layers_list.append({"name": name, "state": "missing", "ref": "-", "commit": "-"})
        data["layers"] = layers_list

        # Prerequisites (quick)
        prereq: Dict = {}
        free_gb = self._free_gb(self.topdir)
        prereq["disk_free_gb"] = round(free_gb, 1)

        required_cmds = [
            "git", "gcc", "make", "python3", "patch", "diffstat",
            "tar", "gzip", "bzip2", "xz", "unzip", "wget", "curl"
        ]
        missing = [cmd for cmd in required_cmds if not shutil.which(cmd)]
        if missing:
            prereq["status"] = "missing_tools"
            prereq["missing"] = missing
        elif free_gb < RECOMMENDED_DISK_GB:
            prereq["status"] = "low_disk"
        else:
            prereq["status"] = "ok"
        data["prerequisites"] = prereq

        # ccache
        data["ccache"] = self._ccache_status()

        return data

    def cmd_info(self, args):
        """Show build system status overview."""
        machine = getattr(args, "machine", None)
        distro = getattr(args, "distro", "tuxbox")
        distro_type = getattr(args, "distro_type", "release")
        machinebuild = getattr(args, "machinebuild", None)
        builddir = getattr(args, "builddir", None)
        as_json = getattr(args, "json", False)

        data = self._collect_info(machine, distro, distro_type, machinebuild, builddir)

        if as_json:
            print(json.dumps(data, indent=2))
            return

        # Header
        self.log(
            f"Tuxbox-OS Builder v{data['builder_version']}",
            Colors.BOLD, bold=True
        )
        codename = data.get('yocto_codename', '')
        yocto_ver = data.get('yocto_version', '')
        yocto_display = f"{codename.capitalize()} ({yocto_ver})" if codename else yocto_ver
        self.info(
            f"Yocto:   {yocto_display}    "
            f"Python: {data['python_version']}    "
            f"Git: {data['git_version']}"
        )
        print()

        # Build configuration
        build = data.get("build", {})
        if data["configured"]:
            self.log("── Build Configuration ─────────────────────────", Colors.BOLD, bold=True)
            build_dir = build.get("build_dir")
            kv = [
                ("MACHINE", build.get("machine", "-")),
                ("MACHINEBUILD", build.get("machinebuild", "-")),
                ("DISTRO", build.get("distro", "-")),
                ("DISTRO_TYPE", build.get("distro_type", "-")),
                ("Build dir", build_dir or "-"),
            ]
            if build.get("dl_dir"):
                kv.append(("DL_DIR", build["dl_dir"]))
            if build.get("sstate_dir"):
                kv.append(("SSTATE_DIR", build["sstate_dir"]))
            if build.get("tmpdir"):
                kv.append(("TMPDIR", self._resolve_topdir_in_path(build["tmpdir"], build_dir)))
            width = max(len(k) for k, _ in kv)
            for key, val in kv:
                self.info(f"  {key:<{width}}  {val}")
        elif machine:
            self.log("── Build Configuration ─────────────────────────", Colors.BOLD, bold=True)
            self.warning(f"  Not configured yet (no local.conf for {machine})")
            self.info(f"  Run: make config MACHINE={machine}")
        else:
            self.log("── Build Configuration ─────────────────────────", Colors.BOLD, bold=True)
            self.warning("  No MACHINE specified and no existing config found")
            self.info("  Run: make config MACHINE=<machine>")
        print()

        # Layer refs
        layers = data.get("layers", [])
        if layers:
            self.log("── Layer Refs ──────────────────────────────────", Colors.BOLD, bold=True)
            rows = [(l["name"], l["state"], l["ref"], l["commit"]) for l in layers]
            headers = ["Layer", "State", "Ref", "Commit"]
            col_widths = [len(h) for h in headers]
            for row in rows:
                for idx, cell in enumerate(row):
                    col_widths[idx] = max(col_widths[idx], len(str(cell)))
            header_line = "  " + "  ".join(
                f"{headers[idx]:<{col_widths[idx]}}" for idx in range(len(headers))
            )
            self.info(header_line)
            self.info("  " + "  ".join("-" * w for w in col_widths))
            for row in rows:
                color = Colors.YELLOW if row[1] in ("missing", "unknown") else Colors.CYAN
                line = "  " + "  ".join(
                    f"{str(row[idx]):<{col_widths[idx]}}" for idx in range(len(headers))
                )
                self.log(line, color)
        print()

        # System
        prereq = data.get("prerequisites", {})
        self.log("── System ──────────────────────────────────────", Colors.BOLD, bold=True)
        status = prereq.get("status", "unknown")
        if status == "ok":
            self.success(f"Prerequisites: OK")
        elif status == "low_disk":
            self.warning(f"Prerequisites: OK (low disk space)")
        elif status == "missing_tools":
            self.error(f"Prerequisites: missing tools: {', '.join(prereq.get('missing', []))}")
        self.info(f"  Disk space:    {prereq.get('disk_free_gb', '?')} GB free")

        # ccache
        cc = data.get("ccache", {})
        if cc.get("enabled"):
            parts = ["enabled"]
            if cc.get("size") and cc.get("max_size"):
                parts.append(f"{cc['size']}/{cc['max_size']} GB")
            elif cc.get("size"):
                parts.append(f"size: {cc['size']}")
            if cc.get("hit_rate"):
                parts.append(f"hit rate: {cc['hit_rate']}")
            self.info(f"  ccache:        {', '.join(parts)}")
        else:
            self.info("  ccache:        not active")

    def cmd_version(self, args):
        """Show version information."""
        builder_ver = self._builder_version()
        codename, yocto_ver = self._yocto_version()
        py = sys.version_info
        git_proc = subprocess.run(["git", "--version"], capture_output=True, text=True)
        git_ver = git_proc.stdout.strip().replace("git version ", "") if git_proc.returncode == 0 else "unknown"

        if getattr(args, "json", False):
            print(json.dumps({
                "builder_version": builder_ver,
                "yocto_codename": codename,
                "yocto_version": yocto_ver,
                "python_version": f"{py.major}.{py.minor}.{py.micro}",
                "git_version": git_ver,
            }, indent=2))
            return

        yocto_display = f"{codename.capitalize()} ({yocto_ver})" if codename else yocto_ver
        print(f"Tuxbox-OS Builder v{builder_ver}")
        print(f"Yocto: {yocto_display}")
        print(f"Python: {py.major}.{py.minor}.{py.micro}")
        print(f"Git: {git_ver}")

    def check(self, args):
        """Check system prerequisites."""
        if self.check_prerequisites():
            self.success("System ready for building")
            sys.exit(0)
        else:
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Tuxbox-OS Builder - Production build system for Tuxbox-Neutrino',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # init command
    init_parser = subparsers.add_parser('init', help='Initialize build environment')
    init_parser.add_argument('-m', '--machine', help='Preferred machine for next-step hints')
    init_parser.add_argument('--machinebuild', help='OEM machine variant for hints')

    # build command
    build_parser = subparsers.add_parser('build', help='Build an image')
    build_parser.add_argument('-m', '--machine', help='Target machine (auto-detect from config if omitted)')
    build_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    build_parser.add_argument('--machinebuild', help='OEM machine variant (defaults to MACHINE or $MACHINEBUILD)')
    build_parser.add_argument(
        '--builddir',
        help='Custom build directory (default: builds/<machine>)'
    )
    build_parser.add_argument('-t', '--target', help='Build target (default: tuxbox-image)')
    build_parser.add_argument('--offline', action='store_true', help='Offline build mode')
    build_parser.add_argument('--no-sstate', action='store_true', help='Disable sstate cache')
    build_parser.add_argument('--devshell', action='store_true', help='Drop to development shell')
    build_parser.add_argument('--force-config', action='store_true',
                             help='Regenerate local.conf/bblayers.conf even if they exist')
    build_parser.add_argument('--distro-type', choices=['release', 'development'],
                            default='release', help='Build type')
    
    # config-only command
    config_parser = subparsers.add_parser('config', help='Generate configs only (no build)')
    config_parser.add_argument('-m', '--machine', required=True, help='Target machine')
    config_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    config_parser.add_argument('--machinebuild', help='OEM machine variant (defaults to MACHINE or $MACHINEBUILD)')
    config_parser.add_argument(
        '--builddir',
        help='Custom build directory (default: builds/<machine>)'
    )
    config_parser.add_argument('--distro-type', choices=['release', 'development'],
                            default='release', help='Build type')

    # show-config command
    show_config_parser = subparsers.add_parser('show-config', help='Show current configuration')
    show_config_parser.add_argument('-m', '--machine', required=True, help='Target machine')
    show_config_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    show_config_parser.add_argument('--machinebuild', help='OEM machine variant (defaults to MACHINE or $MACHINEBUILD)')
    show_config_parser.add_argument(
        '--builddir',
        help='Custom build directory (default: builds/<machine>)'
    )
    show_config_parser.add_argument('--distro-type', choices=['release', 'development'],
                                    default='release', help='Build type')

    # machines command
    machines_parser = subparsers.add_parser('machines', help='List machines by brand')
    machines_parser.add_argument('--brand', help='Filter by brand (e.g., gfutures)')
    machines_parser.add_argument('--with-builds', action='store_true',
                                 help='Include MACHINEBUILD variants per machine')

    # machine-info command
    machine_info_parser = subparsers.add_parser('machine-info', help='Show details for a machine')
    machine_info_parser.add_argument('-m', '--machine', required=True, help='Target machine')

    # audit-machine-mapping command
    audit_parser = subparsers.add_parser(
        'audit-machine-mapping',
        help='Audit MACHINE/MACHINEBUILD, kernel, and image mapping without building'
    )
    audit_parser.add_argument('-m', '--machine', help='Limit audit to one machine')
    audit_parser.add_argument('--machinebuild', help='Limit audit to one MACHINEBUILD')
    audit_parser.add_argument('--brand', help='Limit global audit to one brand')
    audit_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    audit_parser.add_argument('--distro-type', choices=['release', 'development'],
                              default='release', help='Build type')
    audit_parser.add_argument(
        '--bitbake',
        choices=['none', 'selected', 'high-risk', 'suspicious', 'all'],
        default='high-risk',
        help='Run bitbake -e for selected rows (default: high-risk)'
    )
    audit_parser.add_argument('--bitbake-timeout', type=int, default=180,
                              help='Timeout in seconds for each bitbake -e parse')
    audit_parser.add_argument('--deploy', action='store_true',
                              help='Inspect latest deploy zip for selected rows')
    audit_parser.add_argument('--live', action='store_true',
                              help='Read-only SSH check for known live boxes')
    audit_parser.add_argument('--scratch-root',
                              help='Scratch root for generated configs (default: /tmp/tuxbox-audit/run-*)')
    audit_parser.add_argument('--keep-scratch', action='store_true',
                              help='Keep generated scratch configs after the audit')
    audit_parser.add_argument('--limit', type=int,
                              help='Limit number of rows, useful while developing the audit')
    audit_parser.add_argument('--json', action='store_true', help='Output JSON')

    # migrate-configs command
    migrate_parser = subparsers.add_parser(
        'migrate-configs',
        help='Migrate legacy shared configs into per-machine build dirs'
    )
    migrate_mode = migrate_parser.add_mutually_exclusive_group()
    migrate_mode.add_argument('--apply', action='store_true', help='Apply safe migrations')
    migrate_mode.add_argument('--check', action='store_true', help='Fail if migrations are needed')
    migrate_mode.add_argument('--dry-run', action='store_true', help='Show planned migrations only')
    migrate_parser.add_argument('--json', action='store_true', help='Output JSON')

    # deploy-info command
    deploy_info_parser = subparsers.add_parser(
        'deploy-info',
        help='Resolve and validate machine-aware build/deploy paths'
    )
    deploy_info_parser.add_argument('-m', '--machine', required=True, help='Target machine')
    deploy_info_parser.add_argument('--machinebuild', help='OEM machine variant')
    deploy_info_parser.add_argument('--builddir', help='Build directory to inspect')
    deploy_info_parser.add_argument('--require-ipk', action='store_true',
                                    help='Fail if deploy/ipk is missing')
    deploy_info_parser.add_argument('--require-images', action='store_true',
                                    help='Fail if deploy/images/<machine> is missing')
    deploy_info_parser.add_argument('--require-manifest', action='store_true',
                                    help='Fail if manifest.json is missing or inconsistent')
    deploy_info_parser.add_argument('--json', action='store_true', help='Output JSON')

    # clean command
    clean_parser = subparsers.add_parser('clean', help='Clean build artifacts')
    clean_parser.add_argument('-m', '--machine', help='Machine to clean (all if not specified)')

    # fetch-only command
    fetch_parser = subparsers.add_parser('fetch-only', help='Download sources only')
    fetch_parser.add_argument('-m', '--machine', required=True, help='Target machine')

    # sync command
    sync_parser = subparsers.add_parser('sync', help='Sync with upstream')
    sync_parser.add_argument('--check', action='store_true', help='Check for updates only')

    # check command
    check_parser = subparsers.add_parser('check', help='Check system prerequisites')

    # version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    version_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # info command
    info_parser = subparsers.add_parser('info', help='Show build system status overview')
    info_parser.add_argument('-m', '--machine', help='Target machine (auto-detect from config if omitted)')
    info_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    info_parser.add_argument('--machinebuild', help='OEM machine variant')
    info_parser.add_argument('--builddir', help='Custom build directory')
    info_parser.add_argument('--distro-type', choices=['release', 'development'],
                             default='release', help='Build type')
    info_parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create builder instance
    builder = TuxboxBuilder()

    # Dispatch commands
    if args.command == 'init':
        builder.init(args)
    elif args.command == 'build':
        builder.build(args)
    elif args.command == 'config':
        target_builddir = builder._resolve_user_path(args.builddir) if args.builddir else (
            builder._default_builddir_for_machine(args.machine)
        )
        builder.generate_config(args.machine, args.distro, args.distro_type, args.machinebuild, target_builddir)
        builder.success(f"Config generated at {target_builddir}/conf")
    elif args.command == 'show-config':
        builder.show_config(args)
    elif args.command == 'machines':
        builder.machines(args)
    elif args.command == 'machine-info':
        builder.machine_info(args)
    elif args.command == 'audit-machine-mapping':
        builder.audit_machine_mapping(args)
    elif args.command == 'migrate-configs':
        builder.migrate_configs(args)
    elif args.command == 'deploy-info':
        builder.deploy_info(args)
    elif args.command == 'clean':
        builder.clean(args)
    elif args.command == 'fetch-only':
        builder.fetch_only(args)
    elif args.command == 'sync':
        builder.sync(args)
    elif args.command == 'check':
        builder.check(args)
    elif args.command == 'version':
        builder.cmd_version(args)
    elif args.command == 'info':
        builder.cmd_info(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
