#!/bin/bash
#
# Display information about a specific machine
#

MACHINE="$1"

if [ -z "$MACHINE" ]; then
    echo "Usage: $0 <machine>"
    echo "Example: $0 hd51"
    exit 1
fi

# Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}=== Machine Information: ${CYAN}${MACHINE}${NC} ${BOLD}===${NC}\n"

# Known machine details (hardcoded for now, will be read from OE-Alliance later)
case "$MACHINE" in
    hd51)
        echo -e "${BOLD}Manufacturer:${NC} Gigablue"
        echo -e "${BOLD}Model:${NC} HD51"
        echo -e "${BOLD}CPU:${NC} BCM7251S (ARM Cortex-A15, Dual-core 1.5GHz)"
        echo -e "${BOLD}RAM:${NC} 2GB DDR3"
        echo -e "${BOLD}Flash:${NC} 8GB eMMC"
        echo -e "${BOLD}Tuners:${NC} 2x DVB-S2X"
        echo -e "${BOLD}Features:${NC} HDMI 2.0, CI, Transcoding, LCD display"
        echo -e "${BOLD}Status:${NC} ${GREEN}Fully supported${NC}"
        ;;
    hd60|hd61)
        echo -e "${BOLD}Manufacturer:${NC} Gigablue"
        echo -e "${BOLD}Model:${NC} ${MACHINE^^}"
        echo -e "${BOLD}CPU:${NC} BCM7252S (ARM Cortex-A15, Dual-core 1.5GHz)"
        echo -e "${BOLD}RAM:${NC} 2GB DDR4"
        echo -e "${BOLD}Flash:${NC} 8GB eMMC"
        echo -e "${BOLD}Tuners:${NC} 2x DVB-S2X (hd60), 1x DVB-S2X (hd61)"
        echo -e "${BOLD}Features:${NC} HDMI 2.0, CI, Transcoding, UHD support"
        echo -e "${BOLD}Status:${NC} ${GREEN}Fully supported${NC}"
        ;;
    zgemmah7)
        echo -e "${BOLD}Manufacturer:${NC} AirDigital (Zgemma)"
        echo -e "${BOLD}Model:${NC} H7"
        echo -e "${BOLD}CPU:${NC} BCM7251S (ARM Cortex-A15)"
        echo -e "${BOLD}RAM:${NC} 2GB"
        echo -e "${BOLD}Flash:${NC} 16GB eMMC"
        echo -e "${BOLD}Tuners:${NC} 2x DVB-S2X"
        echo -e "${BOLD}Features:${NC} HDMI, CI, LCD display"
        echo -e "${BOLD}Status:${NC} ${GREEN}Fully supported${NC}"
        ;;
    tank)
        echo -e "${BOLD}Manufacturer:${NC} Coolstream"
        echo -e "${BOLD}Model:${NC} Tank"
        echo -e "${BOLD}CPU:${NC} ARM Cortex-A9"
        echo -e "${BOLD}Toolchain:${NC} ${YELLOW}External uClibc toolchain required${NC}"
        echo -e "${BOLD}Notes:${NC} Requires meta-tuxbox-toolchain layer"
        echo -e "${BOLD}Status:${NC} ${GREEN}Supported (special build)${NC}"
        ;;
    *)
        echo -e "${YELLOW}Machine '${MACHINE}' not in detailed database.${NC}"
        echo ""
        echo "This machine may still be supported via OE-Alliance."
        echo "Check: oe-alliance/meta-brands/meta-*/conf/machine/${MACHINE}.conf"
        echo ""
        echo -e "${BOLD}Common machine types:${NC}"
        echo "  Gigablue: hd51, hd60, hd61, uhd4k"
        echo "  AirDigital: zgemmah7, h7s, h7c, i55plus"
        echo "  Vu+: ultimo4k, uno4k, uno4kse, duo4k"
        echo "  Coolstream: tank"
        ;;
esac

echo ""
