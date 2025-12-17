#!/bin/bash
# Convert Gatesgarth override syntax to Kirkstone
# Based on Yocto convert-overrides.py logic

set -e

LAYER_PATH="${1:-meta-neutrino}"

echo "Converting override syntax in $LAYER_PATH..."
echo "This converts underscore syntax to colon syntax for Kirkstone compatibility"
echo ""

# File extensions to process
FILE_PATTERNS="*.bb *.bbappend *.inc *.bbclass *.conf"

# Counter
CONVERTED=0

# Find all files and convert
for pattern in $FILE_PATTERNS; do
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            echo "Processing: $file"

            # Create backup
            cp "$file" "$file.bak"

            # Perform conversions:
            # 1. _append -> :append
            # 2. _prepend -> :prepend
            # 3. _remove -> :remove
            # 4. _pn- -> :pn-
            # 5. _class- -> :class-
            # 6. _task- -> :task-
            # 7. _forcevariable -> :forcevariable
            # 8. _libc- -> :libc-
            # 9. _arch- -> :arch-

            sed -i -E \
                -e 's/([A-Za-z0-9_]+)_append([^a-zA-Z0-9_]|$)/\1:append\2/g' \
                -e 's/([A-Za-z0-9_]+)_prepend([^a-zA-Z0-9_]|$)/\1:prepend\2/g' \
                -e 's/([A-Za-z0-9_]+)_remove([^a-zA-Z0-9_]|$)/\1:remove\2/g' \
                -e 's/([A-Za-z0-9_]+)_pn-/\1:pn-/g' \
                -e 's/([A-Za-z0-9_]+)_class-/\1:class-/g' \
                -e 's/([A-Za-z0-9_]+)_task-/\1:task-/g' \
                -e 's/([A-Za-z0-9_]+)_forcevariable([^a-zA-Z0-9_]|$)/\1:forcevariable\2/g' \
                -e 's/([A-Za-z0-9_]+)_libc-/\1:libc-/g' \
                -e 's/([A-Za-z0-9_]+)_arch-/\1:arch-/g' \
                "$file"

            # Check if file changed
            if ! diff -q "$file" "$file.bak" > /dev/null 2>&1; then
                CONVERTED=$((CONVERTED + 1))
                echo "  ✓ Converted"
            else
                echo "  - No changes needed"
            fi

            # Remove backup
            rm "$file.bak"
        fi
    done < <(find "$LAYER_PATH" -name "$pattern" -type f 2>/dev/null)
done

echo ""
echo "==================================="
echo "Conversion complete!"
echo "Files converted: $CONVERTED"
echo "==================================="
