# meta-local - User Customization Layer

This layer is for your local customizations and overrides.

## Purpose

- Add custom recipes (.bb files)
- Override existing recipes (.bbappend files)
- Add machine-specific configurations
- Test new features before integrating into meta-tuxbox

## Priority

Layer priority: **15** (highest in the stack)

This means recipes and configuration here take precedence over:
- meta-tuxbox (priority 10)
- meta-neutrino (priority 10)
- OE-Alliance layers (priority 7-9)
- meta-openembedded (priority 6)

## Usage

### Adding a custom recipe

```bash
# Create recipe directory
mkdir -p meta-local/recipes-example/myapp

# Add recipe
cat > meta-local/recipes-example/myapp/myapp_1.0.bb <<EOF
DESCRIPTION = "My custom application"
LICENSE = "MIT"

SRC_URI = "file://myapp.c"

do_compile() {
    ${CC} ${CFLAGS} ${LDFLAGS} ${WORKDIR}/myapp.c -o myapp
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 myapp ${D}${bindir}/
}
EOF
```

### Adding a bbappend

```bash
# Override Neutrino settings
cat > meta-local/recipes-neutrino/neutrino/neutrino_git.bbappend <<EOF
# Enable debug build
EXTRA_OECONF += "--enable-debug"
EOF
```

## Git

This layer is intentionally excluded from git (in .gitignore).

Your customizations remain local and won't be committed to the main repository.

If you want to version control your customizations:

```bash
cd meta-local
git init
git add .
git commit -m "Initial meta-local customizations"
```
