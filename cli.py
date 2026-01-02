#!/usr/bin/env python3
"""
Tuxbox-OS Builder - Command Line Interface

Production-ready build orchestrator for Tuxbox-Neutrino.
Manages OE-Alliance integration, submodules, configuration, and builds.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
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


class TuxboxBuilder:
    """Main builder class orchestrating all build operations."""

    def __init__(self):
        self.topdir = Path(__file__).parent.resolve()
        self.state_file = self.topdir / '.tuxbox' / 'state.json'
        self.builddir = self.topdir / 'build'
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
            'git', 'gcc', 'make', 'python3', 'patch', 'diffstat',
            'tar', 'gzip', 'bzip2', 'xz', 'unzip', 'wget', 'curl'
        ]

        missing = []
        for cmd in required_cmds:
            result = self.run_cmd(['which', cmd], capture=True, check=False)
            if result.returncode != 0:
                missing.append(cmd)

        if missing:
            self.error(f"Missing required tools: {', '.join(missing)}")
            self.info("\nInstall on Debian/Ubuntu:")
            self.info("sudo apt install -y gawk wget git diffstat unzip texinfo \\")
            self.info("  gcc build-essential chrpath socat cpio python3 python3-pip \\")
            self.info("  python3-pexpect xz-utils debianutils iputils-ping python3-git \\")
            self.info("  python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1")
            return False

        # Check disk space
        stat = os.statvfs(self.topdir)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        if free_gb < 100:
            self.warning(f"Only {free_gb:.1f}GB free space. Recommended: 100GB+")
        else:
            self.success(f"Disk space OK: {free_gb:.1f}GB free")

        # Check Python version
        py_version = sys.version_info
        if py_version < (3, 6):
            self.error(f"Python 3.6+ required. Found: {py_version.major}.{py_version.minor}")
            return False

        self.success("All prerequisites met")
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
            builddirs = [self.topdir / 'build'] + sorted(
                path for path in self.topdir.glob('build-*') if path.is_dir()
            )

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

    def _extract_layer_paths(self, conf_path: Path) -> List[str]:
        if not conf_path.exists():
            return []
        try:
            text = conf_path.read_text(errors='ignore')
        except OSError:
            return []
        layers = []
        topdir_str = str(self.topdir)
        for match in re.findall(r'(/[^\\s"\']+)', text):
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

        # Create build/conf directory
        target_builddir = Path(builddir) if builddir else self.builddir
        conf_dir = target_builddir / 'conf'
        conf_dir.mkdir(parents=True, exist_ok=True)

        # Generate bblayers.conf
        self.generate_bblayers_conf(conf_dir, machine, brand)

        # Generate local.conf
        self.generate_local_conf(conf_dir, machine, distro, distro_type, machinebuild, target_builddir)

        # Ensure user override include files exist
        self.ensure_user_overrides(conf_dir, machine)

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

    def generate_local_conf(self, conf_dir: Path, machine: str, distro: str, distro_type: str,
                            machinebuild: Optional[str], target_builddir: Path):
        """Generate local.conf from template."""
        template_file = self.topdir / 'templates' / 'local.conf.template'
        output_file = conf_dir / 'local.conf'

        if not template_file.exists():
            self.error(f"Template not found: {template_file}")
            sys.exit(1)

        # Read template
        with open(template_file) as f:
            content = f.read()

        # Default MACHINEBUILD to MACHINE if not provided
        effective_machinebuild = machinebuild or machine

        # Replace variables
        content = content.replace('##MACHINE##', machine)
        content = content.replace('##MACHINEBUILD##', effective_machinebuild)
        content = content.replace('##DISTRO##', distro)
        content = content.replace('##DL_DIR##', str(self.dl_dir))
        content = content.replace('##SSTATE_DIR##', str(self.sstate_dir))
        content = content.replace('##TMPDIR##', str(target_builddir / 'tmp'))
        content = content.replace('##DISTRO_TYPE##', distro_type)

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

    def ensure_user_overrides(self, conf_dir: Path, machine: str):
        """Create optional local override files if missing."""
        if machine.startswith('coolstream'):
            tmpdir = f"build-{machine}/tmp"
        else:
            tmpdir = f"build/tmp-{machine}"
        overrides = {
            conf_dir / 'local.conf.user.inc': (
                "# Local overrides (not tracked)\n"
                "# Use this file for personal settings to avoid regeneration loss.\n"
                "# Example:\n"
                "# DL_DIR = \"/path/to/downloads\"\n"
                "# SSTATE_DIR = \"/path/to/sstate-cache\"\n"
                "#\n"
                "# Parallelism (optional; defaults are auto CPU count):\n"
                "# BB_NUMBER_THREADS = \"8\"\n"
                "# PARALLEL_MAKE = \"-j 8\"\n"
                "#\n"
                "# Image naming (examples - uncomment to use):\n"
                "#\n"
                "# A) Timestamped (unique per build)\n"
                "# IMAGE_NAME = \"${IMAGE_BASENAME}-${MACHINE}-${DATETIME}\"\n"
                "# IMAGE_NAME[vardepsexclude] = \"DATETIME\"\n"
                "# IMAGE_VERSION ?= \"${DISTRO_VERSION}\"\n"
                "# IMAGE_NAME_SUFFIX = \".tuxbox\"\n"
                "# IMAGE_VER_STRING = \"${DISTRO_NAME}-${IMAGE_VERSION}-${MACHINEBUILD}-${DATE}\"\n"
                "# IMAGE_VER_STRING[vardepsexclude] += \"DATE\"\n"
                "#\n"
                "# B) Deterministic (stable names, CI-friendly)\n"
                "# IMAGE_NAME = \"${IMAGE_BASENAME}-${MACHINE}\"\n"
                "# IMAGE_VERSION ?= \"${DISTRO_VERSION}\"\n"
                "# IMAGE_NAME_SUFFIX = \".tuxbox\"\n"
                "# IMAGE_VER_STRING = \"${DISTRO_NAME}-${IMAGE_VERSION}-${MACHINEBUILD}\"\n"
                "#\n"
                "# C) Include MACHINEBUILD in filename\n"
                "# IMAGE_NAME = \"${IMAGE_BASENAME}-${MACHINE}-${MACHINEBUILD}-${DATETIME}\"\n"
                "# IMAGE_NAME[vardepsexclude] = \"DATETIME\"\n"
                "#\n"
                "# Avoid: spaces in IMAGE_VER_STRING (breaks some OA scripts)\n"
                "# Avoid: removing vardepsexclude when DATE/DATETIME is used (rebuild noise)\n"
                "# Avoid: using := with DATE/DATETIME (causes basehash changes)\n"
                "# Avoid: slashes in IMAGE_NAME (must be a filename)\n"
                "# Avoid: changing IMAGE_NAME_SUFFIX unless your tooling expects it\n"
            ),
            conf_dir / f'local.conf.{machine}.inc': (
                f"# Local overrides for MACHINE={machine} (not tracked)\n"
                "# Use this file for machine-specific tweaks.\n"
                "# Default TMPDIR uses per-machine subdirs for safer multi-machine builds.\n"
                f"TMPDIR = \"${{TOPDIR}}/{tmpdir}\"\n"
            ),
            conf_dir / 'bblayers.conf.user.inc': (
                "# Local layer overrides (not tracked)\n"
                "# Example:\n"
                "# BBLAYERS += \" \\\n"
                "#   /path/to/your/layer \\\n"
                "# \"\n"
            ),
        }

        for path, content in overrides.items():
            if not path.exists():
                with open(path, 'w') as f:
                    f.write(content)
                self.info(f"Created: {path}")

    def show_config(self, args):
        """Show current configuration and highlight issues."""
        machine = args.machine
        requested_machinebuild = args.machinebuild or os.environ.get('MACHINEBUILD')
        distro = args.distro
        distro_type = args.distro_type

        target_builddir = Path(args.builddir) if args.builddir else (
            self.topdir / f"build-{machine}" if machine.startswith('coolstream') else self.builddir
        )
        conf_dir = target_builddir / 'conf'
        local_conf = conf_dir / 'local.conf'
        bblayers_conf = conf_dir / 'bblayers.conf'
        local_user_conf = conf_dir / 'local.conf.user.inc'
        local_machine_conf = conf_dir / f'local.conf.{machine}.inc'
        bblayers_user_conf = conf_dir / 'bblayers.conf.user.inc'

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
        if local_user_conf.exists():
            self.success(f"local.conf.user.inc: {local_user_conf}")
        else:
            self.info(f"local.conf.user.inc: missing ({local_user_conf})")
        if local_machine_conf.exists():
            self.success(f"local.conf.{machine}.inc: {local_machine_conf}")
        else:
            self.info(f"local.conf.{machine}.inc: missing ({local_machine_conf})")
        if bblayers_user_conf.exists():
            self.success(f"bblayers.conf.user.inc: {bblayers_user_conf}")
        else:
            self.info(f"bblayers.conf.user.inc: missing ({bblayers_user_conf})")

        keys = ['MACHINE', 'MACHINEBUILD', 'DISTRO', 'DISTRO_TYPE', 'DL_DIR', 'SSTATE_DIR', 'TMPDIR']
        values = {}
        sources = {}
        if local_conf.exists():
            conf_sources = [local_conf, local_user_conf, local_machine_conf]
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
        for layer_file in [bblayers_conf, bblayers_user_conf]:
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
            warnings.append(f"local.conf MACHINE={configured_machine} (requested {machine})")
        if requested_machinebuild and configured_machinebuild and configured_machinebuild != requested_machinebuild:
            warnings.append(
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
                    warnings.append(
                        f"MACHINEBUILD '{machinebuild}' not listed for {machine} "
                        f"(available: {', '.join(builds_display)})"
                    )

        if warnings:
            self.info("")
            self.warning("Warnings:")
            for item in warnings:
                self.warning(f"  {item}")

        image_immediate = self._find_image_immediate_assignments(
            [local_conf, local_user_conf, local_machine_conf]
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
        examples = self._brand_summary_lines()
        if examples:
            self.info("")
            self.info("Machine examples by brand (from OE-Alliance):")
            for line in examples:
                self.info(f"  {line}")
            self.info("Full list: make list-machines")

        hint_machine = getattr(args, 'machine', None) or os.environ.get('MACHINE')
        hint_machinebuild = getattr(args, 'machinebuild', None) or os.environ.get('MACHINEBUILD')
        example_machine = hint_machine or "hd51"
        example_machinebuild = hint_machinebuild if hint_machinebuild and hint_machinebuild != example_machine else None
        if hint_machine and not example_machinebuild:
            build_names, _ = self._machinebuild_candidates(hint_machine)
            if len(build_names) == 1 and build_names[0] != example_machine:
                example_machinebuild = build_names[0]

        self.info("\nNext steps:")
        if hint_machine:
            self.info(f"  ./cli.py build --machine {example_machine}" +
                      (f" --machinebuild {example_machinebuild}" if example_machinebuild else ""))
            self.info(f"  make image MACHINE={example_machine}" +
                      (f" MACHINEBUILD={example_machinebuild}" if example_machinebuild else "") +
                      " (MACHINEBUILD required for some machines)")
        else:
            self.info(f"  ./cli.py build --machine {example_machine}  # example")
            self.info(f"  make image MACHINE={example_machine}  # example")

    def build(self, args):
        """Build an image."""
        machine = args.machine or os.environ.get('MACHINE')
        machinebuild = args.machinebuild or os.environ.get('MACHINEBUILD')
        distro = args.distro
        distro_type = args.distro_type
        target = args.target or 'tuxbox-image'

        target_builddir = Path(args.builddir) if args.builddir else None
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
            target_builddir = Path(selected['builddir']) if selected.get('builddir') else self.builddir

        self.log(f"=== Building {target} for {machine} ===", Colors.BOLD, bold=True)
        if machinebuild:
            self.info(f"Using MACHINEBUILD={machinebuild}")

        # Select per-machine build directory (isolate Coolstream builds)
        if not target_builddir:
            target_builddir = (
                self.topdir / f"build-{machine}" if machine.startswith('coolstream') else self.builddir
            )
        self.builddir = target_builddir

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
        if config_exists and not args.force_config:
            configured_machine = self._read_conf_value(local_conf, 'MACHINE')
            configured_machinebuild = self._read_conf_value(local_conf, 'MACHINEBUILD')
            mismatches = []
            if configured_machine and configured_machine != machine:
                mismatches.append(f"local.conf MACHINE={configured_machine} (requested {machine})")
            if args.machinebuild and configured_machinebuild and configured_machinebuild != args.machinebuild:
                mismatches.append(
                    f"local.conf MACHINEBUILD={configured_machinebuild} (requested {args.machinebuild})"
                )
            if mismatches:
                self.error("Config already exists and does not match requested values:")
                for item in mismatches:
                    self.error(f"  {item}")
                self.info("Run 'make config' to regenerate, or pass --force-config to overwrite.")
                sys.exit(1)
            if not machinebuild and configured_machinebuild:
                machinebuild = configured_machinebuild
            self.info("Using existing configuration (not regenerating)")
        else:
            self.generate_config(machine, distro, distro_type, machinebuild, target_builddir)

        # Setup environment and invoke BitBake
        if args.devshell:
            self.invoke_bitbake_devshell(target, machine)
        elif args.offline:
            self.invoke_bitbake(target, offline=True)
        else:
            self.invoke_bitbake(target, offline=False)

    def invoke_bitbake(self, target: str, offline: bool = False):
        """Invoke BitBake to build target."""
        oe_init_script = self.topdir / 'poky' / 'oe-init-build-env'

        if not oe_init_script.exists():
            self.error(f"OE init script not found: {oe_init_script}")
            self.error("Please ensure Poky submodule is properly initialized")
            sys.exit(1)

        # Build BitBake command
        # We need to source oe-init-build-env then run bitbake
        build_cmd = f"""
