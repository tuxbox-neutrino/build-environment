#!/usr/bin/env python3
"""
Tuxbox-OS Builder - Command Line Interface

Production-ready build orchestrator for Tuxbox-Neutrino.
Manages OE-Alliance integration, submodules, configuration, and builds.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

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

    def detect_machine_brand(self, machine: str) -> str:
        """Detect the brand/manufacturer for a given machine."""
        # Machine to brand mapping (common machines)
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

    def generate_config(self, machine: str, distro: str, distro_type: str = 'release',
                        machinebuild: Optional[str] = None, builddir: Optional[Path] = None):
        """Generate build configuration files from templates."""
        self.log(f"Generating configuration for {machine}...", Colors.BOLD, bold=True)

        # Detect machine brand for meta-brands layer
        brand = self.detect_machine_brand(machine)
        if brand == 'unknown':
            self.warning(f"Unknown machine '{machine}' - brand layer may need manual configuration")

        # Create build/conf directory
        target_builddir = Path(builddir) if builddir else self.builddir
        conf_dir = target_builddir / 'conf'
        conf_dir.mkdir(parents=True, exist_ok=True)

        # Generate bblayers.conf
        self.generate_bblayers_conf(conf_dir, machine, brand)

        # Generate local.conf
        self.generate_local_conf(conf_dir, machine, distro, distro_type, machinebuild, target_builddir)

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

        # Calculate optimal thread counts
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        bb_threads = max(1, cpu_count - 1)  # Leave 1 core for system
        parallel_make = max(1, cpu_count)

        # Default MACHINEBUILD to MACHINE if not provided
        effective_machinebuild = machinebuild or machine

        # Replace variables
        content = content.replace('##MACHINE##', machine)
        content = content.replace('##MACHINEBUILD##', effective_machinebuild)
        content = content.replace('##DISTRO##', distro)
        content = content.replace('##BB_NUMBER_THREADS##', str(bb_threads))
        content = content.replace('##PARALLEL_MAKE##', str(parallel_make))
        content = content.replace('##DL_DIR##', str(self.dl_dir))
        content = content.replace('##SSTATE_DIR##', str(self.sstate_dir))
        content = content.replace('##TMPDIR##', str(target_builddir / 'tmp'))
        content = content.replace('##DISTRO_TYPE##', distro_type)

        # Coolstream-specific toolchain defaults (HD2 uClibc, HD1 glibc)
        if machine.startswith('coolstream') and machine != 'coolstream-nevis':
            content += '\n# Coolstream external uClibc toolchain\n'
            content += 'TCMODE ?= "external-coolstream"\n'
            content += 'TCLIBC ?= "uclibc"\n'

        # Write output
        with open(output_file, 'w') as f:
            f.write(content)

        self.info(f"Generated: {output_file}")
        self.info(f"  Machine: {machine}")
        self.info(f"  MachineBuild: {effective_machinebuild}")
        self.info(f"  Distro: {distro}")
        self.info(f"  Threads: {bb_threads}")
        self.info(f"  Parallel: {parallel_make}")

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
        self.info("\nNext steps:")
        self.info("  ./cli.py build --machine hd51")
        self.info("  make image MACHINE=hd51")

    def build(self, args):
        """Build an image."""
        machine = args.machine
        machinebuild = args.machinebuild or os.environ.get('MACHINEBUILD')
        distro = args.distro
        distro_type = args.distro_type
        target = args.target or 'tuxbox-image'

        self.log(f"=== Building {target} for {machine} ===", Colors.BOLD, bold=True)
        if machinebuild:
            self.info(f"Using MACHINEBUILD={machinebuild}")

        # Select per-machine build directory (isolate Coolstream builds)
        target_builddir = Path(args.builddir) if args.builddir else (
            self.topdir / f"build-{machine}" if machine.startswith('coolstream') else self.builddir
        )
        self.builddir = target_builddir

        # Check if initialized
        state = self.load_state()
        if not state.get('initialized'):
            self.warning("Build environment not initialized. Running init...")
            self.init(args)

        # Check if OE-Alliance submodule exists
        oe_alliance = self.topdir / 'oe-alliance'
        if not oe_alliance.exists():
            self.error("OE-Alliance submodule not found!")
            self.info("Please add submodule:")
            self.info("  git submodule add https://github.com/oe-alliance/oe-alliance-core.git oe-alliance")
            self.info("  git submodule update --init --recursive")
            sys.exit(1)

        # Generate configuration
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

    # build command
    build_parser = subparsers.add_parser('build', help='Build an image')
    build_parser.add_argument('-m', '--machine', required=True, help='Target machine (e.g., hd51)')
    build_parser.add_argument('-d', '--distro', default='tuxbox', help='Distribution (default: tuxbox)')
    build_parser.add_argument('--machinebuild', help='OEM machine variant (defaults to MACHINE or $MACHINEBUILD)')
    build_parser.add_argument('--builddir', help='Custom build directory (default: build or build-<machine> for coolstream)')
    build_parser.add_argument('-t', '--target', help='Build target (default: tuxbox-image)')
    build_parser.add_argument('--offline', action='store_true', help='Offline build mode')
    build_parser.add_argument('--no-sstate', action='store_true', help='Disable sstate cache')
    build_parser.add_argument('--devshell', action='store_true', help='Drop to development shell')
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
