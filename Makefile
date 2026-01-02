# Tuxbox-OS Builder - Main Makefile
# Production-ready build orchestrator for Tuxbox-Neutrino
#
# Usage:
#   make image MACHINE=hd51              # Build image
#   make config MACHINE=hd51             # Generate config only
#   make show-config MACHINE=hd51        # Show configured values
#   make edit-conf MACHINE=hd51          # Edit build config files
#   make feeds MACHINE=hd51              # Build package feeds
#   make clean                           # Clean build (keeps sstate)
#   make list-machines                   # Show all supported machines
#   make help                            # Show this help

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_RED := \033[31m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

# Configuration
MACHINE ?= hd51
MACHINEBUILD ?= $(MACHINE)
DISTRO ?= tuxbox
DISTRO_TYPE ?= release
TOPDIR := $(CURDIR)
SYNC_EXCLUDE ?=
MACHINE_ORIGIN := $(origin MACHINE)
MACHINE_EXPLICIT := $(filter command line environment override,$(MACHINE_ORIGIN))
ifeq ($(MACHINE_EXPLICIT),)
  MACHINE_ARG :=
else
  MACHINE_ARG := --machine $(MACHINE)
endif
MACHINEBUILD_ORIGIN := $(origin MACHINEBUILD)
MACHINEBUILD_EXPLICIT := $(filter command line environment override,$(MACHINEBUILD_ORIGIN))
ifeq ($(MACHINEBUILD_EXPLICIT),)
  MACHINEBUILD_ARG :=
else
  MACHINEBUILD_ARG := --machinebuild $(MACHINEBUILD)
endif
MACHIME_ORIGIN := $(origin MACHIME)
MACHIME_EXPLICIT := $(filter command line,$(MACHIME_ORIGIN))
ifneq ($(MACHIME_EXPLICIT),)
  $(error Unknown variable MACHIME. Did you mean MACHINE=... ?)
endif
FORCE_CONFIG ?=
FORCE_CONFIG_ARG := $(if $(filter 1 yes true,$(FORCE_CONFIG)),--force-config,)
BB_TARGET ?= $(TARGET)
BB_TASK ?=
BB_ARGS ?=
BB_CMD = $(strip $(BB_ARGS) $(if $(BB_TASK),-c $(BB_TASK),) $(BB_TARGET))
DEVTOOL_ARGS ?= $(ARGS)

# Build directories
BUILDDIR := $(TOPDIR)/build
DL_DIR := $(TOPDIR)/downloads
SSTATE_DIR := $(TOPDIR)/sstate-cache
CONF_BUILDDIR = $(if $(filter coolstream%,$(MACHINE)),$(TOPDIR)/build-$(MACHINE),$(BUILDDIR))

# Sstate deployment (optional)
DEPLOY_CONFIG ?= $(TOPDIR)/.tuxbox/deploy.conf
# Optional include; missing file should not fail the build.
-include $(DEPLOY_CONFIG)
SSTATE_RSYNC_DEST ?=
SSTATE_RSYNC_OPTS ?= -a
SSTATE_RSYNC_SSH ?=
SSTATE_RSYNC_EXCLUDE ?=
SSTATE_RSYNC_EXCLUDE_ESC := $(subst ",\",$(SSTATE_RSYNC_EXCLUDE))
SSTATE_DEPLOY_DRYRUN ?= 1
SSTATE_DEPLOY_DELETE ?=
SSTATE_DEPLOY_SRC ?= $(SSTATE_DIR)
DL_RSYNC_DEST ?=
DL_RSYNC_OPTS ?= -a
DL_RSYNC_SSH ?=
DL_RSYNC_EXCLUDE ?= tmp cache *.done *.lock *.tmp
DL_RSYNC_EXCLUDE_ESC := $(subst ",\",$(DL_RSYNC_EXCLUDE))
DL_DEPLOY_DRYRUN ?= 1
DL_DEPLOY_DELETE ?=
DL_DEPLOY_SRC ?= $(DL_DIR)

# State tracking
STATE_FILE := $(TOPDIR)/.tuxbox/state.json

# Python CLI
CLI := $(TOPDIR)/cli.py

# Check if Python CLI is available
ifeq ($(wildcard $(CLI)),)
    USE_CLI := 0
else
    USE_CLI := 1
endif

.PHONY: help
help:
	@echo -e "$(COLOR_BOLD)Tuxbox-OS Builder$(COLOR_RESET)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Basic Commands:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make image MACHINE=hd51$(COLOR_RESET)              Build complete image"
	@echo -e "  $(COLOR_GREEN)make config MACHINE=hd51$(COLOR_RESET)             Generate config only"
	@echo -e "  $(COLOR_GREEN)make show-config MACHINE=hd51$(COLOR_RESET)        Show config + checks"
	@echo -e "  $(COLOR_GREEN)make edit-conf MACHINE=hd51$(COLOR_RESET)          Edit config files"
	@echo -e "  $(COLOR_GREEN)make feeds MACHINE=hd51$(COLOR_RESET)              Build package feeds"
	@echo -e "  $(COLOR_GREEN)make sdk MACHINE=hd51$(COLOR_RESET)                Build SDK for development"
	@echo ""
	@echo -e "$(COLOR_BOLD)Maintenance:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make clean$(COLOR_RESET)                           Clean build artifacts (keeps sstate)"
	@echo -e "  $(COLOR_GREEN)make distclean$(COLOR_RESET)                       Clean everything"
	@echo -e "  $(COLOR_GREEN)make deploy-sstate$(COLOR_RESET)                   Upload sstate cache (rsync)"
	@echo -e "  $(COLOR_GREEN)make deploy-downloads$(COLOR_RESET)                Upload downloads cache (rsync)"
	@echo -e "  $(COLOR_GREEN)make update$(COLOR_RESET)                          Update submodules"
	@echo -e "  $(COLOR_GREEN)make sync$(COLOR_RESET)                            Update repo + submodules (pinned)"
	@echo -e "  $(COLOR_GREEN)SYNC_EXCLUDE=meta-coolstream meta-tuxbox-toolchain$(COLOR_RESET)  Skip submodules in make sync"
	@echo ""
	@echo -e "$(COLOR_BOLD)Information:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make list-machines$(COLOR_RESET)                   List all supported machines"
	@echo -e "  $(COLOR_GREEN)make machine-info MACHINE=hd51$(COLOR_RESET)       Show machine details"
	@echo -e "  $(COLOR_GREEN)make check$(COLOR_RESET)                           Check system prerequisites"
	@echo ""
	@echo -e "$(COLOR_BOLD)Advanced (Python CLI):$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)./cli.py init$(COLOR_RESET)                        Initialize build environment"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51$(COLOR_RESET)               Build with Python CLI"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51 --offline$(COLOR_RESET)     Build offline"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51 --devshell$(COLOR_RESET)    Drop to devshell"
	@echo -e "  $(COLOR_GREEN)./cli.py --help$(COLOR_RESET)                      Show all CLI options"
	@echo ""
	@echo -e "$(COLOR_BOLD)BitBake wrappers:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make bb-ffmpeg$(COLOR_RESET)                      Run 'bitbake ffmpeg'"
	@echo -e "  $(COLOR_GREEN)make bb TARGET=ffmpeg BB_TASK=clean$(COLOR_RESET) Run 'bitbake -c clean ffmpeg'"
	@echo -e "  $(COLOR_GREEN)make bb BB_ARGS=\"-s\"$(COLOR_RESET)               Run 'bitbake -s'"
	@echo -e "  $(COLOR_GREEN)make devtool ARGS=\"modify freetype\"$(COLOR_RESET) Run 'devtool modify freetype'"
	@echo ""
	@echo -e "$(COLOR_BOLD)Variables:$(COLOR_RESET)"
	@echo -e "  MACHINE      Target hardware (default: hd51)"
	@echo -e "  MACHINEBUILD OEM variant (default: MACHINE)"
	@echo -e "  DISTRO       Distribution (default: tuxbox)"
	@echo -e "  DISTRO_TYPE  Build type: release|development (default: release)"
	@echo -e "  SSTATE_DEPLOY_SRC Source sstate dir for deploy-sstate (default: sstate-cache)"
	@echo -e "  SSTATE_RSYNC_EXCLUDE Exclude patterns (space/comma-separated)"
	@echo -e "  DL_DEPLOY_SRC Source downloads dir for deploy-downloads (default: downloads)"
	@echo -e "  DL_RSYNC_EXCLUDE Exclude patterns (default: tmp cache *.done *.lock *.tmp)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Examples:$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=hd60$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=zgemmah7 DISTRO_TYPE=development$(COLOR_RESET)"
	@echo ""

.PHONY: check
check:
	@echo -e "$(COLOR_BOLD)Checking system prerequisites...$(COLOR_RESET)"
ifeq ($(USE_CLI),1)
	@$(CLI) check
else
	@$(TOPDIR)/scripts/check-prerequisites.sh
endif

.PHONY: init
init: check
	@echo -e "$(COLOR_BOLD)Initializing Tuxbox-OS build environment...$(COLOR_RESET)"
ifeq ($(USE_CLI),1)
	@$(CLI) init $(MACHINE_ARG) $(MACHINEBUILD_ARG)
else
	@$(TOPDIR)/scripts/init.sh
endif

.PHONY: image
image: init
ifeq ($(MACHINE_EXPLICIT),)
	@echo -e "$(COLOR_BOLD)Building image using existing config...$(COLOR_RESET)"
else
	@echo -e "$(COLOR_BOLD)Building image for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
endif
ifeq ($(USE_CLI),1)
	@$(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: config
config: init
	@echo -e "$(COLOR_BOLD)Generating config for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: show-config
show-config:
	@echo -e "$(COLOR_BOLD)Showing config for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) show-config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: edit-conf
edit-conf:
	@echo -e "$(COLOR_BOLD)Editing config for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
	@conf_dir="$(CONF_BUILDDIR)/conf"; \
	local_conf="$$conf_dir/local.conf"; \
	bblayers_conf="$$conf_dir/bblayers.conf"; \
	local_user_conf="$$conf_dir/local.conf.user.inc"; \
	machine_conf="$$conf_dir/local.conf.$(MACHINE).inc"; \
	bblayers_user_conf="$$conf_dir/bblayers.conf.user.inc"; \
	if [[ ! -f "$$local_conf" || ! -f "$$bblayers_conf" ]]; then \
		echo -e "$(COLOR_RED)Config missing. Run 'make config MACHINE=$(MACHINE)' first.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -f "$$local_user_conf" ]]; then \
		printf "# Local overrides (not tracked)\n" > "$$local_user_conf"; \
	fi; \
	if [[ ! -f "$$machine_conf" ]]; then \
		printf "# Local overrides for MACHINE=$(MACHINE) (not tracked)\n" > "$$machine_conf"; \
	fi; \
	if [[ ! -f "$$bblayers_user_conf" ]]; then \
		printf "# Local layer overrides (not tracked)\n" > "$$bblayers_user_conf"; \
	fi; \
	editor="$${EDITOR:-$${VISUAL:-}}"; \
	if [[ -z "$$editor" ]]; then \
		if command -v nano >/dev/null 2>&1; then editor="nano"; \
		elif command -v vi >/dev/null 2>&1; then editor="vi"; \
		else \
			echo -e "$(COLOR_RED)No editor found. Set EDITOR or VISUAL.$(COLOR_RESET)"; \
			exit 1; \
		fi; \
	fi; \
	"$$editor" "$$local_conf" "$$bblayers_conf" "$$local_user_conf" "$$machine_conf" "$$bblayers_user_conf"

.PHONY: feeds
feeds: init
	@echo -e "$(COLOR_BOLD)Building package feeds for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) $(MACHINEBUILD_ARG) --target feeds $(FORCE_CONFIG_ARG)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: sdk
sdk: init
	@echo -e "$(COLOR_BOLD)Building SDK for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) $(MACHINEBUILD_ARG) --target sdk $(FORCE_CONFIG_ARG)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: devshell
devshell: init
	@echo -e "$(COLOR_BOLD)Starting development shell for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) $(MACHINEBUILD_ARG) --devshell $(FORCE_CONFIG_ARG)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: bb
bb: init
	@echo -e "$(COLOR_BOLD)Running BitBake...$(COLOR_RESET)"
	@if [[ -z "$(BB_CMD)" ]]; then \
		echo -e "$(COLOR_RED)Missing BitBake args. Use 'make bb-<target>' or set BB_ARGS/BB_TASK/BB_TARGET.$(COLOR_RESET)"; \
		exit 1; \
	fi
ifeq ($(USE_CLI),1)
	@$(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG) --target "$(BB_CMD)"
else
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

bb-%:
	@$(MAKE) bb BB_TARGET=$*

.PHONY: devtool
devtool: init
	@echo -e "$(COLOR_BOLD)Running devtool...$(COLOR_RESET)"
	@if [[ -z "$(DEVTOOL_ARGS)" ]]; then \
		echo -e "$(COLOR_RED)Missing devtool args. Use 'make devtool ARGS=\"modify freetype\"'.$(COLOR_RESET)"; \
		exit 1; \
	fi
	@conf_dir="$(CONF_BUILDDIR)/conf"; \
	local_conf="$$conf_dir/local.conf"; \
	bblayers_conf="$$conf_dir/bblayers.conf"; \
	if [[ ! -f "$$local_conf" || ! -f "$$bblayers_conf" ]]; then \
		echo -e "$(COLOR_RED)Config missing. Run 'make config MACHINE=$(MACHINE)' first.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	if [[ ! -f "$$oe_init" ]]; then \
		echo -e "$(COLOR_RED)OE init script not found: $$oe_init$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	bash -c "source $$oe_init $(CONF_BUILDDIR) >/dev/null && devtool $(DEVTOOL_ARGS)"

.PHONY: deploy-sstate
deploy-sstate:
	@echo -e "$(COLOR_BOLD)Deploying sstate cache...$(COLOR_RESET)"
	@if [[ -z "$(SSTATE_RSYNC_DEST)" ]]; then \
		echo -e "$(COLOR_RED)Missing SSTATE_RSYNC_DEST.$(COLOR_RESET)"; \
		echo -e "Set it in $(DEPLOY_CONFIG) or pass it on the command line:"; \
		echo -e "  make deploy-sstate SSTATE_RSYNC_DEST=user@host:/path/to/sstate"; \
		exit 1; \
	fi
	@if ! command -v rsync >/dev/null 2>&1; then \
		echo -e "$(COLOR_RED)rsync not found. Install rsync and try again.$(COLOR_RESET)"; \
		exit 1; \
	fi
	@if [[ ! -d "$(SSTATE_DEPLOY_SRC)" ]]; then \
		echo -e "$(COLOR_RED)Sstate source not found: $(SSTATE_DEPLOY_SRC)$(COLOR_RESET)"; \
		exit 1; \
	fi
	@rsync_opts=($(SSTATE_RSYNC_OPTS)); \
	if [[ "$(SSTATE_DEPLOY_DELETE)" =~ ^(1|yes|true)$$ ]]; then rsync_opts+=("--delete"); fi; \
	if [[ "$(SSTATE_DEPLOY_DRYRUN)" =~ ^(1|yes|true)$$ ]]; then rsync_opts+=("--dry-run"); fi; \
	if [[ -n "$(SSTATE_RSYNC_SSH)" ]]; then rsync_opts+=("-e" "$(SSTATE_RSYNC_SSH)"); fi; \
	excludes_raw="$(SSTATE_RSYNC_EXCLUDE_ESC)"; \
	excludes_raw="$${excludes_raw//\"/}"; \
	excludes_raw="$${excludes_raw//\'/}"; \
	if [[ -n "$$excludes_raw" ]]; then \
		excludes=($${excludes_raw//,/ }); \
		for ex in "$${excludes[@]}"; do \
			[[ -n "$$ex" ]] && rsync_opts+=("--exclude=$$ex"); \
		done; \
	fi; \
	dest="$(SSTATE_RSYNC_DEST)"; \
	dest="$${dest%/}/"; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) rsync $${rsync_opts[*]} \"$(SSTATE_DEPLOY_SRC)/\" \"$$dest\""; \
	rsync "$${rsync_opts[@]}" "$(SSTATE_DEPLOY_SRC)/" "$$dest"

.PHONY: deploy-downloads
deploy-downloads:
	@echo -e "$(COLOR_BOLD)Deploying downloads cache...$(COLOR_RESET)"
	@if [[ -z "$(DL_RSYNC_DEST)" ]]; then \
		echo -e "$(COLOR_RED)Missing DL_RSYNC_DEST.$(COLOR_RESET)"; \
		echo -e "Set it in $(DEPLOY_CONFIG) or pass it on the command line:"; \
		echo -e "  make deploy-downloads DL_RSYNC_DEST=user@host:/path/to/downloads"; \
		exit 1; \
	fi
	@if ! command -v rsync >/dev/null 2>&1; then \
		echo -e "$(COLOR_RED)rsync not found. Install rsync and try again.$(COLOR_RESET)"; \
		exit 1; \
	fi
	@if [[ ! -d "$(DL_DEPLOY_SRC)" ]]; then \
		echo -e "$(COLOR_RED)Downloads source not found: $(DL_DEPLOY_SRC)$(COLOR_RESET)"; \
		exit 1; \
	fi
	@rsync_opts=($(DL_RSYNC_OPTS)); \
	if [[ "$(DL_DEPLOY_DELETE)" =~ ^(1|yes|true)$$ ]]; then rsync_opts+=("--delete"); fi; \
	if [[ "$(DL_DEPLOY_DRYRUN)" =~ ^(1|yes|true)$$ ]]; then rsync_opts+=("--dry-run"); fi; \
	if [[ -n "$(DL_RSYNC_SSH)" ]]; then rsync_opts+=("-e" "$(DL_RSYNC_SSH)"); fi; \
	excludes_raw="$(DL_RSYNC_EXCLUDE_ESC)"; \
	excludes_raw="$${excludes_raw//\"/}"; \
	excludes_raw="$${excludes_raw//\'/}"; \
	if [[ -n "$$excludes_raw" ]]; then \
		excludes=($${excludes_raw//,/ }); \
		for ex in "$${excludes[@]}"; do \
			[[ -n "$$ex" ]] && rsync_opts+=("--exclude=$$ex"); \
		done; \
	fi; \
	dest="$(DL_RSYNC_DEST)"; \
	dest="$${dest%/}/"; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) rsync $${rsync_opts[*]} \"$(DL_DEPLOY_SRC)/\" \"$$dest\""; \
	rsync "$${rsync_opts[@]}" "$(DL_DEPLOY_SRC)/" "$$dest"

.PHONY: clean
clean:
	@echo -e "$(COLOR_BOLD)Cleaning build artifacts (keeping sstate-cache)...$(COLOR_RESET)"
	@rm -rf $(BUILDDIR)/tmp
	@echo -e "$(COLOR_GREEN)Build artifacts cleaned.$(COLOR_RESET)"

.PHONY: distclean
distclean:
	@echo -e "$(COLOR_BOLD)$(COLOR_RED)Warning: This will delete all builds and caches!$(COLOR_RESET)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(BUILDDIR) $(SSTATE_DIR) $(DL_DIR); \
		rm -f $(STATE_FILE); \
		echo -e "$(COLOR_GREEN)Everything cleaned.$(COLOR_RESET)"; \
	else \
		echo -e "$(COLOR_YELLOW)Cancelled.$(COLOR_RESET)"; \
	fi

.PHONY: update
update:
	@echo -e "$(COLOR_BOLD)Updating submodules...$(COLOR_RESET)"
	@git submodule update --remote --recursive
	@echo -e "$(COLOR_GREEN)Submodules updated.$(COLOR_RESET)"

.PHONY: sync
sync:
	@echo -e "$(COLOR_BOLD)Updating repository...$(COLOR_RESET)"
	@git pull --ff-only
	@echo -e "$(COLOR_BOLD)Updating submodules (pinned)...$(COLOR_RESET)"
	@if [[ -z "$(SYNC_EXCLUDE)" ]]; then \
		git submodule update --init --recursive; \
	else \
		excludes_raw="$(SYNC_EXCLUDE)"; \
		excludes=($${excludes_raw//,/ }); \
		while read -r _ path; do \
			skip=0; \
			for ex in "$${excludes[@]}"; do \
				if [[ "$$path" == "$$ex" ]]; then skip=1; break; fi; \
			done; \
			if [[ $$skip -eq 1 ]]; then \
				echo -e "$(COLOR_YELLOW)Skipping submodule: $$path$(COLOR_RESET)"; \
				continue; \
			fi; \
			git submodule update --init --recursive "$$path"; \
		done < <(git config -f .gitmodules --get-regexp path); \
	fi
	@echo -e "$(COLOR_GREEN)Repository and submodules updated.$(COLOR_RESET)"

.PHONY: list-machines
list-machines:
	@echo -e "$(COLOR_BOLD)Supported machines (from OE-Alliance):$(COLOR_RESET)"
ifeq ($(USE_CLI),1)
	@$(CLI) machines --with-builds
else
	@echo ""
	@echo -e "$(COLOR_BOLD)Priority platforms (tested):$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)GFutures:$(COLOR_RESET)   hd51, hd60, hd61"
	@echo -e "  $(COLOR_GREEN)AirDigital:$(COLOR_RESET) zgemmah7, h7s, h7c"
	@echo -e "  $(COLOR_GREEN)Coolstream:$(COLOR_RESET) tank (uClibc)"
	@echo ""
	@echo -e "$(COLOR_YELLOW)For complete list, init submodules and use ./cli.py machines.$(COLOR_RESET)"
	@echo ""
endif

.PHONY: machine-info
machine-info:
	@echo -e "$(COLOR_BOLD)Machine info for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET):"
	@$(TOPDIR)/scripts/machine-info.sh $(MACHINE)

.PHONY: test
test:
	@echo -e "$(COLOR_BOLD)Running tests...$(COLOR_RESET)"
	@pytest tests/ -v

# Special target for CI
.PHONY: ci-build
ci-build: init
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --ci-mode

.PHONY: version
version:
	@echo "Tuxbox-OS Builder v1.0.0"
	@echo "Yocto: Kirkstone (4.0 LTS)"
	@echo "Python: $$(python3 --version)"
	@echo "Git: $$(git --version)"
