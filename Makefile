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
FORCE_INIT ?=
BB_TARGET ?= $(TARGET)
BB_TASK ?=
BB_ARGS ?=
BB_CMD = $(strip $(BB_ARGS) $(if $(BB_TASK),-c $(BB_TASK),) $(BB_TARGET))
DEVTOOL_ARGS ?= $(ARGS)
QEMU_MACHINE ?= qemux86-64
QEMU_IMAGE ?= tuxbox-qemu-image
QEMU_ARGS ?=
QEMU_BUILD_DIR ?= $(BUILDDIR)

# Build directories
DEFAULT_BUILDDIR := $(TOPDIR)/builds
ifneq ($(wildcard $(TOPDIR)/builds/conf/local.conf),)
DEFAULT_BUILDDIR := $(TOPDIR)/builds
else ifneq ($(wildcard $(TOPDIR)/build/conf/local.conf),)
DEFAULT_BUILDDIR := $(TOPDIR)/build
else ifneq ($(wildcard $(TOPDIR)/builds),)
DEFAULT_BUILDDIR := $(TOPDIR)/builds
endif
BUILDDIR := $(DEFAULT_BUILDDIR)
DL_DIR := $(TOPDIR)/downloads
SSTATE_DIR := $(TOPDIR)/sstate-cache
CONF_BUILDDIR = $(if $(filter coolstream%,$(MACHINE)),$(TOPDIR)/build-$(MACHINE),$(BUILDDIR))
TOASTER_BUILD_DIR ?= $(CONF_BUILDDIR)
TOASTER_DIR ?= $(TOPDIR)/.tuxbox/toaster
TOASTER_VENV ?= $(TOPDIR)/.tuxbox/toaster-venv
TOASTER_PYTHON ?= python3
TOASTER_WEBPORT ?= localhost:8000
TOASTER_START_ARGS ?=
TOASTER_SESSION_PID ?= $(TOASTER_BUILD_DIR)/.toaster-session.pid
TOASTER_SESSION_LOG ?= $(TOASTER_BUILD_DIR)/toaster_session.log
TOASTER_ADMIN_USERNAME ?=
TOASTER_ADMIN_EMAIL ?=
TOASTER_ADMIN_PASSWORD ?=
TOASTER_IMPORT_NAME ?= $(DISTRO)-build
TOASTER_IMPORT_PATH ?= $(TOASTER_BUILD_DIR)
TOASTER_IMPORT_CALLBACK ?=
TOASTER_LAST_PROJECT_FILE ?= $(TOASTER_DIR)/.last-imported-project-id

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
	@echo -e "  $(COLOR_GREEN)make qemu-run$(COLOR_RESET)                         Run QEMU (qemux86-64)"
	@echo -e "  $(COLOR_GREEN)make qemu-smoke$(COLOR_RESET)                       Run QEMU smoke test (needs QEMU running)"
	@echo -e "  $(COLOR_GREEN)make stb-smoke MACHINE=qemux86-64$(COLOR_RESET)     Run stb-* plugin unpack/install smoke checks"
	@echo -e "  $(COLOR_GREEN)make flash-preflight-smoke$(COLOR_RESET)            Run flash backend preflight smoke check"
	@echo -e "  $(COLOR_GREEN)make init-toaster$(COLOR_RESET)                     Setup Toaster venv + DB"
	@echo -e "  $(COLOR_GREEN)make toaster-start$(COLOR_RESET)                    Start Toaster web UI"
	@echo -e "  $(COLOR_GREEN)make toaster-stop$(COLOR_RESET)                     Stop Toaster web UI"
	@echo -e "  $(COLOR_GREEN)make toaster-create-admin$(COLOR_RESET)             Create Toaster admin user"
	@echo -e "  $(COLOR_GREEN)make toaster-import-build$(COLOR_RESET)             Import existing build dir into Toaster"
	@echo -e "  $(COLOR_GREEN)make toaster-reconfigure-build$(COLOR_RESET)        Refresh imported build project"
	@echo -e "  $(COLOR_GREEN)make toaster-open-build$(COLOR_RESET)               Open imported project page"
	@echo ""
	@echo -e "$(COLOR_BOLD)Maintenance:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make clean$(COLOR_RESET)                           Clean build artifacts (keeps sstate)"
	@echo -e "  $(COLOR_GREEN)make distclean$(COLOR_RESET)                       Clean everything"
	@echo -e "  $(COLOR_GREEN)make deploy-sstate$(COLOR_RESET)                   Upload sstate cache (rsync)"
	@echo -e "  $(COLOR_GREEN)make deploy-downloads$(COLOR_RESET)                Upload downloads cache (rsync)"
	@echo -e "  $(COLOR_GREEN)make update$(COLOR_RESET)                          Update repo + pinned submodules (safe/default)"
	@echo -e "  $(COLOR_GREEN)make sync$(COLOR_RESET)                            Same as make update (safe/pinned)"
	@echo -e "  $(COLOR_GREEN)make update-upstream$(COLOR_RESET)                 Update submodules to upstream HEAD (DEV ONLY, unpinned)"
	@echo -e "  $(COLOR_GREEN)SYNC_EXCLUDE=meta-coolstream meta-tuxbox-toolchain$(COLOR_RESET)  Skip submodules in make sync"
	@echo ""
	@echo -e "$(COLOR_BOLD)Information:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make info$(COLOR_RESET)                            Build system status overview"
	@echo -e "  $(COLOR_GREEN)make info MACHINE=hd51$(COLOR_RESET)               Status overview for specific machine"
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
	@echo -e "  FORCE_INIT   Force re-run init (default: 0)"
	@echo -e "  QEMU_MACHINE QEMU machine (default: qemux86-64)"
	@echo -e "  QEMU_IMAGE   QEMU image name (default: tuxbox-qemu-image)"
	@echo -e "  QEMU_ARGS    Extra args for run-qemu.sh (default: auto net)"
	@echo -e "  QEMU_BUILD_DIR Build dir for QEMU (default: builds, legacy: build)"
	@echo -e "  TOASTER_BUILD_DIR Build dir for Toaster env (default: $(CONF_BUILDDIR))"
	@echo -e "  TOASTER_VENV Toaster Python venv (default: .tuxbox/toaster-venv)"
	@echo -e "  TOASTER_PYTHON Python executable for Toaster venv (default: python3)"
	@echo -e "  TOASTER_DIR  Toaster data dir (default: .tuxbox/toaster)"
	@echo -e "  TOASTER_WEBPORT Toaster bind address (default: localhost:8000)"
	@echo -e "  TOASTER_START_ARGS Extra args passed to toaster start"
	@echo -e "  TOASTER_SESSION_PID PID file for detached toaster shell"
	@echo -e "  TOASTER_SESSION_LOG Log file for detached toaster shell"
	@echo -e "  TOASTER_ADMIN_USERNAME Admin username for non-interactive creation"
	@echo -e "  TOASTER_ADMIN_EMAIL Admin email for non-interactive creation"
	@echo -e "  TOASTER_ADMIN_PASSWORD Admin password for non-interactive creation"
	@echo -e "  TOASTER_IMPORT_NAME Toaster project name for build import (default: DISTRO-build)"
	@echo -e "  TOASTER_IMPORT_PATH Existing build dir to import (default: TOASTER_BUILD_DIR)"
	@echo -e "  TOASTER_IMPORT_CALLBACK Optional callback script for buildimport"
	@echo -e "  TOASTER_LAST_PROJECT_FILE File storing last imported Toaster project id"
	@echo -e "  SSTATE_DEPLOY_SRC Source sstate dir for deploy-sstate (default: sstate-cache)"
	@echo -e "  SSTATE_RSYNC_EXCLUDE Exclude patterns (space/comma-separated)"
	@echo -e "  DL_DEPLOY_SRC Source downloads dir for deploy-downloads (default: downloads)"
	@echo -e "  DL_RSYNC_EXCLUDE Exclude patterns (default: tmp cache *.done *.lock *.tmp)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Examples:$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=hd60$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=zgemmah7 DISTRO_TYPE=development$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make qemu-run$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make qemu-smoke$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make stb-smoke MACHINE=qemux86-64$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make flash-preflight-smoke$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make init-toaster MACHINE=hd60 MACHINEBUILD=ax60$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make toaster-start TOASTER_WEBPORT=127.0.0.1:8000$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make toaster-create-admin$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make toaster-create-admin TOASTER_ADMIN_USERNAME=admin TOASTER_ADMIN_EMAIL=admin@example.org TOASTER_ADMIN_PASSWORD='secret'$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make toaster-import-build$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make toaster-open-build$(COLOR_RESET)"
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
ifeq ($(USE_CLI),1)
init:
	@run_init=0; \
	if [[ "$(FORCE_INIT)" =~ ^(1|yes|true)$$ ]]; then \
		run_init=1; \
	elif [[ ! -f "$(STATE_FILE)" ]]; then \
		run_init=1; \
	fi; \
	if [[ $$run_init -eq 1 ]]; then \
		echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) init $(MACHINE_ARG) $(MACHINEBUILD_ARG)"; \
		$(CLI) init $(MACHINE_ARG) $(MACHINEBUILD_ARG); \
	fi