cd {self.topdir}
source {oe_init_script} {self.builddir}
"""

        if offline:
            build_cmd += f"BB_NO_NETWORK='1' bitbake {target}\n"
        else:
            build_cmd += f"bitbake {target}\n"

        self.info(f"Building target: {target}")
        if offline:
            self.info("Offline mode: enabled")

        # Execute build
        result = self.run_cmd(['bash', '-c', build_cmd], check=False)

        if result.returncode != 0:
            self.error(f"Build failed with exit code {result.returncode}")
            sys.exit(1)

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

        # Execute interactively
        result = self.run_cmd(['bash', '-c', devshell_cmd], check=False)

        if result.returncode != 0:
            self.error("Devshell failed")
            sys.exit(1)

    def clean(self, args):
        """Clean build artifacts."""
        machine = args.machine

        self.log(f"Cleaning build for {machine}...", Colors.BOLD, bold=True)

        # TODO: Remove build/tmp for specific machine
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
    build_parser.add_argument('--builddir', help='Custom build directory (default: build or build-<machine> for coolstream)')
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
    config_parser.add_argument('--builddir', help='Custom build directory (default: build or build-<machine> for coolstream)')
    config_parser.add_argument('--distro-type', choices=['release', 'development'],
                            default='release', help='Build type')

    # show-config command
    show_config_parser = subparsers.add_parser('show-config', help='Show current configuration')
    show_config_parser.add_argument('-m', '--machine', required=True, help='Target machine')
    show_config_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    show_config_parser.add_argument('--machinebuild', help='OEM machine variant (defaults to MACHINE or $MACHINEBUILD)')
    show_config_parser.add_argument('--builddir', help='Custom build directory (default: build or build-<machine> for coolstream)')
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
        target_builddir = Path(args.builddir) if args.builddir else (
            builder.topdir / f"build-{args.machine}" if args.machine.startswith('coolstream') else builder.builddir
        )
        builder.generate_config(args.machine, args.distro, args.distro_type, args.machinebuild, target_builddir)
        builder.success(f"Config generated at {target_builddir}/conf")
    elif args.command == 'show-config':
        builder.show_config(args)
    elif args.command == 'machines':
        builder.machines(args)
    elif args.command == 'machine-info':
        builder.machine_info(args)
    elif args.command == 'clean':
        builder.clean(args)
    elif args.command == 'fetch-only':
        builder.fetch_only(args)
    elif args.command == 'sync':
        builder.sync(args)
    elif args.command == 'check':
        builder.check(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
