#!/bin/bash
# Fix tune-include paths for Kirkstone (tune files reorganized into subdirs)

set -e

LAYER_PATH="${1:-oe-alliance/meta-brands}"

echo "Fixing tune-include paths in $LAYER_PATH..."

# Update tune file paths to new Kirkstone structure
find "$LAYER_PATH" -type f \( -name "*.conf" -o -name "*.inc" \) -print0 | \
  xargs -0 sed -i \
    -e 's|conf/machine/include/tune-cortexa15\.inc|conf/machine/include/arm/armv7a/tune-cortexa15.inc|g' \
    -e 's|conf/machine/include/tune-cortexa5\.inc|conf/machine/include/arm/armv7a/tune-cortexa5.inc|g' \
    -e 's|conf/machine/include/tune-mips32\.inc|conf/machine/include/mips/tune-mips32.inc|g' \
    -e 's|conf/machine/include/tune-sh4\.inc|conf/machine/include/sh/tune-sh4.inc|g'

# Verify
REMAINING=$(grep -r "require conf/machine/include/tune-" "$LAYER_PATH" 2>/dev/null | grep -v "arm/\|mips/\|sh/" | wc -l || echo 0)

echo "Tune paths fixed!"
echo "Remaining old-style paths: $REMAINING"

if [ "$REMAINING" -gt 0 ]; then
  echo "Files still with old paths:"
  grep -r "require conf/machine/include/tune-" "$LAYER_PATH" 2>/dev/null | grep -v "arm/\|mips/\|sh/" || true
fi