else
init: check
	@echo -e "$(COLOR_BOLD)Initializing Tuxbox-OS build environment...$(COLOR_RESET)"
	@$(TOPDIR)/scripts/init.sh
endif

.PHONY: image
image: init
ifeq ($(USE_CLI),1)
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG)"
	@$(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG)
else
ifeq ($(MACHINE_EXPLICIT),)
	@echo -e "$(COLOR_BOLD)Building image using existing config...$(COLOR_RESET)"
else
	@echo -e "$(COLOR_BOLD)Building image for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
endif
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: qemu-run
qemu-run:
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) MACHINE=$(QEMU_MACHINE) IMAGE=$(QEMU_IMAGE) BUILD_DIR=$(QEMU_BUILD_DIR) ./scripts/qemu/run-qemu.sh $(QEMU_ARGS)"
	@MACHINE=$(QEMU_MACHINE) IMAGE=$(QEMU_IMAGE) BUILD_DIR=$(QEMU_BUILD_DIR) ./scripts/qemu/run-qemu.sh $(QEMU_ARGS)

.PHONY: qemu-smoke
qemu-smoke:
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) ./scripts/qemu/smoke-test.sh"
	@./scripts/qemu/smoke-test.sh

.PHONY: stb-smoke
stb-smoke:
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) MACHINE=$(MACHINE) BUILD_DIR=$(BUILDDIR) DISTRO=$(DISTRO) DISTRO_TYPE=$(DISTRO_TYPE) ./scripts/stb-plugins-smoke.sh"
	@MACHINE=$(MACHINE) BUILD_DIR=$(BUILDDIR) DISTRO=$(DISTRO) DISTRO_TYPE=$(DISTRO_TYPE) ./scripts/stb-plugins-smoke.sh

