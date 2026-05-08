#!/bin/bash
#
# Check system prerequisites for Tuxbox-OS builds
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Checking System Prerequisites ===${NC}\n"

# Required commands
REQUIRED_CMDS=(
    git
    gcc
    g++
    make
    python3
    patch
    diffstat
    tar
    gzip
    bzip2
    xz
    lz4
    unzip
    wget
    curl
    luajit
    chrpath
    cpio
    file
)

MISSING=()
CHECK_FAILED=0

for cmd in "${REQUIRED_CMDS[@]}"; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING+=("$cmd")
    fi
done

if [ ${#MISSING[@]} -ne 0 ]; then
    echo -e "${RED}Missing required tools:${NC}"
    printf '  %s\n' "${MISSING[@]}"
    echo ""
    echo -e "${YELLOW}Install on Debian/Ubuntu:${NC}"
    echo "sudo apt install -y gawk wget git diffstat unzip texinfo \\"
    echo "  gcc g++ build-essential chrpath socat cpio python3 python3-pip \\"
    echo "  python3-pexpect xz-utils debianutils iputils-ping python3-git \\"
    echo "  python3-jinja2 python3-subunit zstd lz4 file locales libacl1 curl luajit"
    CHECK_FAILED=1
else
    echo -e "${GREEN}✓ All required tools found${NC}"
fi

if [ "$(uname -m)" = "x86_64" ] && command -v gcc >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1; then
    TMPDIR_CHECK=$(mktemp -d)
    trap 'rm -rf "$TMPDIR_CHECK"' EXIT
    printf 'int main(void) { return 0; }\n' > "$TMPDIR_CHECK/test.c"
    printf 'int main() { return 0; }\n' > "$TMPDIR_CHECK/test.cpp"
    if ! gcc -m32 "$TMPDIR_CHECK/test.c" -o "$TMPDIR_CHECK/gcc-m32-test" >/dev/null 2>&1 ||
       ! g++ -m32 "$TMPDIR_CHECK/test.cpp" -o "$TMPDIR_CHECK/gxx-m32-test" >/dev/null 2>&1; then
        echo -e "${RED}Missing 32-bit compiler/multilib support (gcc/g++ -m32)${NC}"
        echo ""
        echo -e "${YELLOW}Install on Debian/Ubuntu:${NC}"
        echo "sudo apt install -y gcc-multilib g++-multilib libc6-dev-i386"
        CHECK_FAILED=1
    else
        echo -e "${GREEN}✓ 32-bit compiler/multilib support OK${NC}"
    fi
fi

if [ "$CHECK_FAILED" -ne 0 ]; then
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 6 ]; }; then
    echo -e "${RED}Python 3.6+ required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION OK${NC}"

# Check disk space
AVAILABLE_GB=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')

if [ "$AVAILABLE_GB" -lt 100 ]; then
    echo -e "${YELLOW}⚠ Only ${AVAILABLE_GB}GB free space. Recommended: 100GB+${NC}"
else
    echo -e "${GREEN}✓ Disk space OK: ${AVAILABLE_GB}GB free${NC}"
fi

# Check locale
if ! locale -a | grep -qi en_US.utf8; then
    echo -e "${YELLOW}⚠ en_US.UTF-8 locale not found. May cause build issues.${NC}"
    echo "  Generate with: sudo dpkg-reconfigure locales"
else
    echo -e "${GREEN}✓ Locale OK${NC}"
fi

echo ""
echo -e "${GREEN}System ready for building!${NC}"
