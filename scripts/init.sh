#!/bin/bash
#
# Initialize Tuxbox-OS build environment
#

set -e

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TOPDIR"

# Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}=== Tuxbox-OS Build Environment Initialization ===${NC}\n"

# Check prerequisites
if [ -f "$TOPDIR/scripts/check-prerequisites.sh" ]; then
    bash "$TOPDIR/scripts/check-prerequisites.sh" || exit 1
    echo ""
fi

# Check for .gitmodules
if [ ! -f "$TOPDIR/.gitmodules" ]; then
    echo -e "${YELLOW}No .gitmodules found. Creating stub...${NC}"
    cat > "$TOPDIR/.gitmodules" << 'EOF'
# Git Submodules for Tuxbox-OS Builder
#
# Add submodules manually:
#   git submodule add <URL> <path>
#
# Recommended submodules:
#   git submodule add https://github.com/oe-alliance/oe-alliance-core.git oe-alliance
#   git submodule add https://github.com/tuxbox-neutrino/meta-neutrino.git meta-neutrino
#
# Then run: git submodule update --init --recursive
EOF
    echo -e "${GREEN}Created .gitmodules stub${NC}"
    echo "Please add submodules and run init again."
    exit 0
fi

# Initialize submodules
echo "Initializing git submodules..."
git submodule init
git submodule update --recursive

# Create build directories
mkdir -p "$TOPDIR/build"
mkdir -p "$TOPDIR/downloads"
mkdir -p "$TOPDIR/sstate-cache"
mkdir -p "$TOPDIR/.tuxbox"

# Create state file
cat > "$TOPDIR/.tuxbox/state.json" << EOF
{
  "initialized": true,
  "version": "1.0.0",
  "timestamp": "$(date -Iseconds)"
}
EOF

echo ""
echo -e "${GREEN}✓ Build environment initialized successfully!${NC}"
echo ""
echo "Next steps:"
EXAMPLE_MACHINE="${MACHINE:-}"
EXAMPLE_MACHINEBUILD="${MACHINEBUILD:-}"
if [ -n "$EXAMPLE_MACHINE" ]; then
  if [ -n "$EXAMPLE_MACHINEBUILD" ] && [ "$EXAMPLE_MACHINEBUILD" != "$EXAMPLE_MACHINE" ]; then
    echo "  ./cli.py build --machine ${EXAMPLE_MACHINE} --machinebuild ${EXAMPLE_MACHINEBUILD}"
    echo "  make image MACHINE=${EXAMPLE_MACHINE} MACHINEBUILD=${EXAMPLE_MACHINEBUILD} (MACHINEBUILD defaults to MACHINE)"
  else
    echo "  ./cli.py build --machine ${EXAMPLE_MACHINE}"
    echo "  make image MACHINE=${EXAMPLE_MACHINE} (MACHINEBUILD defaults to MACHINE)"
  fi
else
  echo "  ./cli.py build --machine hd51  # example"
  echo "  make image MACHINE=hd51  # example"
fi
echo "  make list-machines"