.PHONY: flash-preflight-smoke
flash-preflight-smoke:
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) ./scripts/flash-backend-preflight-smoke.sh"
	@./scripts/flash-backend-preflight-smoke.sh

.PHONY: init-toaster
init-toaster: init
	@echo -e "$(COLOR_BOLD)Initializing Toaster environment...$(COLOR_RESET)"
	@conf_dir="$(TOASTER_BUILD_DIR)/conf"; \
	local_conf="$$conf_dir/local.conf"; \
	bblayers_conf="$$conf_dir/bblayers.conf"; \
	if [[ ! -f "$$local_conf" || ! -f "$$bblayers_conf" ]]; then \
		echo -e "$(COLOR_YELLOW)Config missing in $(TOASTER_BUILD_DIR). Running make config...$(COLOR_RESET)"; \
		$(MAKE) --no-print-directory config MACHINE=$(MACHINE) MACHINEBUILD=$(MACHINEBUILD) DISTRO=$(DISTRO) DISTRO_TYPE=$(DISTRO_TYPE); \
	fi; \
	if [[ ! -f "$$local_conf" || ! -f "$$bblayers_conf" ]]; then \
		echo -e "$(COLOR_RED)Config missing after generation: $$conf_dir$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	toaster_bin="$(TOPDIR)/poky/bitbake/bin/toaster"; \
	toaster_req="$(TOPDIR)/poky/bitbake/toaster-requirements.txt"; \
	if [[ ! -f "$$oe_init" ]]; then \
		echo -e "$(COLOR_RED)OE init script not found: $$oe_init$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -f "$$toaster_bin" ]]; then \
		echo -e "$(COLOR_RED)Toaster script not found: $$toaster_bin$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -f "$$toaster_req" ]]; then \
		echo -e "$(COLOR_RED)Toaster requirements not found: $$toaster_req$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if ! command -v "$(TOASTER_PYTHON)" >/dev/null 2>&1; then \
		echo -e "$(COLOR_RED)Python not found: $(TOASTER_PYTHON)$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Set TOASTER_PYTHON=<python3.12 path> if needed.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	mkdir -p "$(TOASTER_DIR)" "$(dir $(TOASTER_VENV))"; \
	recreate_venv=0; \
	if [[ ! -x "$(TOASTER_VENV)/bin/python3" ]]; then \
		recreate_venv=1; \
	elif ! "$(TOASTER_VENV)/bin/python3" -c "import cgi" >/dev/null 2>&1 && [[ "$(TOASTER_PYTHON)" != "python3" ]]; then \
		echo -e "$(COLOR_YELLOW)Recreating Toaster venv with $(TOASTER_PYTHON)$(COLOR_RESET)"; \
		rm -rf "$(TOASTER_VENV)"; \
		recreate_venv=1; \
	fi; \
	if [[ $$recreate_venv -eq 1 ]]; then \
		echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(TOASTER_PYTHON) -m venv $(TOASTER_VENV)"; \
		"$(TOASTER_PYTHON)" -m venv "$(TOASTER_VENV)"; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(TOASTER_VENV)/bin/pip install --upgrade pip"; \
	"$(TOASTER_VENV)/bin/pip" install --upgrade pip; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(TOASTER_VENV)/bin/pip install -r $$toaster_req"; \
	"$(TOASTER_VENV)/bin/pip" install -r "$$toaster_req"; \
	if ! "$(TOASTER_VENV)/bin/python3" -c "import cgi" >/dev/null 2>&1; then \
		echo -e "$(COLOR_YELLOW)Command:$(COLOR_RESET) $(TOASTER_VENV)/bin/pip install legacy-cgi"; \
		"$(TOASTER_VENV)/bin/pip" install legacy-cgi; \
	fi; \
	if ! "$(TOASTER_VENV)/bin/python3" -c "import cgi" >/dev/null 2>&1; then \
		echo -e "$(COLOR_RED)Toaster requires a working 'cgi' module inside venv.$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Current venv python: $$($(TOASTER_VENV)/bin/python3 --version 2>/dev/null || true)$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Use TOASTER_PYTHON=python3.12 and remove $(TOASTER_VENV) if needed.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && source $$toaster_bin start noweb nobuild toasterdir=$(TOASTER_DIR)"; \
	bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && source '$$toaster_bin' start noweb nobuild toasterdir='$(TOASTER_DIR)'"; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && source $$toaster_bin stop toasterdir=$(TOASTER_DIR)"; \
	bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && source '$$toaster_bin' stop toasterdir='$(TOASTER_DIR)'"; \
	echo -e "$(COLOR_GREEN)Toaster setup complete.$(COLOR_RESET)"; \
	echo -e "Start with: make toaster-start TOASTER_WEBPORT=$(TOASTER_WEBPORT)"; \
	echo -e "Stop with : make toaster-stop"

