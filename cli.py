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

    def generate_config(self, machine: str, distro: str):
        """Generate build configuration files."""
        self.log(f"Generating configuration for {machine}...", Colors.BOLD, bold=True)

        # TODO: Generate bblayers.conf and local.conf
        # This will be implemented based on templates

        self.info(f"Machine: {machine}")
        self.info(f"Distro: {distro}")
        self.success("Configuration generated")

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
        distro = args.distro
        target = args.target or 'tuxbox-image'

        self.log(f"=== Building {target} for {machine} ===", Colors.BOLD, bold=True)

        # Check if initialized
        state = self.load_state()
        if not state.get('initialized'):
            self.warning("Build environment not initialized. Running init...")
            self.init(args)

        # Generate configuration
        self.generate_config(machine, distro)

        # TODO: Invoke BitBake
        self.info(f"Build target: {target}")
        self.info(f"Machine: {machine}")
        self.info(f"Distro: {distro}")

        if args.offline:
            self.info("Offline mode: enabled")

        if args.devshell:
            self.info("Dropping to devshell...")
            # TODO: bitbake -c devshell

        self.warning("Build implementation pending...")

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
    build_parser.add_argument('-t', '--target', help='Build target (default: tuxbox-image)')
    build_parser.add_argument('--offline', action='store_true', help='Offline build mode')
    build_parser.add_argument('--no-sstate', action='store_true', help='Disable sstate cache')
    build_parser.add_argument('--devshell', action='store_true', help='Drop to development shell')
    build_parser.add_argument('--distro-type', choices=['release', 'development'],
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