.PHONY: toaster-start
toaster-start:
	@echo -e "$(COLOR_BOLD)Starting Toaster at http://$(TOASTER_WEBPORT)...$(COLOR_RESET)"
	@oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	toaster_bin="$(TOPDIR)/poky/bitbake/bin/toaster"; \
	session_pid_file="$(TOASTER_SESSION_PID)"; \
	session_log_file="$(TOASTER_SESSION_LOG)"; \
	toastermain_pid_file="$(TOASTER_BUILD_DIR)/.toastermain.pid"; \
	if [[ -f "$$session_pid_file" ]]; then \
		session_pid=$$(cat "$$session_pid_file" 2>/dev/null || true); \
		if [[ -n "$$session_pid" ]] && kill -0 "$$session_pid" 2>/dev/null; then \
			main_pid=$$(cat "$$toastermain_pid_file" 2>/dev/null || true); \
			if [[ -n "$$main_pid" ]] && kill -0 "$$main_pid" 2>/dev/null; then \
				echo -e "$(COLOR_YELLOW)Toaster session already running (session $$session_pid, web $$main_pid).$(COLOR_RESET)"; \
				exit 0; \
			fi; \
			echo -e "$(COLOR_YELLOW)Stale Toaster session detected (pid $$session_pid); cleaning up.$(COLOR_RESET)"; \
			kill "$$session_pid" 2>/dev/null || true; \
		fi; \
		rm -f "$$session_pid_file"; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) make --no-print-directory init-toaster"; \
	$(MAKE) --no-print-directory init-toaster \
		MACHINE="$(MACHINE)" \
		MACHINEBUILD="$(MACHINEBUILD)" \
		DISTRO="$(DISTRO)" \
		DISTRO_TYPE="$(DISTRO_TYPE)" \
		TOASTER_BUILD_DIR="$(TOASTER_BUILD_DIR)" \
		TOASTER_DIR="$(TOASTER_DIR)" \
		TOASTER_VENV="$(TOASTER_VENV)" \
		TOASTER_PYTHON="$(TOASTER_PYTHON)"; \
	if [[ ! -x "$(TOASTER_VENV)/bin/python3" ]]; then \
		echo -e "$(COLOR_RED)Toaster venv missing: $(TOASTER_VENV). Run 'make init-toaster'.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) setsid bash -lc \"source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && source $$toaster_bin start webport=$(TOASTER_WEBPORT) toasterdir=$(TOASTER_DIR) $(TOASTER_START_ARGS) && while :; do sleep 3600; done\""; \
	setsid bash -lc "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && source '$$toaster_bin' start webport='$(TOASTER_WEBPORT)' toasterdir='$(TOASTER_DIR)' $(TOASTER_START_ARGS) && while :; do sleep 3600; done" </dev/null >"$$session_log_file" 2>&1 & \
	echo $$! > "$$session_pid_file"; \
	sleep 2; \
	session_pid=$$(cat "$$session_pid_file" 2>/dev/null || true); \
	if [[ -z "$$session_pid" ]] || ! kill -0 "$$session_pid" 2>/dev/null; then \
		echo -e "$(COLOR_RED)Toaster session failed to stay alive. See $$session_log_file$(COLOR_RESET)"; \
		tail -n 80 "$$session_log_file" 2>/dev/null || true; \
		exit 1; \
	fi; \
	main_pid=""; \
	for _ in $$(seq 1 30); do \
		main_pid=$$(cat "$$toastermain_pid_file" 2>/dev/null || true); \
		if [[ -n "$$main_pid" ]] && kill -0 "$$main_pid" 2>/dev/null; then \
			break; \
		fi; \
		sleep 1; \
	done; \
	if [[ -z "$$main_pid" ]] || ! kill -0 "$$main_pid" 2>/dev/null; then \
		echo -e "$(COLOR_RED)Toaster web process failed to start. See $$session_log_file$(COLOR_RESET)"; \
		tail -n 80 "$$session_log_file" 2>/dev/null || true; \
		kill "$$session_pid" 2>/dev/null || true; \
		rm -f "$$session_pid_file"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_GREEN)Toaster session started (pid $$session_pid).$(COLOR_RESET)"

.PHONY: toaster-stop
toaster-stop:
	@echo -e "$(COLOR_BOLD)Stopping Toaster...$(COLOR_RESET)"
	@oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	toaster_bin="$(TOPDIR)/poky/bitbake/bin/toaster"; \
	if [[ ! -f "$$oe_init" || ! -f "$$toaster_bin" ]]; then \
		echo -e "$(COLOR_RED)Toaster scripts not found. Is poky initialized?$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && source $$toaster_bin stop toasterdir=$(TOASTER_DIR)"; \
	bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && source '$$toaster_bin' stop toasterdir='$(TOASTER_DIR)'"; \
	session_pid_file="$(TOASTER_SESSION_PID)"; \
	if [[ -f "$$session_pid_file" ]]; then \
		session_pid=$$(cat "$$session_pid_file" 2>/dev/null || true); \
		if [[ -n "$$session_pid" ]] && kill -0 "$$session_pid" 2>/dev/null; then \
			kill "$$session_pid" 2>/dev/null || true; \
		fi; \
		rm -f "$$session_pid_file"; \
	fi

.PHONY: toaster-create-admin
toaster-create-admin: init-toaster
	@echo -e "$(COLOR_BOLD)Creating Toaster admin user...$(COLOR_RESET)"
	@oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	manage_py="$(TOPDIR)/poky/bitbake/lib/toaster/manage.py"; \
	if [[ ! -x "$(TOASTER_VENV)/bin/python3" ]]; then \
		echo -e "$(COLOR_RED)Toaster venv missing: $(TOASTER_VENV). Run 'make init-toaster'.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ -n "$(TOASTER_ADMIN_USERNAME)" || -n "$(TOASTER_ADMIN_EMAIL)" || -n "$(TOASTER_ADMIN_PASSWORD)" ]]; then \
		if [[ -z "$(TOASTER_ADMIN_USERNAME)" || -z "$(TOASTER_ADMIN_EMAIL)" || -z "$(TOASTER_ADMIN_PASSWORD)" ]]; then \
			echo -e "$(COLOR_RED)For non-interactive mode set all three: TOASTER_ADMIN_USERNAME, TOASTER_ADMIN_EMAIL, TOASTER_ADMIN_PASSWORD.$(COLOR_RESET)"; \
			exit 1; \
		fi; \
		echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && python3 $$manage_py createsuperuser --noinput --username $(TOASTER_ADMIN_USERNAME) --email $(TOASTER_ADMIN_EMAIL)"; \
		bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && export TOASTER_DIR='$(TOASTER_DIR)' && export DJANGO_SUPERUSER_PASSWORD='$(TOASTER_ADMIN_PASSWORD)' && python3 '$$manage_py' createsuperuser --noinput --username '$(TOASTER_ADMIN_USERNAME)' --email '$(TOASTER_ADMIN_EMAIL)'"; \
	else \
		echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && python3 $$manage_py createsuperuser"; \
		bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && export TOASTER_DIR='$(TOASTER_DIR)' && python3 '$$manage_py' createsuperuser"; \
	fi

.PHONY: toaster-import-build
toaster-import-build: init-toaster
	@echo -e "$(COLOR_BOLD)Importing existing build directory into Toaster...$(COLOR_RESET)"
	@oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	manage_py="$(TOPDIR)/poky/bitbake/lib/toaster/manage.py"; \
	import_path="$(TOASTER_IMPORT_PATH)"; \
	if [[ -z "$(TOASTER_IMPORT_NAME)" ]]; then \
		echo -e "$(COLOR_RED)TOASTER_IMPORT_NAME must not be empty.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -d "$$import_path" ]]; then \
		echo -e "$(COLOR_RED)Import path does not exist: $$import_path$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	import_path="$$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$$import_path")"; \
	if [[ ! -f "$$import_path/conf/local.conf" || ! -f "$$import_path/conf/bblayers.conf" ]]; then \
		echo -e "$(COLOR_RED)Import path is not a configured build dir: $$import_path$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Expected conf/local.conf and conf/bblayers.conf.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -x "$(TOASTER_VENV)/bin/python3" ]]; then \
		echo -e "$(COLOR_RED)Toaster venv missing: $(TOASTER_VENV). Run 'make init-toaster'.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && python3 $$manage_py buildimport --name $(TOASTER_IMPORT_NAME) --path $$import_path --callback $(TOASTER_IMPORT_CALLBACK) --command import"; \
	import_output="$$(bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && export TOASTER_DIR='$(TOASTER_DIR)' && python3 '$$manage_py' buildimport --name '$(TOASTER_IMPORT_NAME)' --path '$$import_path' --callback '$(TOASTER_IMPORT_CALLBACK)' --command import")"; \
	printf '%s\n' "$$import_output"; \
	project_id="$$(printf '%s\n' "$$import_output" | sed -n 's/.*Project_id=\([0-9]\+\).*/\1/p' | tail -n 1)"; \
	if [[ -z "$$project_id" ]]; then \
		echo -e "$(COLOR_RED)Failed to parse Project_id from buildimport output.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	mkdir -p "$(dir $(TOASTER_LAST_PROJECT_FILE))"; \
	printf '%s\n' "$$project_id" > "$(TOASTER_LAST_PROJECT_FILE)"; \
	echo -e "$(COLOR_GREEN)Imported project id $$project_id (name: $(TOASTER_IMPORT_NAME)).$(COLOR_RESET)"; \
	echo -e "Project page: http://$(TOASTER_WEBPORT)/toastergui/project_specific/$$project_id"

.PHONY: toaster-reconfigure-build
toaster-reconfigure-build: init-toaster
	@echo -e "$(COLOR_BOLD)Reconfiguring imported Toaster build project...$(COLOR_RESET)"
	@oe_init="$(TOPDIR)/poky/oe-init-build-env"; \
	manage_py="$(TOPDIR)/poky/bitbake/lib/toaster/manage.py"; \
	import_path="$(TOASTER_IMPORT_PATH)"; \
	if [[ -z "$(TOASTER_IMPORT_NAME)" ]]; then \
		echo -e "$(COLOR_RED)TOASTER_IMPORT_NAME must not be empty.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -d "$$import_path" ]]; then \
		echo -e "$(COLOR_RED)Import path does not exist: $$import_path$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	import_path="$$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$$import_path")"; \
	if [[ ! -f "$$import_path/conf/local.conf" || ! -f "$$import_path/conf/bblayers.conf" ]]; then \
		echo -e "$(COLOR_RED)Import path is not a configured build dir: $$import_path$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Expected conf/local.conf and conf/bblayers.conf.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	if [[ ! -x "$(TOASTER_VENV)/bin/python3" ]]; then \
		echo -e "$(COLOR_RED)Toaster venv missing: $(TOASTER_VENV). Run 'make init-toaster'.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(TOASTER_BUILD_DIR) >/dev/null && python3 $$manage_py buildimport --name $(TOASTER_IMPORT_NAME) --path $$import_path --callback $(TOASTER_IMPORT_CALLBACK) --command reconfigure"; \
	import_output="$$(bash -c "source '$$oe_init' '$(TOASTER_BUILD_DIR)' >/dev/null && export PATH='$(TOASTER_VENV)/bin:'\"\$$PATH\" && export TOASTER_DIR='$(TOASTER_DIR)' && python3 '$$manage_py' buildimport --name '$(TOASTER_IMPORT_NAME)' --path '$$import_path' --callback '$(TOASTER_IMPORT_CALLBACK)' --command reconfigure")"; \
	printf '%s\n' "$$import_output"; \
	project_id="$$(printf '%s\n' "$$import_output" | sed -n 's/.*Project_id=\([0-9]\+\).*/\1/p' | tail -n 1)"; \
	if [[ -z "$$project_id" ]]; then \
		echo -e "$(COLOR_RED)Failed to parse Project_id from buildimport output.$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Run 'make toaster-import-build' first if the project does not exist yet.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	mkdir -p "$(dir $(TOASTER_LAST_PROJECT_FILE))"; \
	printf '%s\n' "$$project_id" > "$(TOASTER_LAST_PROJECT_FILE)"; \
	echo -e "$(COLOR_GREEN)Reconfigured project id $$project_id (name: $(TOASTER_IMPORT_NAME)).$(COLOR_RESET)"; \
	echo -e "Project page: http://$(TOASTER_WEBPORT)/toastergui/project_specific/$$project_id"

.PHONY: toaster-open-build
toaster-open-build: init-toaster
	@echo -e "$(COLOR_BOLD)Opening imported Toaster project page...$(COLOR_RESET)"
	@project_id=""; \
	if [[ -f "$(TOASTER_LAST_PROJECT_FILE)" ]]; then \
		project_id="$$(sed -n '1p' "$(TOASTER_LAST_PROJECT_FILE)" | tr -d '[:space:]')"; \
	fi; \
	if [[ -z "$$project_id" ]]; then \
		db_path="$(TOASTER_DIR)/toaster.sqlite"; \
		if [[ ! -f "$$db_path" ]]; then \
			echo -e "$(COLOR_RED)Toaster database not found: $$db_path$(COLOR_RESET)"; \
			echo -e "$(COLOR_YELLOW)Run 'make toaster-import-build' first.$(COLOR_RESET)"; \
			exit 1; \
		fi; \
		project_id="$$(python3 -c "import sqlite3,sys; conn=sqlite3.connect(sys.argv[1]); cur=conn.cursor(); cur.execute(\"SELECT id FROM orm_project WHERE name = ? ORDER BY id DESC LIMIT 1\", (sys.argv[2],)); row=cur.fetchone(); print(row[0] if row else \"\")" "$$db_path" "$(TOASTER_IMPORT_NAME)")"; \
	fi; \
	if [[ -z "$$project_id" ]]; then \
		echo -e "$(COLOR_RED)No Toaster project id found for name '$(TOASTER_IMPORT_NAME)'.$(COLOR_RESET)"; \
		echo -e "$(COLOR_YELLOW)Run 'make toaster-import-build' first.$(COLOR_RESET)"; \
		exit 1; \
	fi; \
	url="http://$(TOASTER_WEBPORT)/toastergui/project_specific/$$project_id"; \
	echo -e "$(COLOR_GREEN)Project URL: $$url$(COLOR_RESET)"; \
	if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open "$$url" >/dev/null 2>&1 || true; \
	else \
		echo -e "$(COLOR_YELLOW)xdg-open not found. Open URL manually.$(COLOR_RESET)"; \
	fi

.PHONY: config
config: init
ifeq ($(USE_CLI),1)
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)"
	@$(CLI) config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_BOLD)Generating config for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: show-config
show-config:
ifeq ($(USE_CLI),1)
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) show-config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)"
	@$(CLI) show-config --machine $(MACHINE) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_BOLD)Showing config for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
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
ifeq ($(USE_CLI),1)
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) build --machine $(MACHINE) $(MACHINEBUILD_ARG) --devshell $(FORCE_CONFIG_ARG)"
	@$(CLI) build --machine $(MACHINE) $(MACHINEBUILD_ARG) --devshell $(FORCE_CONFIG_ARG)
else
	@echo -e "$(COLOR_BOLD)Starting development shell for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: bb
bb: init
	@if [[ -z "$(BB_CMD)" ]]; then \
		echo -e "$(COLOR_RED)Missing BitBake args. Use 'make bb-<target>' or set BB_ARGS/BB_TASK/BB_TARGET.$(COLOR_RESET)"; \
		exit 1; \
	fi
ifeq ($(USE_CLI),1)
	@echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) $(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG) --target \"$(BB_CMD)\""
	@$(CLI) build $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE) $(FORCE_CONFIG_ARG) --target "$(BB_CMD)"
else
	@echo -e "$(COLOR_BOLD)Running BitBake...$(COLOR_RESET)"
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
	echo -e "$(COLOR_BOLD)Command:$(COLOR_RESET) source $$oe_init $(CONF_BUILDDIR) >/dev/null && devtool $(DEVTOOL_ARGS)"; \
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

.PHONY: update update-upstream
update:
	@echo -e "$(COLOR_BOLD)Running safe update (pinned)...$(COLOR_RESET)"
	@$(MAKE) --no-print-directory sync

update-upstream:
	@echo -e "$(COLOR_BOLD)Syncing submodule URLs...$(COLOR_RESET)"
	@git submodule sync --recursive
	@echo -e "$(COLOR_YELLOW)Warning: make update-upstream moves submodules to upstream HEAD (unpinned).$(COLOR_RESET)"
	@echo -e "$(COLOR_YELLOW)Use this only when you intend to update layer pins; for builds use make update (or make sync).$(COLOR_RESET)"
	@echo -e "$(COLOR_YELLOW)It will leave the working tree dirty unless you commit updated pointers.$(COLOR_RESET)"
	@echo -e "$(COLOR_BOLD)Updating submodules to upstream HEAD (unpinned)...$(COLOR_RESET)"
	@git submodule update --remote --recursive
	@echo -e "$(COLOR_GREEN)Submodules updated (unpinned).$(COLOR_RESET)"
	@echo -e "$(COLOR_YELLOW)Run make update (or make sync) to return to the current pinned dev state.$(COLOR_RESET)"

.PHONY: sync
sync:
	@echo -e "$(COLOR_BOLD)Updating repository...$(COLOR_RESET)"
	@git pull --ff-only
	@echo -e "$(COLOR_BOLD)Syncing submodule URLs...$(COLOR_RESET)"
	@git submodule sync --recursive
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

.PHONY: info
info:
ifeq ($(USE_CLI),1)
	@$(CLI) info $(MACHINE_ARG) $(MACHINEBUILD_ARG) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: version
version:
ifeq ($(USE_CLI),1)
	@$(CLI) version
else
	@echo "Tuxbox-OS Builder"
	@echo "Python: $$(python3 --version)"
	@echo "Git: $$(git --version)"
endif
